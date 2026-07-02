import os
import re
from datetime import datetime, timedelta

# ================= 配置参数 =================
LOG_DIR = r"\\vmware-host\Shared Folders\通达信新高日志"
DAYS_AGO = 10          # 筛选最近多少天内的文档
TARGET_INDUSTRIES = ["配电设备"]   # 目标细分行业列表，例如 ["特高压", "半导体设备"]。如果有值，则只筛选这些行业；如果为空 []，则筛选所有行业
# ============================================

def parse_txt_file(file_path):
    """解析通达信导出的txt文件，返回 (代码, 名称, 细分行业) 列表"""
    recs = []
    try:
        # 尝试先用 utf-8 读取，如果失败则回退到 gb18030
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='gb18030', errors='ignore') as f:
                lines = f.readlines()
        
        if not lines:
            return []

        # 寻找表头行
        header_idx = -1
        for i, line in enumerate(lines[:10]):
            # 有时可能存在乱码，放宽表头识别的条件，或者通过制表符数量判断
            if "代码" in line or "名称" in line or "Code" in line or "Name" in line or "细分行业" in line or line.count('\t') >= 3:
                header_idx = i
                break
        
        if header_idx == -1:
            data_lines = lines
            code_idx, name_idx, ind_idx = 0, 1, 2
        else:
            header = lines[header_idx].split('\t')
            # 严格匹配表头字段
            code_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["代码", "证券代码", "Code"])), 0)
            name_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["名称", "证券名称", "Name"])), 1)
            ind_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["细分行业", "行业", "Industry"])), 2)
            data_lines = lines[header_idx+1:]

        # 解析每一行
        for line in data_lines:
            parts = line.split('\t')
            if len(parts) > max(code_idx, name_idx, ind_idx):
                code = parts[code_idx].strip()
                name = parts[name_idx].strip()
                industry = parts[ind_idx].strip() if ind_idx < len(parts) else ""
                
                # 去除引号
                code = code.replace('"', '').replace("'", "")
                name = name.replace('"', '').replace("'", "")
                industry = industry.replace('"', '').replace("'", "")
                
                # 补齐 6 位代码
                if code.isdigit() and len(code) < 6:
                    code = code.zfill(6)
                
                # 过滤无效行：没有代码、以9开头、包含非股票字符等
                if code and name and "代码" not in code and "数据来源" not in code and not code.startswith('9'):
                    # 确保提取出的行业字段不是乱码数字（比如 -0.16）
                    # 行业名称通常包含中文字符，如果纯数字或者包含负号，说明列索引找错了，丢弃该条数据
                    if re.match(r'^-?\d+(?:\.\d+)?$', industry):
                        continue
                    recs.append((code, name, industry)) 
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return recs

def analyze_industry_leaders():
    if not os.path.exists(LOG_DIR):
        print(f"日志目录不存在: {LOG_DIR}")
        return

    # 正则匹配形如 实时新高20260302.txt 的文件，并提取日期部分
    file_pattern = re.compile(r'^实时新高(\d{8})\.txt$')
    
    file_dates = [] # 存放 (日期字符串, 文件绝对路径)
    for filename in os.listdir(LOG_DIR):
        match = file_pattern.search(filename)
        if match:
            date_str = match.group(1)
            file_dates.append((date_str, os.path.join(LOG_DIR, filename)))
            
    if not file_dates:
        print(f"在 {LOG_DIR} 下未找到符合日期格式的日志文件。")
        return
        
    # 获取所有真实存在的独立日期，按降序（从新到旧）排列
    unique_dates = sorted(list(set([d for d, _ in file_dates])), reverse=True)
    # 取离当前最近的 DAYS_AGO 个日期
    target_dates = set(unique_dates[:DAYS_AGO])
    
    filtered_files = [(d, f) for d, f in file_dates if d in target_dates]
            
    if not filtered_files:
        print(f"最近 {DAYS_AGO} 个交易日内没有找到日志文件。")
        return
        
    # 按日期升序排序 (从最早的开始分析)
    filtered_files.sort(key=lambda x: x[0])
    
    print(f"共筛选出 {len(filtered_files)} 个文档进行分析")
    print(f"时间范围: {filtered_files[0][0]} -> {filtered_files[-1][0]}")
    if TARGET_INDUSTRIES:
        print(f"目标细分行业: {TARGET_INDUSTRIES}")
    print("=" * 60)
    
    # 记录每个行业首次出现新高的信息
    # 数据结构: { industry_name: {"date": date_str, "stocks": [(code, name), ...]} }
    industry_first_highs = {}
    
    # 记录个股在筛选范围内的出现次数
    industry_stock_counts = {}
    
    for date_str, filepath in filtered_files:
        recs = parse_txt_file(filepath)
        for code, name, industry in recs:
            if not industry:
                continue
                
            industry_clean = industry.strip()
            # 如果指定了目标行业列表，则进行模糊匹配
            if TARGET_INDUSTRIES:
                matched = False
                for target in TARGET_INDUSTRIES:
                    if target.strip() in industry_clean:
                        matched = True
                        break
                if not matched:
                    continue
                    
            # 统计出现次数
            if industry_clean not in industry_stock_counts:
                industry_stock_counts[industry_clean] = {}
            if code not in industry_stock_counts[industry_clean]:
                industry_stock_counts[industry_clean][code] = {"name": name, "count": 0}
            industry_stock_counts[industry_clean][code]["count"] += 1
                
            if industry_clean not in industry_first_highs:
                # 记录该行业首次创出新高的日期和股票
                industry_first_highs[industry_clean] = {
                    "date": date_str,
                    "stocks": []
                }
            
            # 如果当前文件的日期就是该行业首次出现的日期，则加入股票列表
            # （这样可以找出同一天、同一行业一起创新高的多个股票）
            if industry_first_highs[industry_clean]["date"] == date_str:
                stock_tuple = (code, name)
                if stock_tuple not in industry_first_highs[industry_clean]["stocks"]:
                    industry_first_highs[industry_clean]["stocks"].append(stock_tuple)
                    
    # 输出结果
    if not industry_first_highs:
        print("未找到符合条件的行业或个股。")
        return
        
    # ================= 增加个股评分查询 =================
    all_codes_set = set()
    for info in industry_first_highs.values():
        for code, name in info["stocks"]:
            all_codes_set.add(code)
    for counts in industry_stock_counts.values():
        for code in counts.keys():
            all_codes_set.add(code)
            
    all_codes = list(all_codes_set)
    db_info = {}
    if all_codes:
        try:
            import sys
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
            from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
            import pymysql
            
            conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            format_strings = ','.join(['%s'] * len(all_codes))
            cursor.execute(f"SELECT code, result_type, score FROM stock_deep_analysis WHERE code IN ({format_strings})", tuple(all_codes))
            for row in cursor.fetchall():
                if row['result_type'] != '淘汰':
                    db_info[row['code']] = {'result_type': row['result_type'], 'score': row['score']}
            conn.close()
        except Exception as e:
            print(f"查询数据库评分失败: {e}")
    # ====================================================
        
    # 按首次出现的日期进行排序，日期相同的按行业名称排序
    sorted_industries = sorted(industry_first_highs.items(), key=lambda x: (x[1]["date"], x[0]))
    
    for ind, info in sorted_industries:
        date_str = info["date"]
        formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
        
        # 格式化领涨个股列表，并附加评分信息
        stock_strs = []
        for code, name in info["stocks"]:
            base_str = f"{name}({code})"
            if code in db_info:
                score_info = db_info[code]
                base_str += f" [{score_info['result_type']}] {score_info['score']}分"
            stock_strs.append(base_str)
            
        stocks_str = "、".join(stock_strs)
        
        # 提取该板块中新高出现次数最多的个股
        freq_strs = []
        counts = industry_stock_counts.get(ind, {})
        if counts:
            max_count = max(c_info["count"] for c_info in counts.values())
            top_stocks = sorted([code for code, c_info in counts.items() if c_info["count"] == max_count])
            for code in top_stocks:
                name = counts[code]["name"]
                base_str = f"{name}({code}) {max_count}次"
                if code in db_info:
                    score_info = db_info[code]
                    base_str += f" [{score_info['result_type']}] {score_info['score']}分"
                freq_strs.append(base_str)
        freq_output = "、".join(freq_strs) if freq_strs else "无"
        
        print(f"【{ind}】")
        print(f"  最早创新高日期: {formatted_date}")
        print(f"  板块领涨先锋: {stocks_str}")
        print(f"  板块最活跃个股(新高次数最多): {freq_output}")
        print("-" * 40)
        
    # 全局最活跃个股统计 (在筛选行业中总体次数最多的Top 10)
    global_stock_counts = {}
    for ind, counts in industry_stock_counts.items():
        for code, c_info in counts.items():
            if code not in global_stock_counts:
                global_stock_counts[code] = {"name": c_info["name"], "count": 0, "industries": set()}
            global_stock_counts[code]["count"] += c_info["count"]
            global_stock_counts[code]["industries"].add(ind)
            
    sorted_global = sorted(global_stock_counts.items(), key=lambda x: x[1]["count"], reverse=True)
    if sorted_global:
        print("=" * 60)
        print(f"【筛选范围内最活跃个股 Top 10】(最近 {DAYS_AGO} 个交易日)")
        for code, info in sorted_global[:10]:
            name = info["name"]
            count = info["count"]
            inds = ",".join(info["industries"])
            base_str = f"{name}({code}) - 新高 {count} 次 (所属: {inds})"
            if code in db_info:
                score_info = db_info[code]
                base_str += f" [{score_info['result_type']}] {score_info['score']}分"
            print(f"  {base_str}")

if __name__ == "__main__":
    analyze_industry_leaders()
