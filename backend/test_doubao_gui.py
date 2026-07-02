import os
import time
import pyautogui as pag
import pyperclip
import pandas as pd
import pymysql
import re
from io import StringIO
from datetime import datetime, timedelta
import sys

# 添加 backend 目录到 sys.path
sys.path.append(os.path.dirname(__file__))

from quant.services.monitor_tdx import (
    _locate_center, _ensure_click, 
    IMG_DOUBAO1, IMG_DOUBAO2, IMG_DOUBAO3, IMG_DOUBAO3_5, IMG_DOUBAO4, IMG_DOUBAO4_5, IMG_DOUBAO5, IMG_DOUBAO5_5
)
from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

SCORING_STANDARD = """个股评分标准（最终定稿版）
一、终极判定：满足任一条件直接评为对应分数及评级，杜绝周期陷阱：
①【全球霸主】中国厂商全球市占≥30% 且拥有全球定价权；或全球市占≥25% + 海外收入≥30% + 毛利率处于行业前15%，直接评为 SS 级 100 分；
②【格局垄断】国内 CR3≥70% + 全球市占≥20% + 海外收入占比 > 30%，直接评为 SS 级 100 分；
③【超级成长】连续两季度营收增速≥40% + 毛利率≥35% + 机构持仓环比提升≥2pct，且扣非净利润同步增长（排除增收不增利），直接评为 S 级（90~99分）；若同时满足供应链满分、无扣分，可升级为 SS 级 100 分；
④【周期反转龙头】资源/制造类个股：库存≤历史20%分位 + 产品价格连续3个月环比上涨 + 行业CR3≥60%，直接评为 S 级（90~99分）；若同时具备全球垄断属性（全球市占≥30%），可升级为 SS 级 100 分。
二、红线淘汰：触发任一红线直接 0 分淘汰：
①财务造假 / 立案调查 / 非标审计意见 / 重大信披违规；
②被实施*ST、ST、退市风险警示，或净资产为负；
③连续2年扣非亏损 + 经营现金流持续为负 + 无明确业务拐点；
④大股东质押率≥90% + 公司存在逾期债务/流动性危机；
⑤近1年存在重大诉讼、核心资产被查封、实控人失联等重大经营风险。
三、常规评分（未直通、未淘汰，满分 100 分）：采用阶梯定值打分，完全去区间化，杜绝主观模糊，权重不变
1. 需求爆发（20分，阶梯定值，总分适配20分权重）
- 20分：行业年化增速≥30%，供需缺口持续扩大；
- 16分：行业年化增速20%~29%，需求稳定向上；
- 12分：行业年化增速10%~19%，行业成熟稳定；
- 8分：行业年化增速5%~9%，需求平稳无增长；
- 0分：行业年化增速<5%（含负增长）、市场饱和或处于衰退期。
2. 全球供给格局（25分，阶梯定值，总分适配25分权重）
- 25分：全球市占≥20%，具备行业话语权；
- 20分：全球市占15%~19% 或 国内CR3≥70%；
- 15分：全球市占10%~14% 或 国内行业龙头（市占≥15%）；
- 10分：国内行业中等份额（市占5%~14%），无全球市场地位；
- 0分：国内市占<5%，行业边缘小厂，无核心竞争力，无定价权。
3. 量价与盈利质量（20分，阶梯定值，总分适配20分权重）
- 20分：毛利率≥30% + ROE≥15% + 经营现金流/净利润≥0.8，盈利质量优异；
- 16分：毛利率25%~29% + ROE12%~14%，盈利较强；
- 12分：毛利率20%~24% + ROE8%~11%，盈利稳健；
- 8分：毛利率10%~19%，盈利水平一般，无明显波动；
- 0分：毛利率<10% 或 盈利波动巨大，盈利质量差。
4. 第二曲线 / 转型（15分，阶梯定值，总分适配15分权重）
- 15分：新业务已贡献≥15%营收，转型验证成功，增长潜力明确；
- 12分：新业务已贡献10%~14%营收，转型进展顺利；
- 9分：新业务处于投入期，逻辑通顺，有明确落地进展；
- 3分：转型动作缓慢，无清晰方向，进展不及预期；
- 0分：无第二曲线布局，主业持续萎缩，无转型意愿。
5. 管理层与护城河（20分，阶梯定值，总分适配20分权重）
- 20分：具备极强核心壁垒（技术/专利/资源/牌照等），管理层专业且稳定，无负面治理新闻；
- 16分：拥有明显竞争优势（客户壁垒/成本优势等），治理结构良好，偶有轻微治理问题；
- 12分：常规制造或服务类企业，无强核心壁垒，治理规范，无重大治理问题；
- 4分：公司治理一般，存在少量关联交易，管理层无频繁减持；
- 0分：公司治理较差，关联交易频繁，管理层减持频繁，无核心竞争力。
四、行业系数修正（修正后再进行后续评分，保证行业公平性；仅作用于常规评分（100分），供应链评分、周期调节不参与系数修正）
- 高端制造行业（含算力、半导体、光模块、CPO、华为产业链相关（核心配套、高端配套领域）、液冷、机器人、低空经济、半导体设备、高端机械、锂电设备、光伏设备、精密仪器、航空航天零部件等具备高壁垒、高成长属性的领域）：常规评分×1.0（不修正）；
- 普通制造行业（含常规机械、通用设备等无强核心壁垒的领域）：常规评分×0.98；
- 资源/周期行业：常规评分×0.95；
- 银行/公用事业/高速公路行业：常规评分×0.92；
- 传统轻工/纺织行业：常规评分×0.85。
五、供应链稳定性评分（修正后执行，满分10分，计入最终得分，保底0分，阶梯定值，总分适配10分补充权重）
供应链稳定性作为补充评分项，核心考核上下游保障能力，具体打分标准如下：
- 10分：上游核心材料自主可控（自主产能≥80%），无对外依赖；下游拥有3家及以上行业龙头客户，合作期限≥3年，客户集中度合理（前五大客户占比≤60%），需求稳定有保障；
- 7分：上游核心材料自主可控率60%~79%，少量依赖外部供应但有备选供应商；下游有稳定核心客户（2家及以上），合作关系良好，无重大客户依赖风险；
- 4分：上游核心材料自主可控率30%~59%，依赖单一或少数供应商，存在轻微供应风险；下游客户分散，有1家核心稳定客户，订单波动适中；
- 1分：上游核心材料自主可控率<30%，依赖单一或少数供应商，供应风险较高；下游无核心稳定客户，订单波动较大；
- 0分：上游核心材料完全依赖外部进口或单一供应商，供应稳定性极差；下游无稳定客户，订单持续性不足，存在断单风险。
六、周期位置硬调节（基于修正后、供应链评分后的得分调整）
仅针对周期类行业（资源/大宗/化工/制造/光伏/锂电/面板/航运）可参与±5分调节，其余非周期类行业（如银行、高速、公用事业、传统轻工纺织等）均按0分调整（即不加分、不扣分，不影响最终得分）；库存相关指标采用“主指标+代理指标”模式，解决数据获取难题：
① 加分（+5分，最终得分封顶100分）：主指标（库存≤历史20%分位）+ 产品价格连续2个月环比持平/上涨 + 行业产能利用率≥80%；若无行业库存数据，可用代理指标替代（存货周转天数较上季度显著下降≥10% 或 合同负债（预收款）较上季度激增≥30%）；
② 扣分（-5分，最终得分保底0分）：主指标（库存≥历史80%分位）+ 产品价格连续2个月环比下跌 + 行业CAPEX过高（产能过剩风险）；若无行业库存数据，可用代理指标替代（存货周转天数较上季度显著上升≥10% 或 合同负债（预收款）较上季度下降≥30%）。
七、最终评级（基于最终得分判定）
- SS级：100分（顶级全球霸主/超级黑马，完美级，长坡厚雪+核心壁垒无短板）；
- S级：90~99分（全球霸主/超级黑马，核心竞争力突出，允许轻微失分，贴合长坡厚雪、高爆发力定位）；
- A级（核心重仓）：≥80分（且<90分）；
- B级（重点观察）：65~79分；
- C级（谨慎跟踪）：50~64分；
- D级（淘汰）：<50分。
补充要求：所有打分需引用明确可查的量化数据（如市占率、增速、毛利率、存货周转天数等）作为依据，不得主观模糊判定；代理指标与主指标二选一即可，优先采用主指标。
请务必牢记以上《个股评分标准（最终定稿版）》中的评分规则，之后的股票评分严格按照这一套规则执行。
"""

def test_doubao():
    print("[Test] Starting Doubao GUI Interaction Test...", flush=True)
    d = datetime.now().strftime("%Y%m%d")
    actual_path = f"\\vmware-host\Shared Folders\通达信新高日志\\十五以内{d}.txt"
    
    # 确保文件存在，如果不存在则创建一个测试用的
    if not os.path.exists(actual_path):
        print(f"[Test] File {actual_path} not found. Creating a dummy file for testing.", flush=True)
        os.makedirs(os.path.dirname(actual_path), exist_ok=True)
        with open(actual_path, 'w', encoding='utf-8') as f:
            f.write("000001\t平安银行\t银行\n")
            f.write("600519\t贵州茅台\t白酒\n")

    print(f"[Test] Reading data from {actual_path}", flush=True)

    # 点击 doubao1.png
    if _ensure_click(IMG_DOUBAO1, retries=3, confidence=0.8, move_time=0.5):
        time.sleep(1.0)
        # 点击 doubao2.png
        if _ensure_click(IMG_DOUBAO2, retries=3, confidence=0.8, move_time=0.5):
            time.sleep(1.0)
            
            # 检查是否有 doubao3.png
            pos3 = _locate_center(IMG_DOUBAO3, confidence=0.8, timeout=5.0)
            if pos3:
                print("[Test] Found doubao3.png, looking for doubao3.5.png to focus input...", flush=True)
                
                # 寻找并点击 doubao3.5.png 以获取焦点
                if _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5):
                    print("[Test] Clicked doubao3.5.png, input box focused.", flush=True)
                    time.sleep(0.5)
                    
                    if os.path.exists(actual_path):
                        # 尝试用 gb18030（兼容 gbk/gb2312）读取，以防通达信导出的是 ANSI 编码
                        try:
                            with open(actual_path, 'r', encoding='utf-8', errors='strict') as f:
                                raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('9')]
                        except UnicodeDecodeError:
                            with open(actual_path, 'r', encoding='gb18030', errors='ignore') as f:
                                raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('9')]
                            
                        # 增加逻辑：从数据库读取一个月内已存在的股票并过滤
                        thirty_days_ago = (datetime.strptime(d, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
                        existing_codes = set()
                        try:
                            filter_conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
                            filter_cursor = filter_conn.cursor()
                            filter_cursor.execute("SELECT code FROM stock_deep_analysis WHERE report_date >= %s", (thirty_days_ago,))
                            existing_codes = {row[0] for row in filter_cursor.fetchall()}
                            filter_conn.close()
                        except Exception as filter_e:
                            print(f"[Test] Warning: Failed to query existing codes for filtering: {filter_e}", flush=True)
                            
                        lines = []
                        for line in raw_lines:
                            # 假设 line 格式类似: 600312 平高电气
                            code_match = re.search(r'\d{6}', line)
                            if not code_match:
                                continue  # 跳过表头或不含股票代码的行
                            if code_match.group() in existing_codes:
                                continue
                            lines.append(line)
                                
                        print(f"[Test] Read {len(raw_lines)} lines, after filtering 30-day existing codes, {len(lines)} lines remaining to process.", flush=True)
                        
                        if not lines:
                            print("[Test] The file is empty or all stocks are filtered out. Skipping Doubao interaction.", flush=True)
                            return
                        else:
                            batch_size = 5
                            db_txt_path = f"\\vmware-host\Shared Folders\通达信新高日志\\数据库{d}.txt"
                            
                            # 每次开始前先清空或新建文件
                            with open(db_txt_path, 'w', encoding='utf-8') as db_f:
                                db_f.write("")
                                
                            for i in range(0, len(lines), batch_size):
                                if i == 0 or i % 50 == 0:
                                    print(f"[Test] Sending SCORING_STANDARD before stock index {i}...", flush=True)
                                    std_ready = False
                                    while not std_ready:
                                        pyperclip.copy(SCORING_STANDARD)
                                        time.sleep(0.5)
                                        pag.hotkey('ctrl', 'v')
                                        time.sleep(1.0)
                                        pag.press('enter')
                                        
                                        print("[Test] Waiting for doubao4.5.png after sending standard (up to 3 mins)...", flush=True)
                                        std_wait_time = time.time()
                                        while time.time() - std_wait_time < 180.0:
                                            if _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=1.0, silent=True):
                                                std_ready = True
                                                break
                                            time.sleep(1.0)
                                            
                                        if not std_ready:
                                            print("[Test] Warning: doubao4.5.png not found within 3 mins, resending SCORING_STANDARD...", flush=True)
                                            _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5)
                                    
                                    print("[Test] doubao4.5.png found. Standard sent successfully.", flush=True)
                                    time.sleep(2.0)
                                    if _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5):
                                        print("[Test] Refocused input box for next batch.", flush=True)

                                batch_lines = lines[i:i + batch_size]
                                stock_info = "\n".join(batch_lines)
                                
                                msg_to_agent = f"搜索各个股票信息，信息要尽可能的全面，至少获取60篇及以上的资料，严格按《个股评分标准（最终定稿版）》全流程检索打分，输出固定格式（股票代码 股票简称 综合评级 综合评分 核心投资逻辑摘要） 的文本，文本不需要表头，且不输出其他任何内容 \n【股份信息】\n{stock_info}"
                                
                                result_ready = False
                                pos4_5 = None
                                
                                while not result_ready:
                                    pyperclip.copy(msg_to_agent)
                                    time.sleep(0.5)
                                    
                                    pag.hotkey('ctrl', 'v')
                                    time.sleep(1.0) # 等待粘贴完成
                                    pag.press('enter')
                                    print(f"[Test] Sent batch {i//batch_size + 1} to Doubao.", flush=True)
                                    
                                    # 等待 doubao4.5.png 出现（说明已经有结果）
                                    print("[Test] Waiting for doubao4.5.png (result ready) up to 3 mins...", flush=True)
                                    start_wait_time = time.time()
                                    max_wait_time = 180.0
                                    
                                    while time.time() - start_wait_time < max_wait_time:
                                        pos4_5 = _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=1.0, silent=True)
                                        
                                        if pos4_5:
                                            result_ready = True
                                            break
                                            
                                        time.sleep(1.0)
                                        
                                    if not result_ready:
                                        print("[Test] Warning: doubao4.5.png not found within 3 mins, resending batch...", flush=True)
                                        _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5)
                                    
                                print("[Test] Found doubao4.5.png, waiting 5 seconds before looking for doubao5.png...", flush=True)
                                time.sleep(5.0)
                                    
                                # 为了确保点击的是最新的复制按钮（在屏幕最下方），我们可以通过定位所有 doubao5.png
                                # 然后选取 Y 坐标最大的那个（即最靠下的那个）来点击。
                                try:
                                    # 增加循环等待寻找复制按钮的逻辑，最多等待 180 秒（3分钟）
                                    start_wait_copy_time = time.time()
                                    max_wait_copy_time = 180.0
                                    all_pos5 = []
                                    
                                    print("[Test] Looking for doubao5.png or doubao5.5.png (up to 3 minutes)...", flush=True)
                                    while time.time() - start_wait_copy_time < max_wait_copy_time:
                                        # 先尝试找所有的 doubao5.png，如果没找到则找 doubao5.5.png
                                        all_pos5 = list(pag.locateAllOnScreen(IMG_DOUBAO5, confidence=0.8, grayscale=True))
                                        if not all_pos5:
                                            all_pos5 = list(pag.locateAllOnScreen(IMG_DOUBAO5_5, confidence=0.8, grayscale=True))
                                            
                                        if all_pos5:
                                            break
                                            
                                        time.sleep(1.0)
                                        
                                    if all_pos5:
                                        # 根据 y 坐标排序，找到最下面的那个
                                        bottom_pos5 = sorted(all_pos5, key=lambda p: p.top, reverse=True)[0]
                                        center_x = bottom_pos5.left + bottom_pos5.width / 2
                                        center_y = bottom_pos5.top + bottom_pos5.height / 2
                                        
                                        pag.moveTo(center_x, center_y, 0.5)
                                        pag.click()
                                        print(f"[Test] Clicked the lowest doubao5.png at ({center_x}, {center_y})", flush=True)
                                        
                                        time.sleep(1.0)
                                        result_text = pyperclip.paste()
                                        
                                        # 粘贴追加到数据库文件
                                        with open(db_txt_path, 'a', encoding='utf-8') as db_f:
                                            db_f.write(result_text + "\n\n")
                                        print(f"[Test] Saved batch {i//batch_size + 1} result to {db_txt_path}", flush=True)
                                        
                                        # 为了确保能发送下一批次，重新寻找并点击输入框激活焦点
                                        print("[Test] Looking for doubao3.5.png to refocus for next batch...", flush=True)
                                        if _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5):
                                            print("[Test] Refocused input box for next batch.", flush=True)
                                        else:
                                            print("[Test] Warning: Failed to refocus input box.", flush=True)
                                            
                                    else:
                                        print("[Test] Error: Failed to find doubao5.png on screen", flush=True)
                                except Exception as e:
                                    print(f"[Test] Error locating/clicking doubao5.png: {e}", flush=True)
                                    
                        # 数据清洗：剔除豆包生成的无关闲聊与空行
                        print("[Test] Cleaning up irrelevant conversational text...", flush=True)
                        try:
                            with open(db_txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                raw_lines = f.readlines()
                            
                            cleaned_lines = []
                            for line in raw_lines:
                                stripped = line.strip()
                                if not stripped:
                                    continue
                                if '需要我把这' in stripped or '全流程打分明细吗' in stripped:
                                    continue
                                if stripped.startswith('好的') or '以下是' in stripped:
                                    continue
                                cleaned_lines.append(line)
                                
                            with open(db_txt_path, 'w', encoding='utf-8') as f:
                                f.writelines(cleaned_lines)
                            print(f"[Test] Cleaned {len(raw_lines) - len(cleaned_lines)} irrelevant lines.", flush=True)
                        except Exception as clean_e:
                            print(f"[Test] Error during data cleaning: {clean_e}", flush=True)
                            
                        # 最后落库到 quant_data.stock_deep_analysis
                        print("[Test] Importing results to database...", flush=True)
                        try:
                            conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
                            cursor = conn.cursor()
                            
                            with open(db_txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                            
                            # 提取 markdown csv 或直接按行处理
                            csv_blocks = re.findall(r'```(?:csv)?\n(.*?)\n```', content, re.DOTALL)
                            if not csv_blocks:
                                csv_blocks = [content]
                            
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
                                                print(f"[Test] Inserted {code} - {name} into DB", flush=True)
                                except Exception as inner_e:
                                    print(f"[Test] Error parsing CSV block: {inner_e}")
                                    
                            # 落库完成后，根据 score 统一调整当日的 result_type 评级
                            update_sql = """
                                UPDATE stock_deep_analysis
                                SET result_type = CASE
                                    WHEN score >= 100 THEN 'SS级'
                                    WHEN score >= 90 AND score <= 99 THEN 'S级'
                                    WHEN score >= 80 AND score <= 89 THEN 'A级'
                                    WHEN score >= 65 AND score <= 79 THEN 'B级'
                                    WHEN score >= 50 AND score <= 64 THEN 'C级'
                                    WHEN score > 0 AND score < 50 THEN 'D级'
                                    ELSE result_type
                                END
                                WHERE report_date = %s AND score > 0;
                            """
                            cursor.execute(update_sql, (d,))
                            
                            conn.commit()
                            conn.close()
                            print("[Test] DB import and result_type adjustment finished.", flush=True)
                        except Exception as db_e:
                            print(f"[Test] DB import error: {db_e}", flush=True)
                    else:
                        print(f"[Test] Actual path {actual_path} not found.", flush=True)
            else:
                print("[Test] Error: doubao3.png not found.", flush=True)
        else:
            print("[Test] Error: Failed to click doubao2.png", flush=True)
    else:
        print("[Test] Error: Failed to click doubao1.png", flush=True)

if __name__ == "__main__":
    test_doubao()
