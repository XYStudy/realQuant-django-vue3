import sys
import re
import pymysql
import json
sys.path.append('d:/traeProject/backend')
from quant.services.stock_analysis import get_fundamental_data

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "root"
DB_NAME = "quant_data"

# 已知的超级龙头库 (S级免检直通车)
# Global market share >= 50% AND pricing power
TIER_1_KNOWLEDGE = {
    '宁德时代': '全球动力电池霸主，市占率超36%（非中国区超50%），绝对定价权。',
    '中国巨石': '全球最大玻纤企业，产能占全球超20%（具备全球定价权）。',
    '中际旭创': '全球光模块市占率第一（超50%的高端份额），垄断AI核心光互联。',
    '福晶科技': '非线性光学晶体全球隐形冠军，市占率极高。',
    '中瓷电子': '高端光通信陶瓷封装双寡头之一。',
    '大金重工': '海工单桩欧洲市占率超30%，出海第一梯队。'
}

def extract_growth(text, keyword):
    """提取净利润或营收同比增速"""
    match = re.search(rf'{keyword}:\s*(-?\d+\.?\d*)', text)
    if match:
        return float(match.group(1))
    return None

def extract_q1_forecast(text):
    if '预告' in text and '预增' in text:
        nums = re.findall(r'增长:(-?\d+\.?\d*)', text)
        if nums:
            return max([float(n) for n in nums])
        return 30.0 # 保底预增
    return None

def evaluate_single_stock(code, name):
    # Tier 1 Filter
    if name in TIER_1_KNOWLEDGE:
        return "S级", 100, f"【S级 (100分) - 国产主导全球霸主】{TIER_1_KNOWLEDGE[name]}"
        
    # Get Real Financials
    fund_text = get_fundamental_data(code)
    
    # Defaults
    score = 0
    reason_parts = []
    
    # Parse Financials
    rev_growth = extract_growth(fund_text, '营收同比')
    profit_growth = extract_growth(fund_text, '净利润同比')
    q1_growth = extract_q1_forecast(fund_text)
    
    # Use Q1 if available and higher, else use annual profit growth
    actual_profit_growth = profit_growth if profit_growth is not None else 0.0
    if q1_growth is not None:
        actual_profit_growth = max(actual_profit_growth, q1_growth)
    actual_rev_growth = rev_growth if rev_growth is not None else 0.0
    
    # 1. Domestic Monopoly (30 pts)
    domestic_score = 0
    if any(k in name for k in ['龙头', '重工', '通信', '精机', '科技', '精密', '股份']) and actual_profit_growth > 30:
        domestic_score = 15
        reason_parts.append("国内份额领先潜力(15/30)")
    elif actual_profit_growth > 60:
        domestic_score = 20
        reason_parts.append("细分赛道强势地位(20/30)")
    else:
        reason_parts.append("未证明国内垄断(0/30)")
        
    score += domestic_score
    
    # 2. Product Price Surge (25 pts)
    price_score = 0
    if actual_profit_growth > 50:
        price_score = 25
        reason_parts.append("业绩飙升验证量价齐升(25/25)")
    elif actual_profit_growth > 20:
        price_score = 15
        reason_parts.append("进入成长加速期(15/25)")
    else:
        reason_parts.append("无显著涨价放量红利(0/25)")
    score += price_score
    
    # 3. Earnings Validation (25 pts)
    earnings_score = 0
    if actual_profit_growth > actual_rev_growth and actual_profit_growth > 0:
        earnings_score = 25
        reason_parts.append(f"净利增速({actual_profit_growth}%)>营收增速({actual_rev_growth}%)(25/25)")
    elif actual_profit_growth > 0:
        earnings_score = 10
        reason_parts.append(f"净利正增长但未超营收({actual_profit_growth}%)(10/25)")
    else:
        reason_parts.append(f"净利萎缩或为负(0/25)")
    score += earnings_score
    
    # 4. Demand & Theme (20 pts)
    theme_score = 0
    theme_score += 20 if actual_profit_growth > 40 else (10 if actual_profit_growth > 15 else 0)
    score += theme_score
    reason_parts.append(f"需求景气度附加分({theme_score}/20)")
    
    # Final Output formatting based on Custom Instructions
    if score >= 80:
        result_type = "A级"
        prefix = f"【A级 ({score}分) - 重点关注】"
    elif score >= 60:
        result_type = "B级"
        prefix = f"【B级 ({score}分) - 观察】"
    else:
        result_type = "淘汰"
        # One-line kill-shot reason
        kill_shot = f"净利润增速仅为({actual_profit_growth}%)，护城河极浅，平庸废料毫无全球霸主潜质。"
        return "淘汰", score, f"【淘汰】{kill_shot}"
        
    detail = prefix + " | ".join(reason_parts)
    return result_type, score, detail

def run():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    
    cursor.execute("SELECT id, code, name FROM stock_deep_analysis WHERE result_type = '淘汰' AND report_date='20260413'")
    rows = cursor.fetchall()
    
    print(f"Starting strict re-evaluation for {len(rows)} eliminated stocks...")
    
    updated = 0
    for row in rows:
        db_id = row['id']
        code = row['code']
        name = row['name']
        
        res_type, score, detail = evaluate_single_stock(code, name)
        
        cursor.execute(
            "UPDATE stock_deep_analysis SET result_type=%s, score=%s, analysis_detail=%s WHERE id=%s",
            (res_type, score, detail, db_id)
        )
        updated += 1
        if updated % 20 == 0:
            print(f"Processed {updated}/{len(rows)}...")
            
    conn.commit()
    conn.close()
    print(f"Strict evaluation completed for {updated} stocks.")

if __name__ == '__main__':
    run()