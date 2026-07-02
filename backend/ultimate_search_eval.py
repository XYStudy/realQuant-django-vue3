import traceback
import sys
import re
import time
import urllib.request
import urllib.parse
import ssl
import random
import pymysql
sys.path.append('d:/traeProject/backend')
from quant.services.stock_analysis import get_fundamental_data

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "root"
DB_NAME = "quant_data"

def search_bing(query):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        q = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={q}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            html = response.read().decode('utf-8')
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', html)
            text = " ".join(snippets)
            text = re.sub(r'<[^>]+>', '', text)
            if len(text) > 10: return text
    except Exception as e:
        pass
    return ""

def search_sogou(query):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        q = urllib.parse.quote(query)
        url = f"https://www.sogou.com/web?query={q}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            html = response.read().decode('utf-8')
            snippets = re.findall(r'<div class="vrwrap"[^>]*>(.*?)</div>', html, re.DOTALL)
            text = " ".join(snippets)
            text = re.sub(r'<[^>]+>', '', text)
            if len(text) > 10: return text
    except Exception as e:
        pass
    return ""

def fetch_search_context(name):
    query = f"{name} 核心竞争优势 行业地位 市占率"
    # Randomize to prevent ban
    if random.random() > 0.5:
        context = search_bing(query)
        if not context: context = search_sogou(query)
    else:
        context = search_sogou(query)
        if not context: context = search_bing(query)
        
    if not context:
        context = "搜索无结果"
    return context

def extract_growth(text, keyword):
    match = re.search(rf'{keyword}:\s*(-?\d+\.?\d*)', text)
    if match:
        return float(match.group(1))
    return None

def evaluate_single_stock(code, name):
    try:
        fund_text = get_fundamental_data(code)
        
        search_text = fetch_search_context(name)
        time.sleep(0.5)
        
        rev_growth = extract_growth(fund_text, '营收同比') or 0.0
        profit_growth = extract_growth(fund_text, '净利润同比') or 0.0
        
        q1_growth = 0.0
        if '预告' in fund_text and '预增' in fund_text:
            nums = re.findall(r'增长:(-?\d+\.?\d*)', fund_text)
            if nums:
                q1_growth = max([float(n) for n in nums])
            else:
                q1_growth = 30.0
                
        actual_profit_growth = max(profit_growth, q1_growth)
        actual_rev_growth = rev_growth
        
        score = 0
        reason_parts = []
        
        is_global_leader = any(k in search_text for k in ['全球第一', '全球最大', '全球领先', '出海龙头', '全球市占率前'])
        is_domestic_leader = any(k in search_text for k in ['国内第一', '市占率第一', '国内最大', '龙头企业', '垄断', '隐形冠军'])
        is_hot_theme = any(k in search_text for k in ['算力', '半导体', '光模块', '黄金', '大宗', '出海', '铜', '铝', '华为', '液冷', '机器人', 'CPO', '低空经济'])

        if is_global_leader and actual_profit_growth > 10:
            return "S级", 95, f"【S级 (95分) - 全球霸主/出海龙头】Web搜索证实其全球地位领先，且利润增速为正({actual_profit_growth}%)，属核心资产。"
            
        domestic_score = 0
        if is_domestic_leader:
            domestic_score = 30
            reason_parts.append("Web搜证国内垄断/龙头(30/30)")
        elif is_hot_theme:
            domestic_score = 15
            reason_parts.append("热点赛道核心(15/30)")
        else:
            reason_parts.append("未搜证到核心壁垒(0/30)")
        score += domestic_score
        
        price_score = 0
        if actual_profit_growth > 50:
            price_score = 25
            reason_parts.append("业绩飙升验证量价逻辑(25/25)")
        elif actual_profit_growth > 20:
            price_score = 15
            reason_parts.append("进入加速期(15/25)")
        else:
            reason_parts.append("无涨价或放量红利(0/25)")
        score += price_score
        
        earnings_score = 0
        if actual_profit_growth > actual_rev_growth and actual_profit_growth > 0:
            earnings_score = 25
            reason_parts.append(f"净利增速({actual_profit_growth}%)>营收增速(25/25)")
        elif actual_profit_growth > 0:
            earnings_score = 10
            reason_parts.append(f"净利正增长但未超营收(10/25)")
        else:
            reason_parts.append("净利萎缩或负增长(0/25)")
        score += earnings_score
        
        theme_score = 0
        if is_hot_theme and actual_profit_growth > 20:
            theme_score = 20
            reason_parts.append("热点周期共振(20/20)")
        elif actual_profit_growth > 15:
            theme_score = 10
            reason_parts.append("有一定周期红利(10/20)")
        else:
            reason_parts.append("无显著风口(0/20)")
        score += theme_score
        
        if score >= 80:
            result_type = "A级"
            prefix = f"【A级 ({score}分) - 重点关注】"
        elif score >= 60:
            result_type = "B级"
            prefix = f"【B级 ({score}分) - 观察】"
        else:
            result_type = "淘汰"
            kill_shot = f"经Web搜证无核心护城河，且利润增速仅({actual_profit_growth}%)，确系平庸废料。"
            return "淘汰", score, f"【淘汰】{kill_shot}"
            
        detail = prefix + " | ".join(reason_parts)
        return result_type, score, detail
    except Exception as e:
        print(f"EVAL ERROR: {e}")
        traceback.print_exc()
        return "淘汰", 40, f"【淘汰】处理异常 {e}"

def run():
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("SELECT id, code, name FROM stock_deep_analysis WHERE result_type = '淘汰' AND report_date='20260413'")
        rows = cursor.fetchall()
        
        print(f"Starting Ultimate 'Search + Finance' Evaluation for {len(rows)} stocks...")
        
        updated = 0
        revived = 0
        for row in rows:
            db_id = row['id']
            code = row['code']
            name = row['name']
            
            print(f"Evaluating {name} ({code})...", end='', flush=True)
            res_type, score, detail = evaluate_single_stock(code, name)
            
            cursor.execute(
                "UPDATE stock_deep_analysis SET result_type=%s, score=%s, analysis_detail=%s WHERE id=%s",
                (res_type, score, detail, db_id)
            )
            conn.commit()
            
            if res_type != '淘汰':
                revived += 1
                print(f" REVIVED -> {res_type} ({score})")
            else:
                print(" Eliminated.")
                
            updated += 1
            
        conn.close()
        print(f"\nUltimate evaluation completed. Total processed: {updated}, Revived via Search: {revived}.")
    except Exception as e:
        print(f"RUN ERROR: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    run()