import sys
sys.path.append('d:/traeProject/backend')
from quant.services.stock_analysis import get_fundamental_data
import pymysql
import re

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "root"
DB_NAME = "quant_data"

def extract_numbers(text):
    if text == "未知" or not text:
        return 0.0
    try:
        nums = re.findall(r'-?\d+\.?\d*', text)
        if nums:
            return float(nums[0])
    except:
        pass
    return 0.0

def reevaluate_stock(code, name, current_result):
    fund_text = get_fundamental_data(code)
    if "暂无最新" in fund_text:
        return None  # 无数据不改
        
    # 解析文本中的核心数据
    roe = 0.0
    profit_growth = 0.0
    q1_forecast_growth = 0.0
    is_yuzeng = "预增" in fund_text
    
    lines = fund_text.split('\n')
    for line in lines:
        if 'ROE' in line:
            match_roe = re.search(r'ROE:\s*(-?\d+\.?\d*)', line)
            if match_roe:
                roe = float(match_roe.group(1))
            match_pg = re.search(r'净利润同比:\s*(-?\d+\.?\d*)', line)
            if match_pg:
                profit_growth = float(match_pg.group(1))
        if '预告' in line and '预增' in line:
            # 简单提点数字，只要预增且提及大于30%的
            nums = re.findall(r'增长:(-?\d+\.?\d*)', line)
            if nums:
                q1_forecast_growth = max([float(n) for n in nums])
            else:
                q1_forecast_growth = 30.0 # 保底

    max_growth = max(profit_growth, q1_forecast_growth)
    
    # 私募首席二级漏斗：业绩硬逻辑修正
    if roe >= 20.0 or max_growth >= 50.0:
        reason = f"【S级 (95分) - 业绩反转/龙头爆发】ROE达{roe}%，净利润增速强劲(最高{max_growth}%)，属绝对核心资产，绝不错杀！"
        return "S级", 95, reason
    elif roe >= 15.0 or max_growth >= 30.0:
        reason = f"【A级 (85分) - 重点关注】ROE稳健({roe}%)或增速亮眼({max_growth}%)，业绩面支撑强，重点跟踪。"
        return "A级", 85, reason
    elif roe >= 10.0 and max_growth >= 10.0:
        reason = f"【B级 (75分) - 观察】基本面良好(ROE:{roe}%, 增速:{max_growth}%)，具备防守反击属性。"
        return "B级", 75, reason
        
    return None

def run():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    # 选出被淘汰的票进行重评
    cursor.execute("SELECT id, code, name, result_type FROM stock_deep_analysis WHERE result_type = '淘汰' AND report_date='20260413'")
    rows = cursor.fetchall()
    
    print(f"Checking {len(rows)} eliminated stocks for fundamental revival...")
    
    revived_count = 0
    for row in rows:
        db_id = row['id']
        code = row['code']
        name = row['name']
        
        new_eval = reevaluate_stock(code, name, row['result_type'])
        if new_eval:
            result_type, score, reason = new_eval
            cursor.execute(
                "UPDATE stock_deep_analysis SET result_type=%s, score=%s, analysis_detail=%s WHERE id=%s",
                (result_type, score, reason, db_id)
            )
            print(f"Revived {name} ({code}) -> {result_type} ({score})")
            revived_count += 1
            
    conn.commit()
    conn.close()
    print(f"Successfully revived {revived_count} stocks with strong fundamentals.")

if __name__ == '__main__':
    run()