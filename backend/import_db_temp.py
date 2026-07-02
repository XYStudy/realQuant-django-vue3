import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import pymysql
import pandas as pd
from io import StringIO
import re
from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

db_txt_path = r'\\vmware-host\Shared Folders\通达信新高日志\数据库20260422.txt'
d = '20260422'

if not os.path.exists(db_txt_path):
    print(f'File {db_txt_path} not found.')
    sys.exit(1)

print('Importing results to database...')
try:
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
    cursor = conn.cursor()
    
    with open(db_txt_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    # 提取 markdown csv 或直接按行处理
    csv_blocks = re.findall(r'```(?:csv)?\n(.*?)\n```', content, re.DOTALL)
    if not csv_blocks:
        csv_blocks = [content]
    
    total_inserted = 0
    for block in csv_blocks:
        try:
            # 将多个表头进行清洗，或者直接交给 pandas，如果 pandas 报错则按行解析
            lines_in_block = [line for line in block.strip().split('\n') if line.strip() and not line.startswith('---')]
            # 如果含有多个包含“代码”的表头，过滤掉除第一行之外的表头
            cleaned_lines = []
            header_found = False
            for line in lines_in_block:
                if '代码' in line and '名称' in line:
                    if not header_found:
                        cleaned_lines.append(line)
                        header_found = True
                else:
                    cleaned_lines.append(line)
                    
            if cleaned_lines:
                # 如果清洗后没有有效的表头，我们为其添加表头
                if not header_found:
                    # 检查是否是用空格分隔的格式（如：600312 平高电气 A级 82 特高压GIS龙头...）
                    is_space_separated = False
                    if len(cleaned_lines) > 0 and ' ' in cleaned_lines[0]:
                        parts = [p for p in cleaned_lines[0].split(' ') if p.strip()]
                        # 看看分成了几个部分，如果大致符合 5 个部分（代码 名称 评级 分数 原因）
                        if len(parts) >= 5 and re.match(r'\d{6}', parts[0]):
                            is_space_separated = True

                    if is_space_separated:
                        # 对于空格分隔的，手动解析每一行，避免 pandas 错误地将后面的空格也切分开
                        parsed_lines = ["代码\t名称\t评级\t分数\t理由"]
                        for line in cleaned_lines:
                            parts = [p for p in line.strip().split(' ') if p.strip()]
                            if len(parts) >= 5:
                                code = parts[0]
                                name = parts[1]
                                rating = parts[2]
                                score = parts[3]
                                reason = " ".join(parts[4:])
                                # 用制表符重新拼装以防逗号在理由中引起混淆
                                parsed_lines.append(f"{code}\t{name}\t{rating}\t{score}\t{reason}")
                            else:
                                parsed_lines.append(line)
                        cleaned_lines = parsed_lines
                        # 强制指定用制表符解析
                        df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                    else:
                        cleaned_lines.insert(0, "代码,名称,评级,分数,理由")
                        # 尝试用逗号替换可能的其他分隔符（如果有的话，但通常我们要求是csv）
                        try:
                            df = pd.read_csv(StringIO('\n'.join(cleaned_lines)))
                        except Exception:
                            # 如果逗号解析失败，尝试用空格或制表符作为分隔符
                            try:
                                df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                            except Exception:
                                df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep=r'\s+')
                else:
                    # 尝试用逗号替换可能的其他分隔符（如果有的话，但通常我们要求是csv）
                    try:
                        df = pd.read_csv(StringIO('\n'.join(cleaned_lines)))
                    except Exception:
                        # 如果逗号解析失败，尝试用空格或制表符作为分隔符
                        try:
                            df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                        except Exception:
                            df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep=r'\s+')
                            
                # print("解析出的表头和前几行数据：")
                # print(df.head())
                    
                cols = list(df.columns)
                code_col = next((c for c in cols if '代码' in c), None)
                name_col = next((c for c in cols if '名称' in c or '简称' in c), None)
                score_col = next((c for c in cols if '分' in c), None)
                type_col = next((c for c in cols if '评级' in c or '结果' in c or '类型' in c), None)
                detail_col = next((c for c in cols if '理由' in c or '分析' in c or '详情' in c or '简评' in c or '摘要' in c or '原因' in c), None)
                
                if code_col:
                    for _, row in df.iterrows():
                        code = str(row[code_col]).strip()
                        code = code.replace("'", "").replace('"', '')
                        code_match = re.search(r'\d{6}', code)
                        if code_match:
                            code = code_match.group()
                        else:
                            continue
                            
                        if not code or code == 'nan': continue
                        
                        name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ''
                        score = 0
                        if score_col and pd.notna(row[score_col]):
                            try:
                                score_str = str(row[score_col]).replace('分','').strip()
                                score_match = re.search(r'\d+', score_str)
                                if score_match:
                                    score = int(score_match.group())
                            except:
                                pass
                        
                        result_type = str(row[type_col]).strip() if type_col and pd.notna(row[type_col]) else ''
                        detail = str(row[detail_col]).strip() if detail_col and pd.notna(row[detail_col]) else ''
                        
                        # 特殊容错：如果解析出的名称为空或者其他字段异常，但是行原始数据其实很长，说明 pandas 列没对齐
                        # 我们之前的手动空格解析已经尽力将它分为5列，所以对于空格分隔模式，这里的解析通常能对齐。
                        
                        # 为了强制覆盖空内容，即使以前有了记录，如果有新的有效详情，也更新进去
                        sql = '''
                            INSERT INTO stock_deep_analysis (report_date, code, name, result_type, score, analysis_detail)
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                                name = IF(VALUES(name) != '', VALUES(name), name),
                                result_type = IF(VALUES(result_type) != '', VALUES(result_type), result_type),
                                score = IF(VALUES(score) > 0, VALUES(score), score),
                                analysis_detail = IF(VALUES(analysis_detail) != '', VALUES(analysis_detail), analysis_detail)
                        '''
                        cursor.execute(sql, (d, code, name, result_type, score, detail))
                        total_inserted += 1
                        print(f'Inserted {code} - {name} into DB')
        except Exception as inner_e:
            print(f'Error parsing CSV block: {inner_e}')
            
    conn.commit()
    conn.close()
    print(f'DB import finished. Total inserted: {total_inserted}')
except Exception as db_e:
    print(f'DB import error: {db_e}')