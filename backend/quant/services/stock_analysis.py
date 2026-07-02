import os
import sys
import pymysql
import json
import requests
import re
from datetime import datetime

# 数据库配置，与 performance_analysis.py 保持一致
DB_HOST = os.getenv("DB_HOST", "192.168.19.1")
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "root"
DB_NAME = "quant_data"

def init_analysis_db():
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_deep_analysis (
                id INT AUTO_INCREMENT PRIMARY KEY,
                report_date VARCHAR(20) COMMENT '分析日期',
                code VARCHAR(10) COMMENT '股票代码',
                name VARCHAR(50) COMMENT '股票名称',
                result_type VARCHAR(50) COMMENT '评级/结果 (S级/淘汰/分数)',
                score INT DEFAULT 0 COMMENT '打分分数',
                analysis_detail TEXT COMMENT '分析详情',
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_code_date (code, report_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='私募首席选股官深度分析表';
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[stock_analysis] DB Init Error: {e}")

def _get_existing_codes(report_date):
    """获取指定日期已经分析过的股票代码列表"""
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT code FROM stock_deep_analysis WHERE report_date=%s", (report_date,))
        rows = cursor.fetchall()
        conn.close()
        return {r[0] for r in rows}
    except Exception as e:
        print(f"[stock_analysis] DB Query Error: {e}")
        return set()

def save_analysis_result(report_date, code, name, result_type, score, detail):
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        sql = """
            INSERT INTO stock_deep_analysis (report_date, code, name, result_type, score, analysis_detail)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            result_type=VALUES(result_type), score=VALUES(score), analysis_detail=VALUES(analysis_detail)
        """
        cursor.execute(sql, (report_date, code, name, result_type, score, detail))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[stock_analysis] DB Save Error: {e}")

def fetch_eastmoney_data(url):
    """通用的东财 JSONP 接口请求函数"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        text = resp.text
        # 提取 jQuery 回调里的 JSON
        match = re.search(r'jQuery\d+_\d+\((.*)\)', text)
        if match:
            json_str = match.group(1)
            data = json.loads(json_str)
            if data.get("result") and data["result"].get("data"):
                return data["result"]["data"]
    except Exception as e:
        print(f"[stock_analysis] Fetch Eastmoney Data Error: {e}")
    return []

_eastmoney_cache = {}

def get_fundamental_data(code):
    """
    根据股票代码，获取上一年的年报、当年的一季报、一季度预告数据
    如果数据存在，则提取核心指标 (ROE, 营收增速, 净利润增速等)
    """
    global _eastmoney_cache
    now = datetime.now()
    current_year = now.year
    
    last_year_report_date = f"{current_year - 1}-12-31"
    q1_report_date = f"{current_year}-03-31"
    
    if not _eastmoney_cache:
        print("[stock_analysis] Fetching global Eastmoney data for cache...")
        # 1. 抓取去年年报
        annual_url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?callback=jQuery112305277734721240838_1776006126970&sortColumns=UPDATE_DATE%2CSECURITY_CODE&sortTypes=-1%2C-1&pageSize=6000&pageNumber=1&reportName=RPT_LICO_FN_CPD&columns=ALL&filter=(REPORTDATE%3D%27{last_year_report_date}%27)"
        # 2. 抓取一季报
        q1_url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?callback=jQuery112306308897919655297_1776006296676&sortColumns=UPDATE_DATE%2CSECURITY_CODE&sortTypes=-1%2C-1&pageSize=6000&pageNumber=1&reportName=RPT_LICO_FN_CPD&columns=ALL&filter=(REPORTDATE%3D%27{q1_report_date}%27)"
        # 3. 抓取一季报预告
        q1_predict_url = f"https://datacenter-web.eastmoney.com/api/data/v1/get?callback=jQuery112300011986681572838664_1776006400944&sortColumns=NOTICE_DATE%2CSECURITY_CODE&sortTypes=-1%2C-1&pageSize=6000&pageNumber=1&reportName=RPT_PUBLIC_OP_NEWPREDICT&columns=ALL&filter=(REPORT_DATE%3D%27{q1_report_date}%27)"
        
        _eastmoney_cache['annual'] = fetch_eastmoney_data(annual_url)
        _eastmoney_cache['q1'] = fetch_eastmoney_data(q1_url)
        _eastmoney_cache['q1_predict'] = fetch_eastmoney_data(q1_predict_url)
    
    annual_data = _eastmoney_cache['annual']
    q1_data = _eastmoney_cache['q1']
    q1_predict_data = _eastmoney_cache['q1_predict']
    
    # 过滤当前股票的数据
    fund_info = []
    
    # 解析年报
    a_row = next((item for item in annual_data if item.get("SECURITY_CODE") == code), None)
    if a_row:
        roe = a_row.get("WEIGHTAVG_ROE", "未知")
        rev_growth = a_row.get("YSTZ", "未知") # 营收同比增长
        profit_growth = a_row.get("SJLTZ", "未知") # 净利润同比增长
        fund_info.append(f"【{current_year-1}年报】ROE: {roe}%，营收同比: {rev_growth}%，净利润同比: {profit_growth}%")
        
    # 解析一季报
    q_row = next((item for item in q1_data if item.get("SECURITY_CODE") == code), None)
    if q_row:
        roe = q_row.get("WEIGHTAVG_ROE", "未知")
        rev_growth = q_row.get("YSTZ", "未知")
        profit_growth = q_row.get("SJLTZ", "未知")
        fund_info.append(f"【{current_year}一季报】ROE: {roe}%，营收同比: {rev_growth}%，净利润同比: {profit_growth}%")
        
    # 解析一季报预告
    p_row = next((item for item in q1_predict_data if item.get("SECURITY_CODE") == code and item.get("PREDICT_FINANCE_CODE") == "004"), None) # 004是归母净利润
    if p_row:
        p_type = p_row.get("PREDICT_TYPE", "未知")
        p_content = p_row.get("PREDICT_CONTENT", "")
        fund_info.append(f"【{current_year}一季报预告】类型: {p_type}，详情: {p_content}")
        
    return "\n".join(fund_info) if fund_info else "暂无最新基本面数据，请根据历史常识推演。"

def run_deep_analysis(file_path):
    """
    读取 15 以内的文本文件，执行私募首席二级漏斗分析
    """
    if not os.path.exists(file_path):
        print(f"[stock_analysis] File not found: {file_path}")
        return
        
    init_analysis_db()
    report_date = datetime.now().strftime("%Y%m%d")
    existing_codes = _get_existing_codes(report_date)
    
    # 1. 解析文件
    recs = []
    try:
        with open(file_path, 'r', encoding='gb18030', errors='ignore') as f:
            lines = f.readlines()
        
        header_idx = -1
        for i, line in enumerate(lines[:10]):
            if "代码" in line or "名称" in line:
                header_idx = i
                break
        
        if header_idx != -1:
            header = lines[header_idx].split('\t')
            code_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["代码", "证券代码", "Code"])), 0)
            name_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["名称", "证券名称", "Name"])), 1)
            data_lines = lines[header_idx+1:]
            
            for line in data_lines:
                parts = line.split('\t')
                if len(parts) > max(code_idx, name_idx):
                    code = parts[code_idx].strip()
                    name = parts[name_idx].strip()
                    if code.isdigit() and len(code) < 6:
                        code = code.zfill(6)
                    # 过滤 9 开头和无效行
                    if code and not code.startswith('9') and "代码" not in code and "数据来源" not in code:
                        recs.append((code, name))
    except Exception as e:
        print(f"[stock_analysis] File Read Error: {e}")
        return
        
    if not recs:
        print("[stock_analysis] No valid records found to analyze.")
        return

    # 2. 筛选出今天还没分析过的增量股票
    new_recs = [(c, n) for c, n in recs if c not in existing_codes]
    if not new_recs:
        print("[stock_analysis] All records in the file have already been analyzed today.")
        return
        
    print(f"[stock_analysis] Found {len(new_recs)} new records to analyze...")
    
    # 3. 逐个调用大模型进行分析
    prompt_template = """角色：你是顶级私募的“首席选股官”，风格综合、严谨且极具洞察力。你不仅看重核心逻辑，更要求“基本面数据”作为压舱石，绝不错杀真正的优质资产，也绝不放过伪成长的讲故事公司。
任务：对提供的股票数据执行“综合多维逻辑漏斗”筛选，解决“不同股票适用不同标准”的问题：

第一步：逻辑赛道界定（决定适用什么核心驱动力）
你必须首先判断该股票的核心炒作/基本面逻辑属于以下哪一条赛道（只选最核心的一个）：
1. 【霸主与垄断】：适用于传统制造、成熟科技（如中际旭创、中国巨石）。考核核心：市占率、定价权、规模效应。
2. 【隐形冠军/专精特新】：适用于在全球或国内某个极小细分领域拥有绝对垄断地位的公司（如福晶科技的光学晶体）。考核核心：极强的不可替代性、极深的技术护城河，即便总营收体量不大，也具有绝对话语权。
3. 【自主可控/国产替代】：适用于半导体、高端装备、信创等被海外“卡脖子”领域（如源杰科技、长光华芯）。考核核心：技术稀缺性、替代海外份额的增速。
4. 【科技/产业周期反转】：适用于存储、面板、航运等（如德明利）。考核核心：行业去库进度、供需格局反转。
5. 【资源垄断/大宗涨价】：适用于深度受益于上游原材料涨价的公司（如金、银、铜、铁、铝、锂、钼、稀土、锗、大豆、化肥、光纤等）。考核核心：拥有核心矿山/资源壁垒、直接受益于现货价格飙升。
6. 【转型重生】：适用于老旧业务跨界超级风口。考核核心：新业务营收占比是否实质性突破。
如果毫无逻辑且处于夕阳内卷行业，直接归为【平庸废料】，立刻淘汰！

第二步：基本面压舱石与逻辑共振打分（满分100）
无论属于哪个赛道，都必须结合基本面进行综合打分。拿不出硬逻辑或基本面常年稀烂的，一律淘汰！
- 核心逻辑稀缺性与爆发力（40分）：市占率优势、隐形冠军的绝对壁垒、替代稀缺性、或者大宗商品涨价带来的利润高弹性。
- 业绩基本面验证（40分）：净资产收益率(ROE)是否优秀？营收总额是否具备规模效应（对隐形冠军可放宽体量要求，但需具备极高利润率）？净利润增速是否验证了涨价/放量逻辑？（根据你掌握的历史财报及行业当前景气度推演）。
- 需求与排产（20分）：订单是否饱满？是否处于宏观超级风口（如AI、通胀周期、设备更新等）？

第三步：综合裁决与严格格式输出
- 得分 ≥ 90：【S级 - 核心资产/赛道王者】（并标注具体赛道）
- 得分 75-89：【A级 - 强势关注】
- 得分 60-74：【B级 - 观察】
- 得分 < 60 或 属于【平庸废料】：【淘汰】

【极其重要：输出格式要求】
为了方便系统自动化落库，你必须在回答的开头使用如下固定格式输出结论，再进行详细分析：
【评级】: S级/A级/B级/淘汰
【分数】: 具体分数（0-100的整数）
【理由】: 一针见血的致命缺陷或上榜原因...

请根据你所掌握的最新市场数据及基本面情况，对以下股票进行评判：
股票代码：{code}，股票名称：{name}
【注：请调取你的内置金融知识库，结合其历史 ROE、营收体量、当前大宗商品价格趋势等进行深度推演。】
"""

    for code, name in new_recs:
        print(f"[stock_analysis] Analyzing {code} {name} ...")
        
        # 获取最新基本面数据
        fundamental_data = get_fundamental_data(code)
        print(f"[stock_analysis] Fetched fundamental data: {fundamental_data}")
        
        prompt = prompt_template.format(code=code, name=name)
        # 将基本面数据附带给大模型
        prompt += f"\n\n附加真实基本面数据参考：\n{fundamental_data}"
        
        print("==================================================")
        print(f"[{code} {name}] 待发送给首席选股官的 Prompt：\n")
        print(prompt)
        print("==================================================\n")
        
        # 将组装好的 Prompt 和待分析状态写入数据库，等待后续手动分析或其它调用处理
        save_analysis_result(report_date, code, name, "待分析", 0, prompt)
            
if __name__ == "__main__":
    d = datetime.now().strftime("%Y%m%d")
    test_path = f"\\vmware-host\Shared Folders\通达信新高日志\\十五以内{d}.txt"
    run_deep_analysis(test_path)
