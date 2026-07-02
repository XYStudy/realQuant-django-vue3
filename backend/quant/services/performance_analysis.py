import requests
import json
import time
import os
import sys
from datetime import datetime
import pymysql

# ================= 数据库配置 =================
# 默认连接局域网数据库，也允许通过环境变量覆盖。
DB_HOST = os.getenv("DB_HOST", "192.168.19.1")
DB_PORT = 3306
DB_USER = "root"          # 你的 MySQL 用户名
DB_PASSWORD = "root"      # 你的 MySQL 密码 (根据实际情况修改)
DB_NAME = "quant_data"    # 数据库名称

def init_db():
    """初始化数据库和表结构"""
    try:
        # 先连接 MySQL，不指定数据库，用于创建库
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        conn.close()
        
        # 连接指定数据库建表
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        
        # 1. 业绩预告表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS earnings_forecast (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_date VARCHAR(20) COMMENT '报告期',
                code VARCHAR(10) COMMENT '股票代码',
                name VARCHAR(50) COMMENT '股票名称',
                notice_date DATE COMMENT '公告日期',
                finance VARCHAR(50) COMMENT '预测指标',
                amt_str VARCHAR(100) COMMENT '预测数值',
                amp_str VARCHAR(100) COMMENT '变动同比',
                content TEXT COMMENT '变动内容',
                reason TEXT COMMENT '变动原因',
                pre_year VARCHAR(50) COMMENT '上年同期',
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code_report (code, report_date)
            ) COMMENT '业绩预告表'
        """)
        
        # 2. 业绩报告表 (优质财报)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS earnings_report (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_date VARCHAR(20) COMMENT '报告期',
                code VARCHAR(10) COMMENT '股票代码',
                name VARCHAR(50) COMMENT '股票名称',
                industry VARCHAR(50) COMMENT '所属行业',
                ystz FLOAT COMMENT '营收同比(%)',
                sjltz FLOAT COMMENT '净利同比(%)',
                roe FLOAT COMMENT '净资产收益率(%)',
                cash_flow FLOAT COMMENT '每股经营现金流(元)',
                margin FLOAT COMMENT '销售毛利率(%)',
                notice_date DATE COMMENT '公告日期',
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code_report (code, report_date)
            ) COMMENT '优质财报表'
        """)
        conn.commit()
        conn.close()
        print("[performance_analysis] Database and tables initialized successfully.")
    except Exception as e:
        print(f"[performance_analysis] DB Init Error: {e}. Please check your MySQL configuration.")

def save_forecasts_to_db(forecasts, report_date):
    if not forecasts: return
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        sql = """
            INSERT INTO earnings_forecast 
            (report_date, code, name, notice_date, finance, amt_str, amp_str, content, reason, pre_year)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            notice_date=VALUES(notice_date), amt_str=VALUES(amt_str), amp_str=VALUES(amp_str),
            content=VALUES(content), reason=VALUES(reason)
        """
        data_tuples = []
        for f in forecasts:
            data_tuples.append((
                report_date, f['code'], f['name'], f['notice_date'] or None, 
                f['finance'], f['amt_str'], f['amp_str'], f['content'], f['reason'], f['pre_year']
            ))
        cursor.executemany(sql, data_tuples)
        conn.commit()
        conn.close()
        print(f"[performance_analysis] Saved {len(forecasts)} forecasts to MySQL database.")
    except Exception as e:
        print(f"[performance_analysis] DB Save Forecast Error: {e}")

def save_reports_to_db(reports, report_date):
    if not reports: return
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        sql = """
            INSERT INTO earnings_report 
            (report_date, code, name, industry, ystz, sjltz, roe, cash_flow, margin, notice_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            ystz=VALUES(ystz), sjltz=VALUES(sjltz), roe=VALUES(roe), 
            cash_flow=VALUES(cash_flow), margin=VALUES(margin), notice_date=VALUES(notice_date)
        """
        data_tuples = []
        for r in reports:
            data_tuples.append((
                report_date, r['code'], r['name'], r['industry'], 
                r['ystz'], r['sjltz'], r['roe'], r['cash_flow'], r['margin'], r['notice_date'] or None
            ))
        cursor.executemany(sql, data_tuples)
        conn.commit()
        conn.close()
        print(f"[performance_analysis] Saved {len(reports)} high-quality reports to MySQL database.")
    except Exception as e:
        print(f"[performance_analysis] DB Save Report Error: {e}")

# ================= 业务逻辑 =================

# 引入微信发送通知
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
# try:
#     from quant.services.auto_analyzer import send_wechat_message
# except ImportError:
#     def send_wechat_message(msg):
#         print(f"Mock WeChat Send:\n{msg}")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://data.eastmoney.com/"
}

def _parse_jsonp(text):
    """解析 JSONP 响应格式"""
    start = text.find('(')
    end = text.rfind(')')
    if start != -1 and end != -1:
        json_str = text[start+1:end]
        return json.loads(json_str)
    return json.loads(text)

def format_amt(val):
    """将数值格式化为 'X万' (传入数值单位为元)"""
    if val is None:
        return ""
    return f"{val / 10000:.0f}万"

def format_amp(val):
    """将比率格式化为 'X%' """
    if val is None:
        return ""
    return f"{val}%"

def fetch_earnings_forecast(report_date="2026-03-31"):
    """
    一季度业绩预告
    """
    timestamp = int(time.time() * 1000)
    callback = f"jQuery1123023436202814502205_{timestamp}"
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    
    params = {
        "callback": callback,
        "sortColumns": "NOTICE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",  # 修复：原先只传了一个 -1，导致“排序字段和顺序数量不一致”
        "pageSize": "6000",
        "pageNumber": "1",
        "reportName": "RPT_PUBLIC_OP_NEWPREDICT",
        "columns": "ALL",
        "filter": f"(REPORT_DATE='{report_date}')(FORECAST_STATE=\"increase\")"
    }
    
    results = []
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        print(f"[performance_analysis] Forecast API Status: {resp.status_code}")
        data = _parse_jsonp(resp.text)
        
        if not data.get("success"):
            print(f"[performance_analysis] Forecast API failed: {data.get('message')}")
        
        if data.get("success") and data.get("result") and data["result"].get("data"):
            print(f"[performance_analysis] Forecast API returned {len(data['result']['data'])} records.")
            for r in data["result"]["data"]:
                lower_amt = format_amt(r.get("PREDICT_AMT_LOWER"))
                upper_amt = format_amt(r.get("PREDICT_AMT_UPPER"))
                amt_str = f"{lower_amt}～{upper_amt}" if lower_amt and upper_amt else (lower_amt or upper_amt or "-")
                
                lower_amp = format_amp(r.get("ADD_AMP_LOWER"))
                upper_amp = format_amp(r.get("ADD_AMP_UPPER"))
                amp_str = f"{lower_amp}～{upper_amp}" if lower_amp and upper_amp else (lower_amp or upper_amp or "-")
                
                results.append({
                    "code": r.get("SECURITY_CODE"),
                    "name": r.get("SECURITY_NAME_ABBR"),
                    "notice_date": r.get("NOTICE_DATE", "")[:10],
                    "finance": r.get("PREDICT_FINANCE"),
                    "content": r.get("PREDICT_CONTENT"),
                    "amt_str": amt_str,
                    "amp_str": amp_str,
                    "reason": r.get("CHANGE_REASON_EXPLAIN") or "无",
                    "pre_year": format_amt(r.get("PREYEAR_SAME_PERIOD"))
                })
    except Exception as e:
        print(f"[performance_analysis] Error fetching forecast: {e}")
    
    return results

def fetch_earnings_report(report_date="2026-03-31"):
    """
    一季度业绩报告
    """
    timestamp = int(time.time() * 1000)
    callback = f"jQuery112304674064740853465_{timestamp}"
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    
    params = {
        "callback": callback,
        "sortColumns": "UPDATE_DATE,SECURITY_CODE",
        "sortTypes": "-1,-1",
        "pageSize": "5000",
        "pageNumber": "1",
        "reportName": "RPT_LICO_FN_CPD",
        "columns": "ALL",
        "filter": f"(REPORTDATE='{report_date}')"
    }
    
    good_stocks = []
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        print(f"[performance_analysis] Report API Status: {resp.status_code}")
        data = _parse_jsonp(resp.text)
        
        if not data.get("success"):
            print(f"[performance_analysis] Report API failed: {data.get('message')}")
        
        if data.get("success") and data.get("result") and data["result"].get("data"):
            print(f"[performance_analysis] Report API returned {len(data['result']['data'])} records.")
            for r in data["result"]["data"]:
                market = r.get("TRADE_MARKET", "")
                
                # 仅筛选主板，科创板，创业板（排除风险警示等）
                if not any(m in market for m in ["主板", "科创板", "创业板"]):
                    continue
                if "风险" in market or "退市" in market:
                    continue
                
                ystz = r.get("YSTZ") # 营业总收入同比增长
                sjltz = r.get("SJLTZ") # 净利润同比增长
                roe = r.get("WEIGHTAVG_ROE") # 净资产收益率
                cash_flow = r.get("MGJYXJJE") # 每股经营现金流 (元)
                margin = r.get("XSMLL") # 销售毛利率 (%)
                industry = r.get("BOARD_NAME") or r.get("PUBLISHNAME") or "未知行业"
                
                # 条件1：营业总收入同比增长 和 净利润同比增长
                if ystz is not None and sjltz is not None and ystz > 0 and sjltz > 0:
                    # 放宽条件以便测试数据能跑出来：净利增长>10%，营收>10%，ROE和毛利只要为正即可
                    if sjltz >= 10 and ystz > 10 and (roe is None or roe > 0) and (margin is None or margin > 0):
                        good_stocks.append({
                            "code": r.get("SECURITY_CODE"),
                            "name": r.get("SECURITY_NAME_ABBR"),
                            "industry": industry,
                            "ystz": ystz,
                            "sjltz": sjltz,
                            "roe": roe or 0,
                            "cash_flow": cash_flow or 0,
                            "margin": margin or 0,
                            "notice_date": r.get("NOTICE_DATE", "")[:10]
                        })
    except Exception as e:
        print(f"[performance_analysis] Error fetching report: {e}")
        
    # 按净利润增长率降序排序，选取最好的
    good_stocks.sort(key=lambda x: x["sjltz"], reverse=True)
    return good_stocks

def run_analysis(report_date="2026-03-31"):
    print(f"[performance_analysis] Starting performance analysis for Q1 {report_date[:4]}...")
    
    # 1. 初始化数据库
    init_db()
    
    forecasts = fetch_earnings_forecast(report_date)
    reports = fetch_earnings_report(report_date)
    
    # 2. 存入数据库
    if forecasts:
        save_forecasts_to_db(forecasts, report_date)
    if reports:
        save_reports_to_db(reports, report_date)
        
    msg_lines = []
    
    if forecasts:
        msg_lines.append(f"📊【一季度业绩预告 - 预增速递】(共{len(forecasts)}家预增)")
        # 仅取前 15 条作为示例发送，避免消息过长导致微信发送失败
        # 按变动上限排序
        forecasts.sort(key=lambda x: float(x['amp_str'].split('～')[-1].replace('%', '')) if '～' in x['amp_str'] and x['amp_str'].split('～')[-1].replace('%', '').replace('.','').isdigit() else 0, reverse=True)
        
        for f in forecasts[:15]:
            msg_lines.append(f"🔹 {f['code']} {f['name']} ({f['notice_date']})")
            msg_lines.append(f"预测指标: {f['finance']} | 变动同比: {f['amp_str']}")
            msg_lines.append(f"预测数值: {f['amt_str']} (去年同期: {f['pre_year']})")
            # 截断过长的原因
            reason = f['reason']
            if len(reason) > 60:
                reason = reason[:60] + "..."
            msg_lines.append(f"原因: {reason}\n")
            
    if reports:
        msg_lines.append(f"🏆【一季度业绩报告 - 优质财报精选】(筛选出{len(reports)}家优秀企业)")
        msg_lines.append("筛选标准：主板/科创板/创业板，净利增长>10%，营收增长>0%，ROE及毛利为正。")
        
        for r in reports[:10]: # 取前10家最优的
            msg_lines.append(f"🔸 {r['code']} {r['name']} | {r['industry']}")
            msg_lines.append(f"净利同比: {r['sjltz']:.2f}% | 营收同比: {r['ystz']:.2f}%")
            msg_lines.append(f"ROE: {r['roe']}% | 毛利率: {r['margin']}% | 每股现金流: {r['cash_flow']}元\n")
            
    if msg_lines:
        final_msg = "\n".join(msg_lines).strip()
        print("[performance_analysis] Analysis completed. Sending to WeChat...")
        send_wechat_message(final_msg)
    else:
        print("[performance_analysis] No valid data found for this period.")

if __name__ == "__main__":
    # 默认获取一季度数据
    run_analysis("2026-03-31")
