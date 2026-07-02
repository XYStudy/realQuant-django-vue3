import os
import time
from datetime import datetime, timedelta
import pyautogui as pag
import pandas as pd
import argparse
from io import StringIO
import pyperclip
import pymysql
import re
try:
    from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    pass

try:
    from quant.services.auto_analyzer import send_wechat_message
    from quant.services.analyze_new_high import get_today_advice_msg, get_market_advice
except Exception:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from quant.services.auto_analyzer import send_wechat_message
    from quant.services.analyze_new_high import get_today_advice_msg, get_market_advice

IMAGE_DIR = os.path.join(os.path.dirname(__file__), "monitor_images")
IMG_TDX = os.path.join(IMAGE_DIR, "tdx.png")
IMG_OPTIONS = os.path.join(IMAGE_DIR, "options.png")
IMG_OPTIONS2 = os.path.join(IMAGE_DIR, "options2.png")
IMG_OPTIONS3 = os.path.join(IMAGE_DIR, "options3.png")
IMG_BANKUAI = os.path.join(IMAGE_DIR, "bankuai.png")
IMG_BANKUAI2 = os.path.join(IMAGE_DIR, "bankuai2.png")
IMG_TAB3 = os.path.join(IMAGE_DIR, "tab3.png")
IMG_TAB4 = os.path.join(IMAGE_DIR, "tab4.png")
IMG_TAB5 = os.path.join(IMAGE_DIR, "tab5.png")
IMG_TAB6 = os.path.join(IMAGE_DIR, "tab6.png")
IMG_REFRESH_BTN = os.path.join(IMAGE_DIR, "refreshBtn.png")
IMG_REFRESH_BTN2 = os.path.join(IMAGE_DIR, "refreshBtn2.png")
IMG_AUTOTIP = os.path.join(IMAGE_DIR, "autoTip.png")
IMG_EXPORT_BTN = os.path.join(IMAGE_DIR, "exportBtn.png")
IMG_EXPORT_DO = os.path.join(IMAGE_DIR, "exportDo.png")
IMG_CANCEL_BTN = os.path.join(IMAGE_DIR, "cancleBtn.png")
IMG_CANCEL_BTN2 = os.path.join(IMAGE_DIR, "cancleBtn2.png")
IMG_EXPORT_ALL = os.path.join(IMAGE_DIR, "exportAll.png")
IMG_FORMAT = os.path.join(IMAGE_DIR, "format.png")
IMG_REFRESH = os.path.join(IMAGE_DIR, "refresh.png")
IMG_LEFT_TAB = os.path.join(IMAGE_DIR, "leftTab.png")
IMG_MARKET = os.path.join(IMAGE_DIR, "market.png")
IMG_MARKET2 = os.path.join(IMAGE_DIR, "market2.png")
IMG_CODE = os.path.join(IMAGE_DIR, "code.png")
IMG_AT = os.path.join(IMAGE_DIR, "@.png")
IMG_ROLE = os.path.join(IMAGE_DIR, "role.png")
IMG_TRAE = os.path.join(IMAGE_DIR, "trae.png")
IMG_DOUBAO1 = os.path.join(IMAGE_DIR, "doubao1.png")
IMG_DOUBAO2_1 = os.path.join(IMAGE_DIR, "doubao2.1.png")
IMG_DOUBAO3 = os.path.join(IMAGE_DIR, "doubao3.png")
IMG_DOUBAO3_5 = os.path.join(IMAGE_DIR, "doubao3.5.png")
IMG_DOUBAO3_6 = os.path.join(IMAGE_DIR, "doubao3.6.png")
IMG_DOUBAO3_7 = os.path.join(IMAGE_DIR, "doubao3.7.png")
IMG_DOUBAO4 = os.path.join(IMAGE_DIR, "doubao4.png")
IMG_DOUBAO4_5 = os.path.join(IMAGE_DIR, "doubao4.5.png")
IMG_DOUBAO4_6 = os.path.join(IMAGE_DIR, "doubao4.6.png")
IMG_DOUBAO5 = os.path.join(IMAGE_DIR, "doubao5.png")
IMG_DOUBAO5_5 = os.path.join(IMAGE_DIR, "doubao5.5.png")

pag.FAILSAFE = True
pag.PAUSE = 0.2

baseline_date = None
baseline_codes = set()
afternoon_task_done_date = None

# ================= 时间配置区 =================
# 开始主流程前，至少等待到该时间点再运行。
MARKET_START_TIME = "09:25"

# 每天这些时间点发送最近 10 个交易日“实时新高”家数趋势分析。
NEW_HIGH_ANALYSIS_TIMES = ["08:00", "14:40"]
# 每个时间点后的有效触发窗口，避免因为启动略晚错过发送。
NEW_HIGH_ANALYSIS_WINDOW_MINUTES = 30
# 统计最近多少个交易日的“实时新高”文件。
MORNING_NEW_HIGH_ANALYSIS_DAYS = 10

# 每天这些整点会尝试发送一次“今日操作建议”。
ADVICE_HOURS = [10, 11, 13, 14]
# 整点后的有效触发窗口，超过这个分钟数就不再补发。
ADVICE_TRIGGER_WINDOW_MINUTES = 15

# 起爆点任务时间：到点后导出 `tab5`，并发送“起爆点”消息。
QBD_TASK_TIMES = ["09:45", "10:00", "10:15", "10:30", "11:00", "11:15", "13:30", "14:00", "14:30"]
# ETF 任务时间：到点后导出 `tab6`，并发送“距离新高5%以内ETF”消息。
ETF_TASK_TIMES = ["10:00", "11:00", "13:30", "14:30"]
# 如果脚本重启后发现已经超过任务时间这么多分钟，则跳过该时间点，避免补跑过期任务。
SPECIAL_TASK_EXPIRE_MINUTES = 10

# 到了这个小时后，切换为盘后“十五以内”逻辑。
AFTERNOON_START_HOUR = 15
# 当天盘后逻辑已执行完成后，每轮休眠秒数，避免空转。
AFTERNOON_DONE_SLEEP_SECONDS = 60

# ================= 调试开关：是否立即强制执行打分（忽略 15:00 时间检查） =================
# True  : 不等 15:00，启动即进入打分流程（用于测试）
# False : 正常按时间判断（默认）
FORCE_SCORING_NOW = False

SCORING_MODE = "new" # "old" ，改为 "new" 仅跑新标准，改为 "serial" 则串行执行

# VMware 共享目录：通达信导出文件和中间结果统一写到这里。
VMWARE_SHARED_LOG_DIR = r"\\vmware-host\Shared Folders\通达信新高日志"

# 记录上次发送操作建议的时间戳，避免重复发送
last_advice_sent_time = None
new_high_analysis_sent_keys = set()

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

# ================= 评分模式配置 =================
# "old"    : 仅运行老评分标准（SCORING_STANDARD → stock_deep_analysis）
# "new"    : 仅运行新评分标准（SCORING_STANDARD_V2 → stock_deep_analysis_v2）
# "serial" : 先运行老标准，结束后再运行新标准


SCORING_STANDARD_V2 = """个股超级龙头+泡沫+翻倍股综合评分标准（V2版）
请对每只股票按以下五大部分进行评分，并输出每部分的得分小计与总分，最终给出综合评级。

第一部分：超级龙头判断法（满分100分）
一、高确定需求（20分，每条5分）
1. 是否刚需不可替代？拿掉产品下游终端就做不出来 → 加分。
2. 下游客户是不是行业龙头？大客户集中（巨头/头部大厂）> 散户、小厂商分散订单。
3. 订单能见度高不高？交付周期3个月以上、订单排满 → 确定性强；临时小单、即时拿货 → 弱。
4. 技术路线会不会被颠覆？未来2-3年没有新路线替代现有产品 → 高确定；技术迭代快、路线摇摆 → 低确定。

二、受限供给（22分）
1. 技术/工艺壁垒（最难突破）：配方、精密加工、良率控制需要多年积累，新玩家学不会、老玩家扩产也提不上量。（4分）
2. 产能建设周期长：建厂、装机、调试、客户认证全流程要2-5年，不是几个月就能扩产。（4分）
3. 政策/配额管控：行业实行产能配额、环保限制、进出口管制，明文不让随便扩产。（3分）
4. 核心设备/原料卡脖子：被卡脖子减分，反卡别人脖子另加2分。（3-5分）
5. 行业寡头格局：全球就2-3家头部企业，同行不愿激进扩产，主动维持紧平衡。例：碳化硅衬底、高端谐波减速器。（3分）
6. 客户认证壁垒：就算你造出产品，下游巨头（英伟达、特斯拉、台积电）认证要数年，产能有了也进不了供应链，等同于有效供给不变。（3分）

三、低关注度（20分）
机构覆盖评价越少分数越高、散户越不懂分数越高、估值越低分数越高。

四、高价值捕获（20分）
越有定价权分数越高、毛利越高分数越高、拿走产业链大部分利润越多分数越高。

五、强催化剂（20分，每条4分）
1) 巨头订单/白名单（最强，直接锁死未来）
2) 技术突破+量产（从0→1，壁垒兑现）
3) 政策/补贴（直接给钱+锁产能）
4) 业绩爆发+指引上调（最硬兑现）
5) 行业拐点+稀缺加剧（涨价+抢货）

第二部分：泡沫判断标准（满分100分，得分越高泡沫越大）
一、核心逻辑：瓶颈失效（最关键，权重最高，共3条）
1. 核心卡脖子环节出现新产能落地/在建产能密集公示，短期供给不再刚性。（7分）
2. 第二/第三家竞争对手完成认证、批量供货，寡头格局被打破。（7分）
3. 出现替代技术、替代材料、替代工艺，原有技术路线壁垒弱化。（6分）

二、供需关系：景气反转（共3条）
4. 下游头部大厂（云厂商/终端/晶圆厂）资本开支增速下调、订单指引保守。（7分）
5. 产品交付周期、排产周期明显缩短，从"抢货"变为"正常供货"。（7分）
6. 核心产品价格止涨、松动，或出现降价促销，企业定价权下降。（6分）

三、业绩&估值：预期完全透支（共3条）
7. TTM/动态PE、PS、EV/EBITDA 创出公司历史/行业历史极值。（7分）
8. 市场估值已经计入未来2-3年最乐观业绩预期，无超额预期差。（7分）
9. 业绩增速见顶，环比开始走弱，高增长难以持续。（6分）

四、市场情绪：全民狂热（共3条）
10. 全网刷屏，普通散户、短线资金、纯题材玩家集中涌入，人人都在聊这只票/赛道。（7分）
11. 同赛道低位蹭概念小票集体暴涨，主线开始泛化、炒作发散。（7分）
12. 券商研报集体唱多、统一上调目标价，出现"长期牛市、永不停歇"等极端叙事。（6分）

五、资金行为：主力撤退（共3条）
13. 大股东、高管、原始股东密集减持、大额解禁落地。（7分）
14. 专业机构（公募/私募/北向）悄悄减仓，龙虎榜、持仓数据持续流出。（7分）
15. 场内融资杠杆、场外配资达到阶段峰值，杠杆资金开始松动。（6分）

第三部分：综合条件打分（满分130分）
1. 老业务留现金流，切新0→1赛道。（10分）
2. 自己做行业标准，不当跟风打工者，是隐形冠军。（5分）
3. 绑定全球顶级大客户锁生态。（5分）
4. 高研发+逆势扩产筑壁垒。（5分）
5. 从卖单品升级做整套平台方案。（5分）
6. 周期低谷逆势并购卡位或自研扩产。（5分）
7. 上游下游产业链控制力强。（5分）
8. 毛利率高吗，在行业地位，利润和销售增幅大吗。（5分）
9. 上涨逻辑还在吗？属周期上升景气股吗？利好消化完了吗？还有新利好吗？（10分）
10. 有哪些风险？风险大减分，风险小不减分。（5分）
11. 公司的产品的整个行业扩产的速度是慢于还是快于整个行业需求增长速度？慢于需求增长可以得满分。（5分）
12. 设备和原料有无卡脖子情况？无得满分。（5分）
13. 现金流，弹性，三年折价估值低得满分。（5分）
14. 股价三天内上涨的幅度远低于业绩暴增速度。业绩暴增速度等于毛利率×销售增长率×利润增长率，暴增速度越大越好。（10分）
15. 股东数近几个月减少，机构持仓占比大，共识快速形成。（5分）
16. 该股票行业缺口度非常高，超级硬逻辑世界级垄断。（5分）
17. 未来三年预估利润，2028年市盈率能下降吗，2028年市盈率较低。（10分）
18. 有翻番潜力。（5分）
19. 要求每股收益连续至少一到二个季度加速增长，增速最好超过25%，越高越好。年度EPS增长率至少达到25%到50%。特别强调"加速"的概念，比如上季度增长30%、这季度增长50%，这种加速趋势比单纯的高增速更重要。此外要求近期季度EPS创历史新高，并且盈利惊喜（超预期）是加分项。（10分）
20. 在最近一周内率先大幅上涨，且接近或创历史新高。（10分）

第四部分：股价上涨逻辑分类（判断属于以下哪一类）
1. 像沃格光电：目前还亏损，远期有科幻想象力（最弱题材）
2. 像江海股份：利润无连续加速，但盈利，纯题材炒作，但有0→1创新，但创新销售占比少。
3. 像风华高科：单季小幅回暖，周期涨价题材，也是题材炒作。但有0→1创新，但创新销售占比多一点。
4. 像铜冠铜箔：逐季加速满分，业绩兑现，盈利质量一般，泡沫较大，估值偏高，但有0→1创新，但创新销售占比更大，且落地。
5. 像商络电子：逐季加速满分，盈利质量极强，泡沫最少，估值很低，但有0→1创新，但创新销售占比非常大，且业绩落地。
6. 像中际旭创：逐季加速满分，盈利扎实，市盈率合理，泡沫最小（稳健核心重仓），但有0→1创新，但创新销售占比非常大，完全落地，强垄断。

第五部分：翻倍股可能性打分（满分100分，每项20分）
1. 供给端：若是供应端的竞争对手占比高又是永久不可逆出清和停产，打20分；如中船特气的竞争对手日本两家企业直接永久关停全部高纯六氟化钨产能，占全球流通高端产能55%，再也不会复产；若是暂时停产和占比产能低则降分数。
2. 供应端承接比例：如全球仅中船特气有匹配晶圆厂的7N高纯产能，独一份缺口承接者则打20分；若有两家承接则加10分。
3. 下游需求端：是AI芯片刚需打20分，全球无替代满分；如中船特气是HBM、3D NAND先进制程刻蚀必须用六氟化钨，没有替代品则打满分。
4. 现货价格上涨：若现货价格直接上涨翻2倍以上，订单排到2027年，直接打满分。
5. 市值基数：极低在300亿以下打满分20分，300亿到500亿打15分，500到1000亿打10分，1000亿以上打5分。

总分 = 第一部分(100) + 第三部分(130) + 第五部分(100) - 第二部分(100) = 综合得分
综合评级标准：
- SS级：综合得分≥350分
- S级：300~349分
- A级：250~299分
- B级：200~249分
- C级：150~199分
- D级：<150分

输出固定格式（股票代码 股票简称 第一部分得分 第二部分得分 第三部分得分 第四部分分类 第五部分得分 核心投资逻辑摘要），文本不需要表头，且不输出其他任何内容。
请务必牢记以上《个股超级龙头+泡沫+翻倍股综合评分标准（V2版）》中的评分规则，之后的股票评分严格按照这一套规则执行。
"""

def _locate_center(img_path, confidence=0.85, timeout=3.0, step=0.3, silent=False, min_confidence=0.55):
    end = time.time() + timeout
    basename = os.path.basename(img_path)
    # 尝试多个置信度级别，始终从最高到最低尝试，防止低置信度误触
    conf_list = sorted(list(set([confidence, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55])), reverse=True)
    # 过滤掉高于传入 confidence 的值，或者从 confidence 开始往下找
    conf_list = [c for c in conf_list if c <= max(confidence, 0.9)]
    # 同时过滤掉低于 min_confidence 的值，防止低置信度误匹配相似图形
    conf_list = [c for c in conf_list if c >= min_confidence]
    
    while True:
        try:
            for conf in conf_list:
                try:
                    pos = pag.locateCenterOnScreen(img_path, confidence=conf, grayscale=True)
                    if pos:
                        if not silent:
                            print(f"[monitor_tdx] Found {basename} at {pos} (conf={conf})", flush=True)
                        return pos
                except Exception:
                    pass
        except Exception as e:
            if not silent:
                print(f"[monitor_tdx] Error locating {basename}: {e}", flush=True)
        
        if time.time() >= end:
            break
        time.sleep(step)
        
    if not silent:
        print(f"[monitor_tdx] Failed to find {basename} after {timeout}s", flush=True)
    return None

def _click(img_path, confidence=0.85, timeout=3.0, double=False, move_time=0.5, offset_x=0, offset_y=0, min_confidence=0.55):
    pos = _locate_center(img_path, confidence, timeout, min_confidence=min_confidence)
    if pos:
        target_x = pos.x + offset_x
        target_y = pos.y + offset_y
        # 先移动鼠标，带有动画效果
        pag.moveTo(target_x, target_y, duration=move_time)
        if double:
            pag.doubleClick(target_x, target_y)
            print(f"[monitor_tdx] Double-Clicked {os.path.basename(img_path)} at ({target_x}, {target_y}) after moving", flush=True)
        else:
            pag.click(target_x, target_y)
            print(f"[monitor_tdx] Clicked {os.path.basename(img_path)} at ({target_x}, {target_y}) after moving", flush=True)
        return True
    return False

def _wait_until_disappear(img_path, confidence=0.85, max_wait=60.0, step=0.5):
    end = time.time() + max_wait
    basename = os.path.basename(img_path)
    while time.time() < end:
        pos = None
        try:
            pos = pag.locateCenterOnScreen(img_path, confidence=confidence)
        except Exception:
            pos = None
        if not pos:
            print(f"[monitor_tdx] {basename} disappeared", flush=True)
            return True
        time.sleep(step)
    print(f"[monitor_tdx] Timeout waiting for {basename} to disappear", flush=True)
    return False

def _ensure_click(img_path, retries=3, confidence=0.85, double=False, move_time=0.5, offset_x=0, offset_y=0, min_confidence=0.55):
    basename = os.path.basename(img_path)
    for i in range(retries):
        if _click(img_path, confidence=confidence, timeout=2.0, double=double, move_time=move_time, offset_x=offset_x, offset_y=offset_y, min_confidence=min_confidence):
            return True
        print(f"[monitor_tdx] Retry {i+1}/{retries} clicking {basename}", flush=True)
        time.sleep(0.5)
    return False

def _ensure_until_found(target_img, fallback_img, confidence=0.75, step=0.5, move_time=0.5):
    target_name = os.path.basename(target_img)
    fallback_name = os.path.basename(fallback_img)
    print(f"[monitor_tdx] Seeking {target_name}, fallback is {fallback_name}", flush=True)
    
    # 第一次尝试静默查找，避免日志刷屏
    start_time = time.time()
    max_total_wait = 30.0 # 最多等待30秒
    
    while time.time() - start_time < max_total_wait:
        # 1. 尝试查找目标 (缩短超时，静默模式)
        pos = _locate_center(target_img, confidence=confidence, timeout=1.0, silent=True)
        if pos:
            pag.moveTo(pos.x, pos.y, duration=move_time)
            pag.click(pos.x, pos.y)
            print(f"[monitor_tdx] Successfully found and clicked {target_name} after moving", flush=True)
            return True
        
        # 2. 没找到，尝试激活 fallback (通常是 tdx.png)
        print(f"[monitor_tdx] {target_name} not found, clicking {fallback_name} to activate...", flush=True)
        # 激活时尝试双击，确保窗口能弹出来
        _ensure_click(fallback_img, retries=1, confidence=0.55, double=True, move_time=move_time)
        time.sleep(step)
        
    print(f"[monitor_tdx] Error: Failed to find {target_name} even after repeated activations", flush=True)
    return False

def _try_recover_doubao4_5_via_4_6(confidence=0.9, move_time=0.5):
    print("[monitor_tdx] doubao4.5.png not found, checking doubao4.6.png as fallback...", flush=True)
    # doubao4.6.png 是向下箭头，易与加号等相似图形误匹配，使用较高的 min_confidence 防止误判
    pos4_6 = _locate_center(IMG_DOUBAO4_6, confidence=confidence, timeout=2.0, silent=True, min_confidence=0.85)
    if not pos4_6:
        print("[monitor_tdx] doubao4.6.png not found either.", flush=True)
        return False

    print("[monitor_tdx] Found doubao4.6.png, clicking it and retrying doubao4.5.png...", flush=True)
    if not _ensure_click(IMG_DOUBAO4_6, retries=2, confidence=confidence, move_time=move_time, min_confidence=0.85):
        return False

    time.sleep(1.0)
    return _locate_center(IMG_DOUBAO4_5, confidence=confidence, timeout=8.0, silent=True) is not None

def _export_file(target_tab=IMG_TAB3, export_file_prefix="实时新高"):
    # 1. 如果当前已经在通达信界面（能看到 market.png / market2.png），就不再重复点击 tdx.png
    print("[monitor_tdx] --- Step 1: Ensure TDX is active ---", flush=True)
    pos_market = _locate_center(IMG_MARKET, confidence=0.7, timeout=0.5, silent=True)
    if not pos_market:
        pos_market = _locate_center(IMG_MARKET2, confidence=0.7, timeout=0.5, silent=True)

    if pos_market:
        print("[monitor_tdx] TDX workspace already visible via market icon, skipping TDX click.", flush=True)
    else:
        print("[monitor_tdx] Market icons not visible, clicking TDX to activate...", flush=True)
        if not _ensure_click(IMG_TDX, retries=3, confidence=0.6, double=True):
            print("[monitor_tdx] Warning: TDX icon not clicked", flush=True)

    # 2. 查找 bankuai.png 和 target_tab，点击刷新按钮
    target_tab_name = os.path.basename(target_tab)
    print(f"[monitor_tdx] --- Step 2: Seek bankuai and refresh ({target_tab_name}) ---", flush=True)
    start_time = time.time()
    refresh_clicked = False
    
    while time.time() - start_time < 60:  # 最多等待 60 秒
        should_click_tdx_again = False

        # 在点击之前先检查是否有卡住的弹窗
        if _handle_stuck_screens():
            print("[monitor_tdx] Stuck screen cleared before refreshing. Continuing...", flush=True)
            time.sleep(0.5)

        # 优先找 target_tab
        pos_tab = _locate_center(target_tab, confidence=0.7, timeout=0.5, silent=True)
        if not pos_tab:
            # 找不到，尝试找 bankuai.png 或 bankuai2.png
            pos_bk = _locate_center(IMG_BANKUAI, confidence=0.7, timeout=0.5, silent=True)
            if not pos_bk:
                pos_bk = _locate_center(IMG_BANKUAI2, confidence=0.7, timeout=0.5, silent=True)
            
            if pos_bk:
                print(f"[monitor_tdx] Found bankuai, clicking it to reveal {target_tab_name}...", flush=True)
                pag.click(pos_bk.x, pos_bk.y)
                time.sleep(1.0)
                continue # 继续循环找 target_tab
            else:
                # 如果没找到 bankuai，找 leftTab.png
                pos_left = _locate_center(IMG_LEFT_TAB, confidence=0.7, timeout=0.5, silent=True)
                if pos_left:
                    print("[monitor_tdx] Found leftTab, clicking it to switch view...", flush=True)
                    pag.click(pos_left.x, pos_left.y)
                    time.sleep(0.5)
                    continue # 重新循环找 bankuai / target_tab
                else:
                    # 如果没有找到 leftTab.png，就先尝试找到 market.png / market2.png 并点击一下，
                    # 然后等待 leftTab.png 出现；如果两个 market 图都没找到，再单击 TDX 激活窗口。
                    pos_market = _locate_center(IMG_MARKET, confidence=0.7, timeout=0.5, silent=True)
                    market_name = "market.png"
                    if not pos_market:
                        pos_market = _locate_center(IMG_MARKET2, confidence=0.7, timeout=0.5, silent=True)
                        market_name = "market2.png"

                    if pos_market:
                        print(f"[monitor_tdx] Found {market_name}, clicking it to reveal leftTab...", flush=True)
                        pag.click(pos_market.x, pos_market.y)
                        print("[monitor_tdx] Waiting for leftTab.png to appear (up to 60s)...", flush=True)
                        pos_left_wait = _locate_center(IMG_LEFT_TAB, confidence=0.7, timeout=60.0)
                        if pos_left_wait:
                            print("[monitor_tdx] Found leftTab.png after clicking market area, clicking it...", flush=True)
                            pag.click(pos_left_wait.x, pos_left_wait.y)
                            time.sleep(0.5)
                            continue
                    else:
                        should_click_tdx_again = True
        else:
            # 找到了 target_tab，先点击一下，再找刷新按钮
            print(f"[monitor_tdx] Found {target_tab_name}, clicking it to reveal refresh button...", flush=True)
            pag.click(pos_tab.x, pos_tab.y)
            time.sleep(0.5) # 给刷新按钮显示一点时间

            # 查找并点击刷新按钮
            pos_refresh_btn = _locate_center(IMG_REFRESH_BTN, confidence=0.7, timeout=1.0, silent=True)
            if not pos_refresh_btn:
                pos_refresh_btn = _locate_center(IMG_REFRESH_BTN2, confidence=0.7, timeout=1.0, silent=True)

            if pos_refresh_btn:
                print("[monitor_tdx] Found refresh button, clicking it...", flush=True)
                pag.click(pos_refresh_btn.x, pos_refresh_btn.y)
                refresh_clicked = True
                break
            else:
                print(f"[monitor_tdx] Failed to find refresh button after clicking {target_tab_name}.", flush=True)

        # 仅在 market.png / market2.png 都没找到时，再单击 TDX 激活窗口，避免已打开窗口被双击缩回去。
        if should_click_tdx_again:
            print("[monitor_tdx] Required tabs not found and market icons missing, single-clicking TDX again...", flush=True)
            _ensure_click(IMG_TDX, retries=1, confidence=0.6, double=False)
            time.sleep(1.0)

    if not refresh_clicked:
        print("[monitor_tdx] Error: Failed to find/click refresh button after 60s", flush=True)
        return None

    # 3. 等待 autoTip.png 出现并消失 (自动选股过程)
    print("[monitor_tdx] --- Step 3: Waiting for auto-selection (autoTip) ---", flush=True)
    start_wait = time.time()
    # 整个 Step 3 的最大允许时间为 10 分钟 (600秒)
    MAX_STEP3_TIME = 600
    tip_appeared = False
    
    while True:
        elapsed = time.time() - start_wait
        if elapsed > MAX_STEP3_TIME:
            print(f"[monitor_tdx] Error: Step 3 total time exceeded {MAX_STEP3_TIME}s. Checking for stuck screens...", flush=True)
            # 10 分钟到了还没找到，最后检查一次是否有卡住的弹窗
            if _handle_stuck_screens():
                print("[monitor_tdx] Stuck screen cleared after 10 min timeout. Restarting flow...", flush=True)
            return None
            
        # 尝试查找 autoTip.png
        tip_pos = _locate_center(IMG_AUTOTIP, confidence=0.8, timeout=1.0, silent=True)
        
        if tip_pos:
            if not tip_appeared:
                print("[monitor_tdx] autoTip detected, now waiting for it to finish...", flush=True)
                tip_appeared = True
            # 如果还在显示，继续等待
            time.sleep(2.0)
            continue
        else:
            # 如果曾经出现过，现在找不到了，说明消失了，过程结束
            if tip_appeared:
                print("[monitor_tdx] autoTip disappeared, selection finished.", flush=True)
                break
            
            # 如果还没出现过，就一直等待到 10 分钟为止
            if elapsed % 30 < 2: # 每 30 秒打印一下状态
                print(f"[monitor_tdx] Still waiting for autoTip to appear... ({int(elapsed)}s/{MAX_STEP3_TIME}s)", flush=True)
            
            # 期间如果看到 refresh 也可以打印一下，但不中断
            if _locate_center(IMG_REFRESH, confidence=0.8, timeout=0.5, silent=True):
                # print("[monitor_tdx] refresh indicator detected, still waiting for autoTip...", flush=True)
                pass
            
            time.sleep(2.0)
            continue

    print("[monitor_tdx] Auto-selection phase finished", flush=True)

    # 3.5. 点击 code.png 下方 50 像素处
    print("[monitor_tdx] --- Step 3.5: Click below code.png ---", flush=True)
    pos_code = _locate_center(IMG_CODE, confidence=0.7, timeout=3.0)
    if pos_code:
        target_x = pos_code.x
        target_y = pos_code.y + 50
        print(f"[monitor_tdx] Found code.png at {pos_code}, clicking below it at ({target_x}, {target_y})...", flush=True)
        pag.moveTo(target_x, target_y, duration=0.5)
        pag.click(target_x, target_y)
        time.sleep(0.5)
    else:
        print("[monitor_tdx] Warning: code.png not found, skipping Step 3.5", flush=True)

    # 4. 点击选项按钮 (options.png / options2.png / options3.png) - 找不到就重复找，不往下走
    print("[monitor_tdx] --- Step 4: Click Options ---", flush=True)
    options_clicked = False
    start_time = time.time()
    last_options_img = IMG_OPTIONS # 记录最后一次成功的图片，用于后续回退
    while time.time() - start_time < 60:
        # 尝试按顺序找三个 options 图片
        for img in [IMG_OPTIONS, IMG_OPTIONS2, IMG_OPTIONS3]:
            if _ensure_click(img, retries=1, confidence=0.6):
                options_clicked = True
                last_options_img = img
                break
        if options_clicked:
            break
        print("[monitor_tdx] options.png / options2.png / options3.png not found, retrying...", flush=True)
        time.sleep(1.0)
    
    if not options_clicked:
        print("[monitor_tdx] Error: Could not find Options button after 60s", flush=True)
        return None

    # 5. 点击导出按钮 (exportBtn.png)
    print("[monitor_tdx] --- Step 5: Click Export ---", flush=True)
    if not _ensure_until_found(IMG_EXPORT_BTN, last_options_img, confidence=0.7, step=0.5):
        # 如果还是找不到，尝试清理一下可能遮挡的弹窗
        _handle_stuck_screens()
        return None
        
    # 6. 导出对话框操作
    print("[monitor_tdx] --- Step 6: Handle Export Dialog ---", flush=True)
    # 先点“格式文本文件”
    if not _ensure_until_found(IMG_FORMAT, IMG_EXPORT_BTN, confidence=0.7, step=0.5):
        return None
    # 再点“所有数据(显示的栏目)”
    if not _ensure_until_found(IMG_EXPORT_ALL, IMG_FORMAT, confidence=0.7, step=0.5):
        return None
    # 最后点“导出”
    if not _ensure_until_found(IMG_EXPORT_DO, IMG_EXPORT_ALL, confidence=0.7, step=0.5):
        return None
    time.sleep(1.0)
    
    # 6.5 等待刷新数据 (refresh.png) 消失
    print("[monitor_tdx] --- Step 6.5: Waiting for refresh to finish ---", flush=True)
    # 给一点时间让 refresh.png 可能出现
    time.sleep(1.0)
    if _locate_center(IMG_REFRESH, confidence=0.8, timeout=2.0, silent=True):
        print("[monitor_tdx] refresh indicator detected, waiting for it to disappear...", flush=True)
        # 最长等待 600 秒刷新完成 (10 分钟)
        _wait_until_disappear(IMG_REFRESH, confidence=0.8, max_wait=600.0, step=1.0)
    else:
        print("[monitor_tdx] No refresh indicator detected, proceeding...", flush=True)

    # 7. 关闭导出完成提示
    print("[monitor_tdx] --- Step 7: Close Dialog ---", flush=True)
    # 增加置信度到 0.9，防止误触左边的“确定”按钮
    # 同时增加 offset_x=10，确保点击的是“取消”按钮的中心偏右位置
    _ensure_click(IMG_CANCEL_BTN, retries=3, confidence=0.9, offset_x=10)
    
    d = datetime.now().strftime("%Y%m%d")
    path = os.path.join(VMWARE_SHARED_LOG_DIR, f"{export_file_prefix}{d}.txt")
    return path

def _wait_file_ready(path, timeout=10.0, step=0.5):
    end = time.time() + timeout
    last_size = -1
    while time.time() < end:
        if os.path.exists(path):
            try:
                size = os.path.getsize(path)
                if size > 0 and size == last_size:
                    return True
                last_size = size
            except Exception:
                pass
        time.sleep(step)
    return os.path.exists(path)

def _fallback_latest_file():
    base = VMWARE_SHARED_LOG_DIR
    try:
        files = [os.path.join(base, f) for f in os.listdir(base) if f.endswith(".xls")]
        files = sorted(files, key=lambda p: os.path.getmtime(p), reverse=True)
        return files[0] if files else None
    except Exception:
        return None

def _read_records(file_path):
    if not file_path or not os.path.exists(file_path):
        print(f"[monitor_tdx] read_records: file not exists: {file_path}", flush=True)
        return []
    
    print(f"[monitor_tdx] --- Parsing File Content: {os.path.basename(file_path)} ---", flush=True)
    
    recs = []
    # 如果是 .txt 文件，通达信导出的 TXT 通常是 GBK 编码的制表符分隔文本
    if file_path.endswith('.txt'):
        try:
            with open(file_path, 'r', encoding='gb18030', errors='ignore') as f:
                lines = f.readlines()
            
            if not lines:
                print("[monitor_tdx] TXT file is empty", flush=True)
                return []

            # 打印前 3 行原始数据，确认格式
            for i, line in enumerate(lines[:3]):
                preview = line.strip().replace('\t', '[TAB]')
                print(f"[monitor_tdx] TXT Line {i+1} raw: {preview}", flush=True)

            # 寻找表头行，通常包含“代码”或“名称”
            header_idx = -1
            for i, line in enumerate(lines[:10]):
                if "代码" in line or "名称" in line:
                    header_idx = i
                    break
            
            if header_idx == -1:
                # 如果没找到表头，假设从第 1 行开始就是数据
                print("[monitor_tdx] Header not found, assuming data starts from line 1", flush=True)
                data_lines = lines
                code_idx, name_idx, ind_idx, zdf_idx = 0, 1, 2, -1
            else:
                header = lines[header_idx].split('\t')
                print(f"[monitor_tdx] Header found at line {header_idx+1}: {header}", flush=True)
                # 寻找关键列的索引
                code_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["代码", "证券代码", "Code"])), 0)
                name_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["名称", "证券名称", "Name"])), 1)
                ind_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["细分行业", "行业", "Industry"])), 2)
                zdf_idx = next((i for i, h in enumerate(header) if "涨幅" in h or "涨跌幅" in h), -1)
                data_lines = lines[header_idx+1:]

            for line in data_lines:
                parts = line.split('\t')
                if len(parts) > max(code_idx, name_idx):
                    code = parts[code_idx].strip()
                    name = parts[name_idx].strip()
                    industry = parts[ind_idx].strip() if ind_idx < len(parts) else ""
                    zdf = parts[zdf_idx].strip() if zdf_idx != -1 and zdf_idx < len(parts) else ""
                    
                    # 补齐 6 位代码
                    if code.isdigit() and len(code) < 6:
                        code = code.zfill(6)
                    
                    # 过滤无效行及以 9 开头的股票代码
                    if code and name and "代码" not in code and "数据来源" not in code:
                        if code.startswith('9'):
                            print(f"[monitor_tdx] Filtering out code starting with 9: {code} | {name}", flush=True)
                            continue
                        recs.append((code, name, industry, zdf)) 
            
            if recs:
                print(f"[monitor_tdx] Successfully parsed via manual TXT parsing, records={len(recs)}", flush=True)
                # 打印所有数据进行核对
                print("[monitor_tdx] --- Detailed Records Start ---", flush=True)
                for i, (c, n, ind, zdf) in enumerate(recs):
                    print(f"[monitor_tdx] Row {i+1}: {c} | {n} | {ind} | {zdf}", flush=True)
                print(f"[monitor_tdx] --- Total Extracted: {len(recs)} records ---", flush=True)
                return recs
        except Exception as e:
            print(f"[monitor_tdx] Manual TXT parse error: {e}", flush=True)

    # 如果 TXT 手动解析失败或不是 TXT，尝试原来的 pandas 逻辑
    df = None
    try:
        # ... 原有的 pandas 解析逻辑作为兜底 ...
        if file_path.endswith('.txt'):
            df = pd.read_csv(file_path, sep='\t', encoding='gb18030', engine='python', skipblanklines=True)
    except Exception:
        pass
    
    # (此处省略部分冗余的旧逻辑代码，保持 read_records 结构完整即可)
    if not recs and (df is not None and not df.empty):
        # 按照原逻辑提取数据...
        pass

    return recs

def _query_stock_scores(codes):
    """查询个股评分信息：优先查 stock_deep_analysis_v2，没查到再查 stock_deep_analysis。
    返回 dict: code -> {'source': 'v2'|'old', 'p1'..'p5', 'part4', 'result_type', 'score'}
    v2 表用 (P1+P3+P5) 作为排序分；老表用 score 作为排序分。
    """
    info_map = {}
    if not codes:
        return info_map
    try:
        from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
        import pymysql
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        format_strings = ','.join(['%s'] * len(codes))

        # 1) 先查 v2 表
        try:
            cursor.execute(f"SELECT code, name, score_part1, score_part2, score_part3, part4_category, score_part5 FROM stock_deep_analysis_v2 WHERE code IN ({format_strings})", tuple(codes))
            for row in cursor.fetchall():
                if row['score_part1'] or row['score_part2'] or row['score_part3'] or row['score_part5']:
                    info_map[row['code']] = {
                        'source': 'v2',
                        'p1': row['score_part1'] or 0,
                        'p2': row['score_part2'] or 0,
                        'p3': row['score_part3'] or 0,
                        'part4': (row['part4_category'] or '').strip(),
                        'p5': row['score_part5'] or 0,
                    }
        except Exception as e:
            print(f"[monitor_tdx] v2 query error (table may not exist): {e}", flush=True)

        # 2) 对 v2 表没查到的 code，再查老表
        missing_codes = [c for c in codes if c not in info_map]
        if missing_codes:
            fmt2 = ','.join(['%s'] * len(missing_codes))
            cursor.execute(f"SELECT code, result_type, score FROM stock_deep_analysis WHERE code IN ({fmt2})", tuple(missing_codes))
            for row in cursor.fetchall():
                if row['result_type'] != '淘汰':
                    info_map[row['code']] = {
                        'source': 'old',
                        'result_type': row['result_type'],
                        'score': row['score'] or 0,
                    }
        conn.close()
    except Exception as e:
        print(f"[monitor_tdx] _query_stock_scores DB error: {e}", flush=True)
    return info_map


def _build_score_suffix(info):
    """根据 info 组装评分后缀文本和排序分。"""
    if info['source'] == 'v2':
        # 格式: 第四类 龙头89 泡沫61 基本面115 翻倍50
        suffix = f" {info['part4']} 龙头{info['p1']} 泡沫{info['p2']} 基本面{info['p3']} 翻倍{info['p5']}"
        sort_score = info['p1'] + info['p3'] + info['p5']
    else:
        suffix = f" [{info['result_type']}] {info['score']}分"
        sort_score = info['score']
    return suffix, sort_score


def _compose_all_msg(recs):
    # 查询数据库获取个股评价（优先 v2，回退老表）
    codes = [c for c, _, _, _ in recs]
    db_info = _query_stock_scores(codes)

    # 给 recs 附加排序分
    recs_with_score = []
    for c, n, i, zdf in recs:
        sort_score = -1
        if c in db_info:
            _, sort_score = _build_score_suffix(db_info[c])
        recs_with_score.append((c, n, i, zdf, sort_score))

    # 根据分数降序排序
    recs_with_score.sort(key=lambda x: x[4], reverse=True)

    # 每行: 股票代码 股票名称 细分行业 + 评分后缀
    lines = []
    for c, n, i, zdf, score in recs_with_score:
        base_line = f"{c} {n} {i}"
        if c in db_info:
            suffix, _ = _build_score_suffix(db_info[c])
            base_line += suffix
        lines.append(base_line)
    return "\n".join(lines)

def _compose_incremental_msg(new_recs):
    # 查询数据库获取个股评价（优先 v2，回退老表）
    codes = [c for c, _, _, _ in new_recs]
    db_info = _query_stock_scores(codes)

    # 给 new_recs 附加排序分
    recs_with_score = []
    for c, n, i, zdf in new_recs:
        sort_score = -1
        if c in db_info:
            _, sort_score = _build_score_suffix(db_info[c])
        recs_with_score.append((c, n, i, zdf, sort_score))

    # 根据分数降序排序
    recs_with_score.sort(key=lambda x: x[4], reverse=True)

    # 仅针对新增股票的提醒格式: 代码 名称 细分行业 + 评分后缀
    lines = []
    for c, n, i, zdf, score in recs_with_score:
        base_line = f"{c} {n} {i}"
        if c in db_info:
            suffix, _ = _build_score_suffix(db_info[c])
            base_line += suffix
        lines.append(base_line)

    # 在消息最后面统一添加提示
    lines.append("\n请注意锁住利润！新仓请在尾盘开！")
    return "\n".join(lines)

def _compose_industry_cluster_msg(recs):
    """
    分析细分行业聚集逻辑：
    如果细分行业内容一样且超过3个，提醒“XXX”已同时新高几个。
    排除“其他通用设备”、“其他专用设备”。
    """
    from collections import Counter
    # 提取所有行业（过滤掉排除名单和空值）
    exclude_list = ["其他通用设备", "其他专用设备", ""]
    industries = [i for _, _, i, _ in recs if i not in exclude_list]
    
    counts = Counter(industries)
    cluster_msgs = []
    for ind, count in counts.items():
        if count >= 3:
            cluster_msgs.append(f"“{ind}”已同时新高{count}个")
                
    return "\n".join(cluster_msgs) if cluster_msgs else ""

def _handle_stuck_screens():
    """检测并清理卡住的界面（如取消按钮弹窗）"""
    for img in [IMG_CANCEL_BTN, IMG_CANCEL_BTN2]:
        # 对于这种极其相似的按钮，我们手动调用 locate，不使用 _locate_center 的自动降级逻辑
        # 强制要求 0.9 以上的精度
        try:
            pos = pag.locateCenterOnScreen(img, confidence=0.95, grayscale=True)
            if not pos:
                pos = pag.locateCenterOnScreen(img, confidence=0.9, grayscale=True)
            
            if pos:
                print(f"[monitor_tdx] Stuck screen detected via {os.path.basename(img)} at {pos}, clicking to clear...", flush=True)
                # 移动到该位置右侧 15 像素（确保在“取消”按钮内部靠右）
                target_x = pos.x + 15
                target_y = pos.y
                pag.moveTo(target_x, target_y, duration=0.5)
                pag.click(target_x, target_y)
                # 成功处理一个就返回
                return True
        except Exception as e:
            print(f"[monitor_tdx] Error locating {os.path.basename(img)} in stuck check: {e}", flush=True)
            
    return False

def _wait_for_market_start(target_time="09:25"):
    """等待直到达到目标开始时间（如 09:25）"""
    target_hour, target_min = map(int, target_time.split(":"))
    
    while True:
        now = datetime.now()
        target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
        
        # 如果当前时间已经过了今天的目标时间
        if now >= target:
            # 检查是否是同一个交易日（如果脚本一直开着）
            # 这里简单处理：只要过了 09:25 就允许运行
            return
            
        wait_seconds = (target - now).total_seconds()
        print(f"[monitor_tdx] Current time {now.strftime('%H:%M:%S')} is before {target_time}. Waiting {int(wait_seconds)}s...", flush=True)
        
        # 每分钟打印一次进度，或者如果剩余时间不足一分钟，则直接睡完
        sleep_time = min(60, wait_seconds)
        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            break

def _format_trade_date(date_str):
    if len(date_str) == 8 and date_str.isdigit():
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
    return date_str

def _count_new_high_records(file_path):
    """轻量统计单个实时新高 TXT 文件中的股票家数。"""
    if not file_path or not os.path.exists(file_path):
        return 0

    try:
        with open(file_path, 'r', encoding='gb18030', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"[monitor_tdx] Failed to read new high file {file_path}: {e}", flush=True)
        return 0

    if not lines:
        return 0

    header_idx = -1
    for i, line in enumerate(lines[:10]):
        if "代码" in line or "名称" in line:
            header_idx = i
            break

    if header_idx == -1:
        data_lines = lines
        code_idx = 0
    else:
        header = lines[header_idx].split('\t')
        code_idx = next((i for i, h in enumerate(header) if any(k in h for k in ["代码", "证券代码", "Code"])), 0)
        data_lines = lines[header_idx + 1:]

    codes = set()
    for line in data_lines:
        parts = line.split('\t')
        if len(parts) <= code_idx:
            continue

        raw_code = parts[code_idx].strip()
        if not raw_code or "代码" in raw_code or "数据来源" in raw_code:
            continue

        code_match = re.search(r'\d{6}', raw_code)
        if not code_match:
            continue

        code = code_match.group()
        if code.startswith('9'):
            continue
        codes.add(code)

    return len(codes)

def _get_recent_new_high_file_stats(limit=MORNING_NEW_HIGH_ANALYSIS_DAYS):
    """获取最近 N 个交易日的实时新高文件及其家数统计。"""
    pattern = re.compile(r'^实时新高(\d{8})\.txt$')
    stats = []

    try:
        for file_name in os.listdir(VMWARE_SHARED_LOG_DIR):
            match = pattern.match(file_name)
            if not match:
                continue

            trade_date = match.group(1)
            file_path = os.path.join(VMWARE_SHARED_LOG_DIR, file_name)
            count = _count_new_high_records(file_path)
            stats.append((trade_date, count, file_path))
    except Exception as e:
        print(f"[monitor_tdx] Failed to list realtime new high files: {e}", flush=True)
        return []

    stats.sort(key=lambda item: item[0])
    return stats[-limit:]

def _build_new_high_trend_summary(stats, analysis_time_label):
    if not stats:
        return None

    if analysis_time_label == "14:40":
        title = f"【{analysis_time_label} 近10个交易日实时新高趋势（含当日最新）】"
    else:
        title = f"【{analysis_time_label} 近10个交易日实时新高趋势】"

    dates = [item[0] for item in stats]
    counts = [item[1] for item in stats]
    count_len = len(counts)

    max_count = max(counts)
    min_count = min(counts)
    max_idx = counts.index(max_count)
    min_idx = counts.index(min_count)

    if count_len >= 2:
        latest_change = counts[-1] - counts[-2]
        latest_change_text = f"{latest_change:+d}"
    else:
        latest_change = 0
        latest_change_text = "0"

    if count_len >= 3:
        recent3 = counts[-3:]
        if recent3[0] < recent3[1] < recent3[2]:
            short_trend = "短线连续升温"
        elif recent3[0] > recent3[1] > recent3[2]:
            short_trend = "短线连续降温"
        elif recent3[2] > recent3[1] <= recent3[0]:
            short_trend = "短线有拐头向上迹象"
        elif recent3[2] < recent3[1] >= recent3[0]:
            short_trend = "短线有拐头向下迹象"
        else:
            short_trend = "短线震荡整理"
    else:
        short_trend = "样本较少，短线趋势待观察"

    current_state = get_market_advice(counts[-1])

    lines = [
        title,
        f"统计区间：{_format_trade_date(dates[0])} ~ {_format_trade_date(dates[-1])}",
        f"样本天数：{count_len}天",
        "每日新高家数：",
    ]

    for trade_date, count, _ in stats:
        lines.append(f"{_format_trade_date(trade_date)} {count}家")

    lines.extend([
        f"阶段高点：{max_count}家（{_format_trade_date(dates[max_idx])}）",
        f"阶段低点：{min_count}家（{_format_trade_date(dates[min_idx])}）",
        f"最近一日较前一日：{latest_change_text}家",
        f"趋势判断：{short_trend}",
        f"当前强弱：{current_state}",
    ])
    return "\n".join(lines)

def _check_and_send_new_high_analysis():
    now = datetime.now()
    d = now.strftime("%Y%m%d")
    for analysis_time in NEW_HIGH_ANALYSIS_TIMES:
        target_hour, target_min = map(int, analysis_time.split(":"))
        target_time = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
        diff_minutes = (now - target_time).total_seconds() / 60.0

        if not (0 <= diff_minutes <= NEW_HIGH_ANALYSIS_WINDOW_MINUTES):
            continue

        send_key = f"{d}_{analysis_time}"
        if send_key in new_high_analysis_sent_keys:
            continue

        stats = _get_recent_new_high_file_stats(MORNING_NEW_HIGH_ANALYSIS_DAYS)
        if not stats:
            print(f"[monitor_tdx] New high analysis skipped at {analysis_time}: no recent realtime-new-high files found.", flush=True)
            return False

        msg = _build_new_high_trend_summary(stats, analysis_time)
        if not msg:
            return False

        print(f"[monitor_tdx] Sending realtime-new-high trend analysis for {analysis_time} at {now.strftime('%H:%M:%S')}...", flush=True)
        send_wechat_message(msg)
        new_high_analysis_sent_keys.add(send_key)
        return True

    return False

def _check_and_send_advice():
    """
    检查是否需要在整点发送今日操作建议
    每天10点、11点、13点、14点整点发送
    """
    global last_advice_sent_time
    
    now = datetime.now()
    d = now.strftime("%Y%m%d")
    
    for h in ADVICE_HOURS:
        target_time = now.replace(hour=h, minute=0, second=0, microsecond=0)
        diff_minutes = (now - target_time).total_seconds() / 60.0
        
        # 只要时间过了整点，且距离整点不超过配置窗口，就尝试发送
        if 0 <= diff_minutes <= ADVICE_TRIGGER_WINDOW_MINUTES:
            time_key = f"{d}_{h:02d}"
            
            # 如果这个时间段已经发送过，则跳过
            if last_advice_sent_time == time_key:
                continue
            
            # 获取今日操作建议
            msg, count = get_today_advice_msg()
            
            if msg:
                print(f"[monitor_tdx] Sending daily advice for {h}:00 at {now.strftime('%H:%M:%S')}...", flush=True)
                send_wechat_message(msg)
                last_advice_sent_time = time_key
                return True
    
    return False

def _run_export_and_read(target_tab, export_prefix, d):
    txt_path = os.path.join(VMWARE_SHARED_LOG_DIR, f"{export_prefix}{d}.txt")
    xls_path = os.path.join(VMWARE_SHARED_LOG_DIR, f"{export_prefix}{d}.xls")
    
    for p in [txt_path, xls_path]:
        if os.path.exists(p):
            try:
                os.remove(p)
                print(f"[monitor_tdx] Removed old file: {p}", flush=True)
            except Exception as e:
                print(f"[monitor_tdx] Failed to remove old file: {e}", flush=True)

    actual_path = _export_file(target_tab, export_prefix)
    if actual_path is None:
        print("[monitor_tdx] Export failed due to missing images.", flush=True)
        return None, None

    if not _wait_file_ready(actual_path, timeout=20.0):
        print(f"[monitor_tdx] Export finished but file not ready/found: {actual_path}", flush=True)
        return None, None
        
    print(f"[monitor_tdx] Successfully exported and ready to read: {actual_path}", flush=True)
    recs = _read_records(actual_path)
    return recs, actual_path

special_tasks_done = set()

def _check_and_run_special_tasks(d, current_time_str):
    # 获取所有需要检查的时间点
    all_times = sorted(list(set(ETF_TASK_TIMES + QBD_TASK_TIMES)))
    now = datetime.now()
    
    for t in all_times:
        t_hour, t_min = map(int, t.split(':'))
        target_time = now.replace(hour=t_hour, minute=t_min, second=0, microsecond=0)
        diff_minutes = (now - target_time).total_seconds() / 60.0
        
        if diff_minutes >= 0:
            # 分别检查起爆点和ETF任务是否已执行
            qbd_key = f"{d}_qbd_{t}"
            etf_key = f"{d}_etf_{t}"
            # 如果超过配置分钟数，说明是中途重启，跳过过去太久的任务
            if diff_minutes > SPECIAL_TASK_EXPIRE_MINUTES:
                special_tasks_done.add(qbd_key)
                special_tasks_done.add(etf_key)
                continue
            
            # 1. tab5: 起爆点
            if t in QBD_TASK_TIMES and qbd_key not in special_tasks_done:
                print(f"\n[monitor_tdx] --- Running QBD Special Task for {t} ---", flush=True)
                print(f"[monitor_tdx] Processing tab5: 起爆点", flush=True)
                recs_5, _ = _run_export_and_read(IMG_TAB5, "起爆点", d)
                if recs_5:
                    msg_5 = _compose_all_msg(recs_5)
                    final_msg_5 = f"【起爆点 {t}】\n{msg_5}"
                    send_wechat_message(final_msg_5)
                else:
                    print(f"[monitor_tdx] No records found for tab5 at {t}.", flush=True)
                special_tasks_done.add(qbd_key)
                print(f"[monitor_tdx] --- Finished QBD Special Task for {t} ---\n", flush=True)
                
            # 2. tab6: 新高ETF
            if t in ETF_TASK_TIMES and etf_key not in special_tasks_done:
                print(f"\n[monitor_tdx] --- Running ETF Special Task for {t} ---", flush=True)
                print(f"[monitor_tdx] Processing tab6: 新高ETF", flush=True)
                recs_6, _ = _run_export_and_read(IMG_TAB6, "新高ETF", d)
                if recs_6:
                    # 提取涨幅并附加到记录中用于排序
                    recs_with_zdf = []
                    for c, n, i, zdf in recs_6:
                        zdf_val = 0.0
                        if zdf:
                            try:
                                zdf_val = float(zdf)
                            except:
                                pass
                        recs_with_zdf.append((c, n, i, zdf, zdf_val))
                        
                    # 按照涨幅降序排序
                    recs_with_zdf.sort(key=lambda x: x[4], reverse=True)
                    
                    # 格式化输出行，包含涨幅
                    lines_6 = []
                    for c, n, i, zdf, _ in recs_with_zdf:
                        zdf_str = f" 涨幅:{zdf}%" if zdf else ""
                        lines_6.append(f"{c} {n} {i}{zdf_str}")
                        
                    final_msg_6 = f"【距离新高5%以内ETF {t}】\n" + "\n".join(lines_6)
                    send_wechat_message(final_msg_6)
                else:
                    print(f"[monitor_tdx] No records found for tab6 at {t}.", flush=True)
                special_tasks_done.add(etf_key)
                print(f"[monitor_tdx] --- Finished ETF Special Task for {t} ---\n", flush=True)

def _ensure_scoring_table(db_table):
    """确保评分结果表存在，不存在则创建。v2 表使用细分字段，老表使用原字段结构。"""
    try:
        from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cursor = conn.cursor()
        if db_table == "stock_deep_analysis_v2":
            # 新标准表：细分五大部分得分
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {db_table} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    report_date VARCHAR(20) COMMENT '分析时间',
                    code VARCHAR(10) COMMENT '股票代码',
                    name VARCHAR(50) COMMENT '股票简称',
                    score_part1 INT DEFAULT 0 COMMENT '第一部分得分(超级龙头,满分100)',
                    score_part2 INT DEFAULT 0 COMMENT '第二部分得分(泡沫,满分100,越高泡沫越大)',
                    score_part3 INT DEFAULT 0 COMMENT '第三部分得分(综合条件,满分130)',
                    part4_category VARCHAR(100) COMMENT '第四部分分类(股价上涨逻辑1-6类)',
                    score_part5 INT DEFAULT 0 COMMENT '第五部分得分(翻倍股,满分100)',
                    analysis_detail TEXT COMMENT '分析详情',
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_code_date (code, report_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个股超级龙头+泡沫+翻倍股综合评分表(V2)';
            """)
        else:
            # 老标准表：保持原结构
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {db_table} (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    report_date VARCHAR(20) COMMENT '分析日期',
                    code VARCHAR(10) COMMENT '股票代码',
                    name VARCHAR(50) COMMENT '股票名称',
                    result_type VARCHAR(50) COMMENT '评级/结果',
                    score INT DEFAULT 0 COMMENT '打分分数',
                    analysis_detail TEXT COMMENT '分析详情',
                    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    UNIQUE KEY uk_code_date (code, report_date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='私募首席选股官深度分析表';
            """)
        conn.commit()
        conn.close()
        print(f"[monitor_tdx] Ensured table {db_table} exists.", flush=True)
    except Exception as e:
        print(f"[monitor_tdx] Error creating table {db_table}: {e}", flush=True)


def _run_doubao_scoring_session(d, actual_path, scoring_standard, db_table,
                                 standard_label, standard_name, db_txt_suffix,
                                 update_rating):
    """
    执行一轮豆包打分会话。
    参数:
        d               : 日期字符串 (YYYYMMDD)
        actual_path     : 导出文件路径
        scoring_standard: 评分标准文本
        db_table        : 目标数据库表名
        standard_label  : 标准标签 (用于日志, 如 "老标准"/"新标准")
        standard_name   : 评分标准名称 (用于发送给豆包的消息中引用)
        db_txt_suffix   : 数据库txt文件后缀 (如 "" 或 "_v2")
        update_rating   : 是否根据分数自动调整 result_type 评级
    返回:
        True  - 正常完成
        False - 所有股票已处理过(跳过)或出错提前退出
    """
    print(f"[monitor_tdx] [{standard_label}] Starting Deep Analysis via AI Chief...", flush=True)
    try:
        print(f"[monitor_tdx] [{standard_label}] Interacting with Doubao via GUI...", flush=True)

        # 点击 doubao1.png
        if _ensure_click(IMG_DOUBAO1, retries=3, confidence=0.8, move_time=0.5):
            time.sleep(1.0)
            if _ensure_click(IMG_DOUBAO2_1, retries=3, confidence=0.8, move_time=0.5, offset_y=-30):
                time.sleep(1.0)

                print(f"[monitor_tdx] [{standard_label}] Looking for doubao3.5/3.6/3.7.png to focus input...", flush=True)
                clicked_input = _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5)
                if not clicked_input:
                    print(f"[monitor_tdx] [{standard_label}] doubao3.5.png not found, trying doubao3.6.png...", flush=True)
                    clicked_input = _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5)
                if not clicked_input:
                    print(f"[monitor_tdx] [{standard_label}] doubao3.6.png not found, trying doubao3.7.png...", flush=True)
                    clicked_input = _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)

                if clicked_input:
                    print(f"[monitor_tdx] [{standard_label}] Clicked input area, input box focused.", flush=True)
                    time.sleep(0.5)

                    if os.path.exists(actual_path):
                        try:
                            with open(actual_path, 'r', encoding='utf-8', errors='strict') as f:
                                raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('9')]
                        except UnicodeDecodeError:
                            with open(actual_path, 'r', encoding='gb18030', errors='ignore') as f:
                                raw_lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('9')]

                        # 从数据库读取一个月内已存在的股票并过滤
                        thirty_days_ago = (datetime.strptime(d, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
                        existing_codes = set()
                        try:
                            from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
                            filter_conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
                            filter_cursor = filter_conn.cursor()
                            filter_cursor.execute(f"SELECT code FROM {db_table} WHERE report_date >= %s", (thirty_days_ago,))
                            existing_codes = {row[0] for row in filter_cursor.fetchall()}
                            filter_conn.close()
                        except Exception as filter_e:
                            print(f"[monitor_tdx] [{standard_label}] Warning: Failed to query existing codes for filtering: {filter_e}", flush=True)

                        # v2 模式：解析出 现价/流通市值 等字段
                        if db_table == "stock_deep_analysis_v2":
                            # 解析表头，定位 现价/流通市值 列
                            header_idx = -1
                            price_idx = -1
                            mktcap_idx = -1
                            code_idx_v2 = 0
                            name_idx_v2 = 1
                            for i, line in enumerate(raw_lines[:10]):
                                parts = line.split('\t')
                                if any('代码' in p for p in parts):
                                    header_idx = i
                                    for j, h in enumerate(parts):
                                        if '现价' in h or '最新' in h:
                                            price_idx = j
                                        elif '流通' in h and ('市值' in h or '本' in h):
                                            mktcap_idx = j
                                        elif '代码' in h:
                                            code_idx_v2 = j
                                        elif '名称' in h:
                                            name_idx_v2 = j
                                    break
                            print(f"[monitor_tdx] [{standard_label}] TXT header at line {header_idx+1}, price_idx={price_idx}, mktcap_idx={mktcap_idx}", flush=True)

                            lines = []
                            for line in raw_lines[(header_idx + 1 if header_idx != -1 else 0):]:
                                parts = line.split('\t')
                                code = parts[code_idx_v2].strip() if code_idx_v2 < len(parts) else ''
                                code_match = re.search(r'\d{6}', code)
                                if not code_match:
                                    continue
                                code = code_match.group()
                                if code in existing_codes:
                                    continue
                                if code.startswith('9'):
                                    continue
                                name = parts[name_idx_v2].strip() if name_idx_v2 < len(parts) else ''
                                price = parts[price_idx].strip() if price_idx != -1 and price_idx < len(parts) else ''
                                mktcap = parts[mktcap_idx].strip() if mktcap_idx != -1 and mktcap_idx < len(parts) else ''
                                lines.append(f"{code} {name} 现价：{price} 流通市值：{mktcap}")
                        else:
                            # 老模式：整行作为 stock_info
                            lines = []
                            for line in raw_lines:
                                code_match = re.search(r'\d{6}', line)
                                if not code_match:
                                    continue
                                if code_match.group() in existing_codes:
                                    continue
                                lines.append(line)

                        print(f"[monitor_tdx] [{standard_label}] Read {len(raw_lines)} lines, after filtering 30-day existing codes, {len(lines)} lines remaining.", flush=True)
                        if not lines:
                            print(f"[monitor_tdx] [{standard_label}] All stocks already processed in the last 30 days. Skipping.", flush=True)
                            return False

                        batch_size = 1 if db_table == "stock_deep_analysis_v2" else 5
                        resend_every = 10 if db_table == "stock_deep_analysis_v2" else 50
                        db_txt_prefix = "新数据库" if db_table == "stock_deep_analysis_v2" else "数据库"
                        db_txt_path = os.path.join(VMWARE_SHARED_LOG_DIR, f"{db_txt_prefix}{d}.txt")

                        # 仅当文件不存在时创建空文件；已存在则保留（避免清空已有结果）
                        if not os.path.exists(db_txt_path):
                            with open(db_txt_path, 'w', encoding='utf-8') as db_f:
                                db_f.write("")

                        for i in range(0, len(lines), batch_size):
                            if i == 0 or i % resend_every == 0:
                                print(f"[monitor_tdx] [{standard_label}] Sending scoring standard before stock index {i}...", flush=True)
                                std_ready = False
                                while not std_ready:
                                    pyperclip.copy(scoring_standard)
                                    time.sleep(0.5)
                                    pag.hotkey('ctrl', 'v')
                                    time.sleep(1.0)
                                    pag.press('enter')

                                    print(f"[monitor_tdx] [{standard_label}] Waiting for doubao4.5.png after sending standard (up to 3 mins)...", flush=True)
                                    std_wait_time = time.time()
                                    std_recover_clicked = False
                                    while time.time() - std_wait_time < 180.0:
                                        if _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=1.0, silent=True):
                                            std_ready = True
                                            break
                                        if not std_recover_clicked and _locate_center(IMG_DOUBAO4_6, confidence=0.9, timeout=0.5, silent=True, min_confidence=0.85):
                                            print(f"[monitor_tdx] [{standard_label}] doubao4.5.png not found, clicking doubao4.6.png then retrying...", flush=True)
                                            if _ensure_click(IMG_DOUBAO4_6, retries=2, confidence=0.9, move_time=0.5, min_confidence=0.85):
                                                std_recover_clicked = True
                                                time.sleep(1.0)
                                                continue
                                        time.sleep(1.0)

                                    if not std_ready and not std_recover_clicked and _try_recover_doubao4_5_via_4_6():
                                        std_ready = True

                                    if not std_ready:
                                        print(f"[monitor_tdx] [{standard_label}] Warning: doubao4.5.png not found within 3 mins, resending standard...", flush=True)
                                        if not _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5):
                                            if not _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5):
                                                _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)

                                print(f"[monitor_tdx] [{standard_label}] doubao4.5.png found. Standard sent successfully.", flush=True)
                                time.sleep(2.0)
                                if _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5):
                                    print(f"[monitor_tdx] [{standard_label}] Refocused input box for next batch.", flush=True)

                            batch_lines = lines[i:i + batch_size]
                            stock_info = "\n".join(batch_lines)

                            if db_table == "stock_deep_analysis_v2":
                                output_format = "硬性打分强制规则：1.第一部分：超级龙头判断法，满分100，4大模块所有细分小项逐条打分后相加得出总分；2.第二部分：泡沫风险打分，满分100，15条指标逐条打分求和得出总分；3.第三部分：综合优质个股加分项，满分130，20条逐条计分，风险项倒扣后核算最终总分；4.第四部分：上涨逻辑六类，仅输出中文分类（第一类/第二类/第三类/第四类/第五类/第六类），禁止数字；5.第五部分：翻倍股潜力打分，固定5个分项，每项满分20分，必须单独打出分项分数，5项分数全部相加得出100分制总分，严禁只用单一分项分数、漏算任意一小项、估算模糊分值，计算过程完整核算，总分区间0-100；输出固定单行格式，无表头、无多余解释、无分段：股票代码 股票简称 第一部分总分 第二部分总分 第三部分总分 第四部分中文分类 第五部分完整合计总分 核心投资逻辑摘要"
                            else:
                                output_format = "股票代码 股票简称 综合评级 综合评分 核心投资逻辑摘要"
                            msg_to_agent = f"全网检索个股资料，汇总至少60篇行业研报、公司公告、产业新闻、竞品数据，严格完整按《{standard_name}》全流程检索打分，输出固定格式（{output_format}） 的文本，文本不需要表头，且不输出其他任何内容 \n【股份信息】\n{stock_info}"

                            result_ready = False
                            pos4_5 = None

                            while not result_ready:
                                pyperclip.copy(msg_to_agent)
                                time.sleep(0.5)
                                pag.hotkey('ctrl', 'v')
                                time.sleep(1.0)
                                pag.press('enter')
                                print(f"[monitor_tdx] [{standard_label}] Sent batch {i//batch_size + 1} to Doubao.", flush=True)

                                print(f"[monitor_tdx] [{standard_label}] Waiting for doubao4.5.png (result ready) up to 3 mins...", flush=True)
                                start_wait_time = time.time()
                                max_wait_time = 180.0
                                result_recover_clicked = False

                                while time.time() - start_wait_time < max_wait_time:
                                    pos4_5 = _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=1.0, silent=True)
                                    if pos4_5:
                                        result_ready = True
                                        break
                                    if not result_recover_clicked and _locate_center(IMG_DOUBAO4_6, confidence=0.9, timeout=0.5, silent=True, min_confidence=0.85):
                                        print(f"[monitor_tdx] [{standard_label}] doubao4.5.png not found, clicking doubao4.6.png then retrying...", flush=True)
                                        if _ensure_click(IMG_DOUBAO4_6, retries=2, confidence=0.9, move_time=0.5, min_confidence=0.85):
                                            result_recover_clicked = True
                                            time.sleep(1.0)
                                            continue
                                    time.sleep(1.0)

                                if not result_ready and not result_recover_clicked and _try_recover_doubao4_5_via_4_6():
                                    pos4_5 = _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=2.0, silent=True)
                                    result_ready = pos4_5 is not None

                                if not result_ready:
                                    print(f"[monitor_tdx] [{standard_label}] Warning: doubao4.5.png not found within 3 mins, resending batch...", flush=True)
                                    if not _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5):
                                        if not _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5):
                                            _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)

                            print(f"[monitor_tdx] [{standard_label}] Found doubao4.5.png, waiting 5 seconds before looking for doubao5.png...", flush=True)
                            time.sleep(5.0)

                            try:
                                start_wait_copy_time = time.time()
                                max_wait_copy_time = 180.0
                                all_pos5 = []

                                print(f"[monitor_tdx] [{standard_label}] Looking for doubao5.png or doubao5.5.png (up to 3 minutes)...", flush=True)
                                while time.time() - start_wait_copy_time < max_wait_copy_time:
                                    all_pos5 = list(pag.locateAllOnScreen(IMG_DOUBAO5, confidence=0.8, grayscale=True))
                                    if not all_pos5:
                                        all_pos5 = list(pag.locateAllOnScreen(IMG_DOUBAO5_5, confidence=0.8, grayscale=True))
                                    if all_pos5:
                                        break
                                    time.sleep(1.0)

                                if all_pos5:
                                    bottom_pos5 = sorted(all_pos5, key=lambda p: p.top, reverse=True)[0]
                                    center_x = bottom_pos5.left + bottom_pos5.width / 2
                                    center_y = bottom_pos5.top + bottom_pos5.height / 2

                                    pag.moveTo(center_x, center_y, 0.5)
                                    pag.click()
                                    print(f"[monitor_tdx] [{standard_label}] Clicked the lowest doubao5.png at ({center_x}, {center_y})", flush=True)

                                    time.sleep(1.0)
                                    result_text = pyperclip.paste()

                                    with open(db_txt_path, 'a', encoding='utf-8') as db_f:
                                        db_f.write(result_text + "\n\n")
                                    print(f"[monitor_tdx] [{standard_label}] Saved batch {i//batch_size + 1} result to {db_txt_path}", flush=True)

                                    print(f"[monitor_tdx] [{standard_label}] Looking for doubao3.5/3.6/3.7.png to refocus for next batch...", flush=True)
                                    if not _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5):
                                        if not _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5):
                                            _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)
                                    print(f"[monitor_tdx] [{standard_label}] Refocused input box for next batch.", flush=True)
                                else:
                                    print(f"[monitor_tdx] [{standard_label}] Error: Failed to find doubao5.png on screen", flush=True)
                            except Exception as e:
                                print(f"[monitor_tdx] [{standard_label}] Error locating/clicking doubao5.png: {e}", flush=True)

                        # 数据清洗
                        print(f"[monitor_tdx] [{standard_label}] Cleaning up irrelevant conversational text...", flush=True)
                        try:
                            with open(db_txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                clean_raw_lines = f.readlines()

                            cleaned_lines = []
                            for line in clean_raw_lines:
                                stripped = line.strip()
                                if not stripped:
                                    continue
                                if '需要我把这' in stripped or '全流程打分明细吗' in stripped:
                                    continue
                                if stripped.startswith('好的') or '以下是' in stripped:
                                    continue
                                cleaned_lines.append(stripped)

                            # 多行合并：以6位数字开头的行视为新股票起始，后续非数字开头行合并到前一行
                            merged_lines = []
                            for line in cleaned_lines:
                                if re.match(r'^\d{6}\s', line):
                                    merged_lines.append(line)
                                elif merged_lines:
                                    merged_lines[-1] = merged_lines[-1] + line
                                # 否则丢弃孤立的非股票行

                            cleaned_lines = merged_lines

                            with open(db_txt_path, 'w', encoding='utf-8') as f:
                                f.write('\n'.join(cleaned_lines) + '\n')
                            print(f"[monitor_tdx] [{standard_label}] Cleaned {len(clean_raw_lines) - len(cleaned_lines)} irrelevant lines, merged to {len(cleaned_lines)} stocks.", flush=True)
                        except Exception as clean_e:
                            print(f"[monitor_tdx] [{standard_label}] Error during data cleaning: {clean_e}", flush=True)

                        # 落库
                        print(f"[monitor_tdx] [{standard_label}] Importing results to database {db_table}...", flush=True)
                        try:
                            from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
                            conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
                            cursor = conn.cursor()

                            with open(db_txt_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()

                            csv_blocks = re.findall(r'```(?:csv)?\n(.*?)\n```', content, re.DOTALL)
                            if not csv_blocks:
                                csv_blocks = [content]

                            for block in csv_blocks:
                                try:
                                    lines_in_block = [line for line in block.strip().split('\n') if line.strip() and not line.startswith('---')]
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
                                        if not header_found:
                                            is_space_separated = False
                                            if len(cleaned_lines) > 0 and ' ' in cleaned_lines[0]:
                                                parts = [p for p in cleaned_lines[0].split(' ') if p.strip()]
                                                if len(parts) >= 5 and re.match(r'\d{6}', parts[0]):
                                                    is_space_separated = True

                                            if is_space_separated:
                                                if db_table == "stock_deep_analysis_v2":
                                                    # v2表: 代码 简称 第一部分得分 第二部分得分 第三部分得分 第四部分分类 第五部分得分 摘要
                                                    v2_header = "代码\t简称\t第一部分得分\t第二部分得分\t第三部分得分\t第四部分分类\t第五部分得分\t核心投资逻辑摘要"
                                                    parsed_lines = [v2_header]
                                                    for line in cleaned_lines:
                                                        parts = [p for p in line.strip().split(' ') if p.strip()]
                                                        if len(parts) >= 8:
                                                            code = parts[0]
                                                            name = parts[1]
                                                            p1, p2, p3 = parts[2], parts[3], parts[4]
                                                            p4 = parts[5]
                                                            p5 = parts[6]
                                                            reason = " ".join(parts[7:])
                                                            parsed_lines.append(f"{code}\t{name}\t{p1}\t{p2}\t{p3}\t{p4}\t{p5}\t{reason}")
                                                        else:
                                                            parsed_lines.append(line)
                                                    cleaned_lines = parsed_lines
                                                    df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                                                else:
                                                    parsed_lines = ["代码\t名称\t评级\t分数\t理由"]
                                                    for line in cleaned_lines:
                                                        parts = [p for p in line.strip().split(' ') if p.strip()]
                                                        if len(parts) >= 5:
                                                            code = parts[0]
                                                            name = parts[1]
                                                            rating = parts[2]
                                                            score = parts[3]
                                                            reason = " ".join(parts[4:])
                                                            parsed_lines.append(f"{code}\t{name}\t{rating}\t{score}\t{reason}")
                                                        else:
                                                            parsed_lines.append(line)
                                                    cleaned_lines = parsed_lines
                                                    df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                                            else:
                                                if db_table == "stock_deep_analysis_v2":
                                                    cleaned_lines.insert(0, "代码,简称,第一部分得分,第二部分得分,第三部分得分,第四部分分类,第五部分得分,核心投资逻辑摘要")
                                                else:
                                                    cleaned_lines.insert(0, "代码,名称,评级,分数,理由")
                                                try:
                                                    df = pd.read_csv(StringIO('\n'.join(cleaned_lines)))
                                                except Exception:
                                                    try:
                                                        df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                                                    except Exception:
                                                        df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep=r'\s+')
                                        else:
                                            try:
                                                df = pd.read_csv(StringIO('\n'.join(cleaned_lines)))
                                            except Exception:
                                                try:
                                                    df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep='\t')
                                                except Exception:
                                                    df = pd.read_csv(StringIO('\n'.join(cleaned_lines)), sep=r'\s+')

                                        cols = list(df.columns)
                                        code_col = next((c for c in cols if '代码' in c), None)
                                        name_col = next((c for c in cols if '名称' in c or '简称' in c), None)
                                        detail_col = next((c for c in cols if '理由' in c or '分析' in c or '详情' in c or '简评' in c or '摘要' in c or '原因' in c), None)

                                        if code_col:
                                            for _, row in df.iterrows():
                                                code = str(row[code_col]).strip()
                                                if code.replace('.', '').isdigit():
                                                    code = str(int(float(code))).zfill(6)
                                                code = code.replace("'", "").replace('"', '')
                                                code_match = re.search(r'\d{6}', code)
                                                if code_match:
                                                    code = code_match.group()
                                                else:
                                                    continue

                                                if not code or code == 'nan':
                                                    continue

                                                name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ''
                                                detail = str(row[detail_col]).strip() if detail_col and pd.notna(row[detail_col]) else ''

                                                if db_table == "stock_deep_analysis_v2":
                                                    # 新标准：五大部分细分得分
                                                    def _parse_score(col_keywords):
                                                        col = next((c for c in cols if all(k in c for k in col_keywords)), None)
                                                        if col and pd.notna(row[col]):
                                                            try:
                                                                m = re.search(r'\d+', str(row[col]).replace('分', ''))
                                                                return int(m.group()) if m else 0
                                                            except Exception:
                                                                return 0
                                                        return 0

                                                    score_part1 = _parse_score(['第一部分'])
                                                    score_part2 = _parse_score(['第二部分'])
                                                    score_part3 = _parse_score(['第三部分'])
                                                    score_part5 = _parse_score(['第五部分'])
                                                    part4_col = next((c for c in cols if '第四部分' in c), None)
                                                    part4_category = str(row[part4_col]).strip() if part4_col and pd.notna(row[part4_col]) else ''

                                                    sql = f'''
                                                        INSERT INTO {db_table} (report_date, code, name, score_part1, score_part2, score_part3, part4_category, score_part5, analysis_detail)
                                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                                        ON DUPLICATE KEY UPDATE
                                                            name = IF(VALUES(name) != '', VALUES(name), name),
                                                            score_part1 = IF(VALUES(score_part1) > 0, VALUES(score_part1), score_part1),
                                                            score_part2 = IF(VALUES(score_part2) > 0, VALUES(score_part2), score_part2),
                                                            score_part3 = IF(VALUES(score_part3) > 0, VALUES(score_part3), score_part3),
                                                            part4_category = IF(VALUES(part4_category) != '', VALUES(part4_category), part4_category),
                                                            score_part5 = IF(VALUES(score_part5) > 0, VALUES(score_part5), score_part5),
                                                            analysis_detail = IF(VALUES(analysis_detail) != '', VALUES(analysis_detail), analysis_detail)
                                                    '''
                                                    cursor.execute(sql, (d, code, name, score_part1, score_part2, score_part3, part4_category, score_part5, detail))
                                                else:
                                                    # 老标准：综合评级 + 综合评分
                                                    score_col = next((c for c in cols if '分' in c), None)
                                                    type_col = next((c for c in cols if '评级' in c or '结果' in c or '类型' in c), None)
                                                    score = 0
                                                    if score_col and pd.notna(row[score_col]):
                                                        try:
                                                            score_str = str(row[score_col]).replace('分', '').strip()
                                                            score_match = re.search(r'\d+', score_str)
                                                            if score_match:
                                                                score = int(score_match.group())
                                                        except Exception:
                                                            pass
                                                    result_type = str(row[type_col]).strip() if type_col and pd.notna(row[type_col]) else ''

                                                    sql = f'''
                                                        INSERT INTO {db_table} (report_date, code, name, result_type, score, analysis_detail)
                                                        VALUES (%s, %s, %s, %s, %s, %s)
                                                        ON DUPLICATE KEY UPDATE
                                                            name = IF(VALUES(name) != '', VALUES(name), name),
                                                            result_type = IF(VALUES(result_type) != '', VALUES(result_type), result_type),
                                                            score = IF(VALUES(score) > 0, VALUES(score), score),
                                                            analysis_detail = IF(VALUES(analysis_detail) != '', VALUES(analysis_detail), analysis_detail)
                                                    '''
                                                    cursor.execute(sql, (d, code, name, result_type, score, detail))
                                except Exception as inner_e:
                                    print(f"[monitor_tdx] [{standard_label}] Error parsing CSV block: {inner_e}")

                            # 落库完成后，根据 score 统一调整评级
                            if update_rating:
                                update_sql = f"""
                                    UPDATE {db_table}
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
                            print(f"[monitor_tdx] [{standard_label}] DB import and rating adjustment finished.", flush=True)
                        except Exception as db_e:
                            print(f"[monitor_tdx] [{standard_label}] DB import error: {db_e}", flush=True)
                    else:
                        print(f"[monitor_tdx] [{standard_label}] Actual path {actual_path} not found.", flush=True)
                else:
                    print(f"[monitor_tdx] [{standard_label}] Error: doubao3.5/3.6/3.7.png not found or failed to click.", flush=True)
            else:
                print(f"[monitor_tdx] [{standard_label}] Error: Failed to click doubao2.1.png offset area", flush=True)
        else:
            print(f"[monitor_tdx] [{standard_label}] Error: Failed to click doubao1.png", flush=True)

    except Exception as e:
        print(f"[monitor_tdx] [{standard_label}] Deep Analysis / Doubao GUI Interaction Error: {e}", flush=True)

    return True


def run_once():
    global baseline_date, baseline_codes, afternoon_task_done_date
    
    now = datetime.now()
    d = now.strftime("%Y%m%d")
    
    # 先等待到第一个趋势分析发送时点，再执行近 10 个交易日实时新高趋势分析
    if not FORCE_SCORING_NOW:
        _wait_for_market_start(min(NEW_HIGH_ANALYSIS_TIMES))
        _check_and_send_new_high_analysis()

        # 再等待到开盘前启动时间
        _wait_for_market_start(MARKET_START_TIME)
    
    # 在执行主逻辑前，先检查是否需要发送今日操作建议
    _check_and_send_advice()
    
    print(f"\n[monitor_tdx] --- New Loop Start: {now.strftime('%H:%M:%S')} ---", flush=True)
    
    # 是否强制进入打分流程（用于调试，忽略 15:00 时间限制）
    is_afternoon = FORCE_SCORING_NOW or now.hour >= AFTERNOON_START_HOUR
    
    # 检查并执行特殊时间点的任务 (10:00, 11:00, 13:30, 14:30)
    if not is_afternoon:
        _check_and_run_special_tasks(d, now.strftime('%H:%M'))
    
    # 每一轮开始前，先检查并清理可能卡住的界面
    if _handle_stuck_screens():
        print("[monitor_tdx] Stuck screens cleared, proceeding with normal flow.", flush=True)
    
    if is_afternoon:
        if afternoon_task_done_date == d and not FORCE_SCORING_NOW:
            print("[monitor_tdx] Afternoon task (>=15:00) already done for today. Sleeping...", flush=True)
            time.sleep(AFTERNOON_DONE_SLEEP_SECONDS)
            return
            
        print("[monitor_tdx] --- Running Afternoon Logic (>= 15:00) ---", flush=True)
        # 1. 15:00 之后，先获取业绩预告和报告并保存到数据库
        try:
            from quant.services.performance_analysis import init_db, fetch_earnings_forecast, fetch_earnings_report, save_forecasts_to_db, save_reports_to_db
            report_date = "2026-03-31" # 这里使用默认的一季度
            init_db()
            forecasts = fetch_earnings_forecast(report_date)
            reports = fetch_earnings_report(report_date)
            if forecasts: save_forecasts_to_db(forecasts, report_date)
            if reports: save_reports_to_db(reports, report_date)
        except Exception as e:
            print(f"[monitor_tdx] Error updating performance DB: {e}", flush=True)
            
        target_tab = IMG_TAB4
        export_prefix = "十五以内"
    else:
        target_tab = IMG_TAB3
        export_prefix = "实时新高"

    # 开始自动化导出
    recs, actual_path = _run_export_and_read(target_tab, export_prefix, d)
    
    # 如果没有找到记录或文件读取失败，直接结束本次循环
    if not recs:
        if actual_path is None:
            # 导出过程中出错
            pass
        else:
            print("[monitor_tdx] No records found in the exported file.", flush=True)
            
        # 如果是 15:00 之后，即使没有记录也要标记完成，防止无限重启循环
        if is_afternoon:
            afternoon_task_done_date = d
        return
        
    # ====== 去重逻辑：防止由于读取时遇到重复行而发送多条相同的股票消息 ======
    unique_recs = []
    seen_codes = set()
    for r in recs:
        if r[0] not in seen_codes:
            seen_codes.add(r[0])
            unique_recs.append(r)
    recs = unique_recs
    # =====================================================================

    print(f"[monitor_tdx] Processing {len(recs)} records...", flush=True)
    
    # 15:00 之后的对比逻辑
    if is_afternoon:
        from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
        import pymysql
        
        report_date = "2026-03-31"
        msg_lines = []
        try:
            conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            
            for code, name, industry in recs:
                # 检查业绩预告
                cursor.execute("SELECT reason FROM earnings_forecast WHERE code=%s AND report_date=%s", (code, report_date))
                f_row = cursor.fetchone()
                if f_row:
                    reason = f_row['reason'] or "无"
                    msg_lines.append(f"{code} {name} 原因：{reason}")
                    continue
                
                # 检查业绩报告
                cursor.execute("SELECT id FROM earnings_report WHERE code=%s AND report_date=%s", (code, report_date))
                r_row = cursor.fetchone()
                if r_row:
                    msg_lines.append(f"{code} {name} 距离新高15%以内，且业绩好，请关注。")
                    
            conn.close()
        except Exception as e:
            print(f"[monitor_tdx] DB query error: {e}", flush=True)
            
        if msg_lines:
            batch_size = 3
            for i in range(0, len(msg_lines), batch_size):
                batch_lines = msg_lines[i:i + batch_size]
                final_msg = f"【15:00 盘后十五以内新高及业绩匹配 ({i//batch_size + 1})】\n" + "\n".join(batch_lines)
                # send_wechat_message(final_msg)
                time.sleep(1) # 稍微延迟避免发送过快
        else:
            print("[monitor_tdx] No matching records found in DB for afternoon logic.", flush=True)
            
        # ===================== 评分流程（根据 SCORING_MODE 配置） =====================
        sessions = []
        if SCORING_MODE in ("old", "serial"):
            sessions.append((SCORING_STANDARD, "stock_deep_analysis", "老标准",
                             "个股评分标准（最终定稿版）", "", True))
        if SCORING_MODE in ("new", "serial"):
            sessions.append((SCORING_STANDARD_V2, "stock_deep_analysis_v2", "新标准",
                             "个股超级龙头+泡沫+翻倍股综合评分标准（V2版）", "_v2", False))

        for scoring_standard, db_table, standard_label, standard_name, db_txt_suffix, update_rating in sessions:
            _ensure_scoring_table(db_table)
            _run_doubao_scoring_session(d, actual_path, scoring_standard, db_table,
                                        standard_label, standard_name, db_txt_suffix,
                                        update_rating)

        # 标记今日下午任务已完成
        afternoon_task_done_date = d
        return

        # ===== 以下旧代码已迁移到 _run_doubao_scoring_session 函数，保留备查 =====
        print("[monitor_tdx] Starting Deep Analysis via AI Chief...", flush=True)
        try:
            # 增加通过 GUI 与智能体对话的操作 (改为和豆包交互)
            print("[monitor_tdx] Interacting with Doubao via GUI...", flush=True)
            
            # 点击 doubao1.png
            if _ensure_click(IMG_DOUBAO1, retries=3, confidence=0.8, move_time=0.5):
                time.sleep(1.0)
                # 找到 doubao2.1.png 后，点击其上方 30px 的位置
                if _ensure_click(IMG_DOUBAO2_1, retries=3, confidence=0.8, move_time=0.5, offset_y=-30):
                    time.sleep(1.0)
                    
                    print("[monitor_tdx] Looking for doubao3.5.png / doubao3.6.png / doubao3.7.png to focus input...", flush=True)

                    # 寻找并点击 doubao3.5.png 以获取焦点，找不到则依次尝试 doubao3.6.png / doubao3.7.png
                    clicked_input = _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5)
                    if not clicked_input:
                        print("[monitor_tdx] doubao3.5.png not found, trying doubao3.6.png...", flush=True)
                        clicked_input = _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5)
                    if not clicked_input:
                        print("[monitor_tdx] doubao3.6.png not found, trying doubao3.7.png...", flush=True)
                        clicked_input = _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)
                        
                    if clicked_input:
                        print("[monitor_tdx] Clicked input area, input box focused.", flush=True)
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
                                print(f"[monitor_tdx] Warning: Failed to query existing codes for filtering: {filter_e}", flush=True)

                            lines = []
                            for line in raw_lines:
                                # 假设 line 格式类似: 600312 平高电气
                                code_match = re.search(r'\d{6}', line)
                                if not code_match:
                                    continue  # 跳过表头或不含股票代码的行
                                if code_match.group() in existing_codes:
                                    continue
                                lines.append(line)

                            print(f"[monitor_tdx] Read {len(raw_lines)} lines, after filtering 30-day existing codes, {len(lines)} lines remaining to process.", flush=True)
                            if not lines:
                                print("[monitor_tdx] All stocks already processed in the last 30 days. Skipping Doubao interaction.", flush=True)
                                # 标记今日下午任务已完成并退出本次 GUI 交互逻辑
                                afternoon_task_done_date = d
                                return

                            batch_size = 5
                            db_txt_path = os.path.join(VMWARE_SHARED_LOG_DIR, f"数据库{d}.txt")

                            # 仅当文件不存在时创建空文件；已存在则保留（避免清空已有结果）
                            if not os.path.exists(db_txt_path):
                                with open(db_txt_path, 'w', encoding='utf-8') as db_f:
                                    db_f.write("")

                            for i in range(0, len(lines), batch_size):
                                if i == 0 or i % 50 == 0:
                                    print(f"[monitor_tdx] Sending SCORING_STANDARD before stock index {i}...", flush=True)
                                    std_ready = False
                                    while not std_ready:
                                        pyperclip.copy(SCORING_STANDARD)
                                        time.sleep(0.5)
                                        pag.hotkey('ctrl', 'v')
                                        time.sleep(1.0)
                                        pag.press('enter')

                                        print("[monitor_tdx] Waiting for doubao4.5.png after sending standard (up to 3 mins)...", flush=True)
                                        std_wait_time = time.time()
                                        std_recover_clicked = False
                                        while time.time() - std_wait_time < 180.0:
                                            if _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=1.0, silent=True):
                                                std_ready = True
                                                break
                                            # 没找到 doubao4.5.png，先尝试找 doubao4.6.png 并点击，再继续找 doubao4.5.png
                                            # doubao4.6.png 是向下箭头，易与加号误匹配，使用较高的 min_confidence
                                            if not std_recover_clicked and _locate_center(IMG_DOUBAO4_6, confidence=0.9, timeout=0.5, silent=True, min_confidence=0.85):
                                                print("[monitor_tdx] doubao4.5.png not found, clicking doubao4.6.png then retrying...", flush=True)
                                                if _ensure_click(IMG_DOUBAO4_6, retries=2, confidence=0.9, move_time=0.5, min_confidence=0.85):
                                                    std_recover_clicked = True
                                                    time.sleep(1.0)
                                                    continue
                                            time.sleep(1.0)

                                        if not std_ready and not std_recover_clicked and _try_recover_doubao4_5_via_4_6():
                                            std_ready = True

                                        if not std_ready:
                                            print("[monitor_tdx] Warning: doubao4.5.png not found within 3 mins, resending SCORING_STANDARD...", flush=True)
                                            if not _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5):
                                                if not _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5):
                                                    _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)

                                    print("[monitor_tdx] doubao4.5.png found. Standard sent successfully.", flush=True)
                                    time.sleep(2.0)
                                    if _ensure_click(IMG_DOUBAO3_5, retries=3, confidence=0.8, move_time=0.5):
                                        print("[monitor_tdx] Refocused input box for next batch.", flush=True)

                                batch_lines = lines[i:i + batch_size]
                                stock_info = "\n".join(batch_lines)

                                msg_to_agent = f"搜索各个股票信息，信息要尽可能的全面，至少获取60篇及以上的资料，严格按《个股评分标准（最终定稿版）》全流程检索打分，输出固定格式（股票代码 股票简称 综合评级 综合评分 核心投资逻辑摘要） 的文本，文本不需要表头，且不输出其他任何内容 \n【股份信息】\n{stock_info}"

                                result_ready = False
                                pos4_5 = None

                                while not result_ready:
                                    pyperclip.copy(msg_to_agent)
                                    time.sleep(0.5)

                                    pag.hotkey('ctrl', 'v')
                                    time.sleep(1.0)
                                    pag.press('enter')
                                    print(f"[monitor_tdx] Sent batch {i//batch_size + 1} to Doubao.", flush=True)

                                    print("[monitor_tdx] Waiting for doubao4.5.png (result ready) up to 3 mins...", flush=True)
                                    start_wait_time = time.time()
                                    max_wait_time = 180.0
                                    result_recover_clicked = False

                                    while time.time() - start_wait_time < max_wait_time:
                                        pos4_5 = _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=1.0, silent=True)

                                        if pos4_5:
                                            result_ready = True
                                            break

                                        # 没找到 doubao4.5.png，先尝试找 doubao4.6.png 并点击，再继续找 doubao4.5.png
                                        # doubao4.6.png 是向下箭头，易与加号误匹配，使用较高的 min_confidence
                                        if not result_recover_clicked and _locate_center(IMG_DOUBAO4_6, confidence=0.9, timeout=0.5, silent=True, min_confidence=0.85):
                                            print("[monitor_tdx] doubao4.5.png not found, clicking doubao4.6.png then retrying...", flush=True)
                                            if _ensure_click(IMG_DOUBAO4_6, retries=2, confidence=0.9, move_time=0.5, min_confidence=0.85):
                                                result_recover_clicked = True
                                                time.sleep(1.0)
                                                continue

                                        time.sleep(1.0)

                                    if not result_ready and not result_recover_clicked and _try_recover_doubao4_5_via_4_6():
                                        pos4_5 = _locate_center(IMG_DOUBAO4_5, confidence=0.8, timeout=2.0, silent=True)
                                        result_ready = pos4_5 is not None

                                    if not result_ready:
                                        print("[monitor_tdx] Warning: doubao4.5.png not found within 3 mins, resending batch...", flush=True)
                                        if not _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5):
                                            if not _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5):
                                                _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)

                                print("[monitor_tdx] Found doubao4.5.png, waiting 5 seconds before looking for doubao5.png...", flush=True)
                                time.sleep(5.0)

                                # 为了确保点击的是最新的复制按钮（在屏幕最下方），我们可以通过定位所有 doubao5.png
                                # 然后选取 Y 坐标最大的那个（即最靠下的那个）来点击。
                                try:
                                    # 增加循环等待寻找复制按钮的逻辑，最多等待 180 秒（3分钟）
                                    start_wait_copy_time = time.time()
                                    max_wait_copy_time = 180.0
                                    all_pos5 = []

                                    print("[monitor_tdx] Looking for doubao5.png or doubao5.5.png (up to 3 minutes)...", flush=True)
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
                                        print(f"[monitor_tdx] Clicked the lowest doubao5.png at ({center_x}, {center_y})", flush=True)

                                        time.sleep(1.0)
                                        result_text = pyperclip.paste()

                                        # 粘贴追加到数据库文件
                                        with open(db_txt_path, 'a', encoding='utf-8') as db_f:
                                            db_f.write(result_text + "\n\n")
                                        print(f"[monitor_tdx] Saved batch {i//batch_size + 1} result to {db_txt_path}", flush=True)

                                        # 为了确保能发送下一批次，重新寻找并点击输入框激活焦点
                                        print("[monitor_tdx] Looking for doubao3.5.png / doubao3.6.png / doubao3.7.png to refocus for next batch...", flush=True)
                                        if not _ensure_click(IMG_DOUBAO3_5, retries=2, confidence=0.8, move_time=0.5):
                                            if not _ensure_click(IMG_DOUBAO3_6, retries=2, confidence=0.8, move_time=0.5):
                                                _ensure_click(IMG_DOUBAO3_7, retries=2, confidence=0.8, move_time=0.5)
                                        print("[monitor_tdx] Refocused input box for next batch.", flush=True)
                                    else:
                                        print("[monitor_tdx] Error: Failed to find doubao5.png on screen", flush=True)
                                except Exception as e:
                                    print(f"[monitor_tdx] Error locating/clicking doubao5.png: {e}", flush=True)

                            # 数据清洗：剔除豆包生成的无关闲聊与空行
                            print("[monitor_tdx] Cleaning up irrelevant conversational text...", flush=True)
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
                                print(f"[monitor_tdx] Cleaned {len(raw_lines) - len(cleaned_lines)} irrelevant lines.", flush=True)
                            except Exception as clean_e:
                                print(f"[monitor_tdx] Error during data cleaning: {clean_e}", flush=True)

                            # 最后落库到 quant_data.stock_deep_analysis
                            print("[monitor_tdx] Importing results to database...", flush=True)
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

                                            cols = list(df.columns)
                                            code_col = next((c for c in cols if '代码' in c), None)
                                            name_col = next((c for c in cols if '名称' in c or '简称' in c), None)
                                            score_col = next((c for c in cols if '分' in c), None)
                                            type_col = next((c for c in cols if '评级' in c or '结果' in c or '类型' in c), None)
                                            detail_col = next((c for c in cols if '理由' in c or '分析' in c or '详情' in c or '简评' in c or '摘要' in c or '原因' in c), None)

                                            if code_col:
                                                for _, row in df.iterrows():
                                                    code = str(row[code_col]).strip()
                                                    if code.replace('.', '').isdigit():
                                                        code = str(int(float(code))).zfill(6)
                                                    code = code.replace("'", "").replace('"', '')
                                                    code_match = re.search(r'\d{6}', code)
                                                    if code_match:
                                                        code = code_match.group()
                                                    else:
                                                        continue

                                                    if not code or code == 'nan':
                                                        continue

                                                    name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else ''
                                                    score = 0
                                                    if score_col and pd.notna(row[score_col]):
                                                        try:
                                                            score_str = str(row[score_col]).replace('分', '').strip()
                                                            score_match = re.search(r'\d+', score_str)
                                                            if score_match:
                                                                score = int(score_match.group())
                                                        except Exception:
                                                            pass

                                                    result_type = str(row[type_col]).strip() if type_col and pd.notna(row[type_col]) else ''
                                                    detail = str(row[detail_col]).strip() if detail_col and pd.notna(row[detail_col]) else ''

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
                                    except Exception as inner_e:
                                        print(f"[monitor_tdx] Error parsing CSV block: {inner_e}")

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
                                print("[monitor_tdx] DB import and result_type adjustment finished.", flush=True)
                            except Exception as db_e:
                                print(f"[monitor_tdx] DB import error: {db_e}", flush=True)
                        else:
                            print(f"[monitor_tdx] Actual path {actual_path} not found.", flush=True)
                    else:
                        print("[monitor_tdx] Error: doubao3.5.png not found or failed to click.", flush=True)
                else:
                    print("[monitor_tdx] Error: Failed to click doubao2.1.png offset area", flush=True)
            else:
                print("[monitor_tdx] Error: Failed to click doubao1.png", flush=True)
                
        except Exception as e:
            print(f"[monitor_tdx] Deep Analysis / Doubao GUI Interaction Error: {e}", flush=True)
            
        # 标记今日下午任务已完成
        afternoon_task_done_date = d
        return
        
    # 15:00 之前的逻辑（实时新高）
    # 如果日期变了，清空基准
    if baseline_date != d:
        print(f"[monitor_tdx] Date changed from {baseline_date} to {d}. Resetting baseline.", flush=True)
        baseline_date = d
        baseline_codes = set()
        
    # 如果是当日第一次获取数据（基准为空），则发送全量并建立基准
    if not baseline_codes:
        print("[monitor_tdx] First run of the day. Sending all records and establishing baseline.", flush=True)
        # 全量消息
        msg = _compose_all_msg(recs)
        
        # 行业聚集消息 (针对全量数据)
        cluster_msg = _compose_industry_cluster_msg(recs)
        if cluster_msg:
            msg = f"{msg}\n\n--- 行业聚集提醒 ---\n{cluster_msg}"
            
        if msg:
            send_wechat_message(msg)
        baseline_codes = {c for c, _, _, _ in recs}
        return
        
    # 对比逻辑：找出当前 recs 中存在但 baseline_codes 中不存在的股票
    new_recs = [(c, n, i, zdf) for c, n, i, zdf in recs if c not in baseline_codes]
    
    if new_recs:
        print(f"[monitor_tdx] Detected {len(new_recs)} new high records!", flush=True)
        # 增量消息
        msg = _compose_incremental_msg(new_recs)
        
        # 行业聚集消息 (针对当前所有新高数据，看看是否有新的行业聚集出现)
        cluster_msg = _compose_industry_cluster_msg(recs)
        if cluster_msg:
            msg = f"{msg}\n\n--- 行业聚集提醒 ---\n{cluster_msg}"
            
        # 更新基准，将新增的股票加入（先更新内存，防止发送失败或耗时过长导致下一轮重复）
        for c, _, _, _ in new_recs:
            baseline_codes.add(c)
            
        if msg:
            try:
                send_wechat_message(msg)
            except Exception as e:
                print(f"[monitor_tdx] Error sending incremental WeChat msg: {e}", flush=True)
    else:
        print("[monitor_tdx] No new records since last check. Baseline remains the same.", flush=True)

def main_loop():
    print("[monitor_tdx] started", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            import traceback
            print(f"[monitor_tdx] error: {e}", flush=True)
            traceback.print_exc()
        # 一次循环执行完后，不等待，直接开始下一次循环
        time.sleep(1) # 仅保留1秒极短的缓冲，防止 CPU 100%

def _cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    # 移除 --interval 的默认长等待，改为 1 秒极短缓冲
    parser.add_argument("--interval", type=int, default=1)
    args = parser.parse_args()
    try:
        os.chdir(os.path.dirname(__file__))
    except Exception:
        pass
    if args.once:
        print("[monitor_tdx] mode=once", flush=True)
        try:
            run_once()
        except Exception as e:
            import traceback
            print(f"[monitor_tdx] error: {e}", flush=True)
            traceback.print_exc()
        return
    print(f"[monitor_tdx] mode=loop interval={args.interval}", flush=True)
    while True:
        try:
            run_once()
        except Exception as e:
            import traceback
            print(f"[monitor_tdx] error: {e}", flush=True)
            traceback.print_exc()
        # 不等待，立刻进行下一次（或极短的 args.interval）
        time.sleep(max(1, args.interval))

if __name__ == "__main__":
    _cli()
