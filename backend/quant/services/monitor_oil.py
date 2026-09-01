import os
import time
import datetime
import pymysql
from typing import Dict, List
from decimal import Decimal

# ===================== 【数据库配置：动态复用 monitor_tdx 的连接参数】 =====================
try:
    from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from quant.services.performance_analysis import DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME

# ===================== 【配置区】自行修改 =====================
DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "user": DB_USER,
    "password": DB_PASSWORD,
    "database": DB_NAME,
    "charset": "utf8mb4"
}

# ===================== 宏观常量阈值配置（模式B：灵敏预警 + 连续N日过滤毛刺） =====================
# 一级警戒线（黄色预警）
Y2_POLICY_THRESHOLD = 4.75     # 2Y 政策利率高位警戒
Y10_LONG_THRESHOLD = 4.80      # 10Y 长期通胀/资本成本警戒线
Y30_FISCAL_THRESHOLD = 5.20    # 30Y 财政供给压力警戒线
# 二级红色高危（二次警报）
Y2_CRITICAL = 5.25
Y10_CRITICAL = 5.30
Y30_CRITICAL = 5.60
# "站稳"定义：连续N个交易日高于阈值（过滤毛刺，3=灵敏, 5=默认, 7=保守）
YIELD_STABLE_WINDOW = 5
# 曲线形态判定：噪声过滤阈值（按品种差异化，单位%）
# 低波动美债收益率序列（y2/y10/y30 的 5日变化差值，单位百分点）
THRESH_TREASURY = 0.035
# 高波动大宗商品（铜/原油的日变化率，单位%）
THRESH_COMMODITY = 0.08
# 兼容旧引用（已弃用，新代码请用 THRESH_TREASURY / THRESH_COMMODITY）
CURVE_DELTA_THRESHOLD = THRESH_TREASURY
# 曲线倒挂阈值（10Y-2Y < 0 即倒挂）
CURVE_INV_THRESHOLD = 0.0
# 利差极度收窄预警（10Y-2Y 低于此值视为平坦化压力）
SPREAD_FLAT_THRESHOLD = 0.25
# 连续天数分级标准（文本展示用）
CONT_CONFIRM_SHORT = 3
CONT_CONFIRM_LONG = 8
# 均线周期（用于对比分析）
MA_SHORT = 5      # 短期均线
MA_MID = 20       # 中期均线
MA_LONG = 60      # 长期均线
HIST_PERCENTILE_WINDOW = 250  # 历史分位数回看窗口

# ===================== 大宗商品宏观V3阈值配置（Brent/WTI/铜组合信号） =====================
# Brent 站稳阈值（美元）
BRENT_HOT_ABOVE = 92       # 高位过热区
BRENT_CRISIS_ABOVE = 100   # 危机级高位
BRENT_COOL_BELOW = 68      # 需求降温区
BRENT_CRISIS_BELOW = 62    # 危机级低位
# WTI 站稳阈值（美元）
WTI_HOT_ABOVE = 89
WTI_CRISIS_ABOVE = 97
WTI_COOL_BELOW = 65
WTI_CRISIS_BELOW = 59
# LME铜阈值（美元）
CU_HOT_ABOVE = 11800       # 高位过热
CU_MILD_BELOW = 9500       # 温和走弱
CU_COOL_BELOW = 9200       # 需求降温
CU_CRISIS_BELOW = 8500     # 危机级走弱
CU_DEEP_BELOW = 8200       # 深度衰退
# Brent-WTI 价差阈值（美元）
SPREAD_GEOPOLITICAL_GT = 7     # 东半球地缘溢价扩大
SPREAD_INVERSION_LT = 0        # 价差倒挂（WTI>Brent）
SPREAD_EXTREME_GT = 10         # 极端溢价
# V3 滚动窗口（交易日）
WIN_BRENT_STD = 20         # Brent 标准窗口
WIN_BRENT_FAST = 15        # Brent 快速窗口
WIN_WTI_STD = 20
WIN_WTI_FAST = 15
WIN_CU_LONG = 25           # 铜长窗口
WIN_CU_STD = 20            # 铜标准窗口
WIN_SPREAD = 12            # 价差窗口
# V3 打分基础分与各组合权重
V3_SCORE_BASE = 50.0
V3_SCORE_COMBO_A_HOT = 12       # 过热需求
V3_SCORE_COMBO_B_MILD = -11     # 温和滞胀
V3_SCORE_COMBO_B_CRISIS = -18   # 危机滞胀
V3_SCORE_COMBO_C_COOL = -12     # 需求降温
V3_SCORE_COMBO_C_CRISIS = -22   # 危机衰退
V3_SCORE_COMBO_D_SPECIAL = 6    # 特殊组合

# ===================== 数据库工具函数 =====================
def get_db_conn():
    """获取mysql连接"""
    return pymysql.connect(**DB_CONFIG)

def init_mysql_tables():
    """初始化研判信号表（原始行情表 macro_market_daily_data 由 monitor_tdx 维护，此处不再创建）"""
    conn = get_db_conn()
    cur = conn.cursor()

    # 宏观研判信号结果表（重构：分层阈值警戒 + 多维对比）
    sql_signal = """
    CREATE TABLE IF NOT EXISTS macro_daily_signal (
        trade_date DATE PRIMARY KEY COMMENT '美东交易日',
        y2_cont_warning INT COMMENT '2Y连续站稳警戒线(4.75)天数',
        y2_cont_critical INT COMMENT '2Y连续站稳红色高危(5.25)天数',
        y10_cont_warning INT COMMENT '10Y连续站稳警戒线(4.80)天数',
        y10_cont_critical INT COMMENT '10Y连续站稳红色高危(5.30)天数',
        y30_cont_warning INT COMMENT '30Y连续站稳警戒线(5.20)天数',
        y30_cont_critical INT COMMENT '30Y连续站稳红色高危(5.60)天数',
        curve_inversion_cont_days INT COMMENT '10Y-2Y倒挂连续天数',
        spread_narrowing_cont INT COMMENT '利差持续收窄天数',
        spread_widening_cont INT COMMENT '利差持续扩大天数',
        curve_type TEXT COMMENT '曲线形态(多周期5/10/30日三窗口判定)',
        inversion_status VARCHAR(256) COMMENT '倒挂状态',
        spread_30y10y_info VARCHAR(256) COMMENT '30Y-10Y期限溢价',
        spread_30y2y_info VARCHAR(256) COMMENT '30Y-2Y全曲线斜率',
        daily_comparison TEXT COMMENT '日度对比(今天vs昨天)',
        short_term_comparison TEXT COMMENT '短期对比(5日均线)',
        long_term_comparison TEXT COMMENT '长期对比(60日均线)',
        spread_change_comparison TEXT COMMENT '利差变化对比',
        yield_level_analysis TEXT COMMENT '收益率水位分析(分层警戒)',
        commodity_comparison TEXT COMMENT '大宗商品对比',
        warning_list TEXT,
        summary TEXT,
        brent_wti_spread FLOAT COMMENT 'Brent-WTI价差(美元)',
        spread_gt7_12d TINYINT COMMENT '价差连续12日>7(地缘溢价扩大)',
        spread_lt0_12d TINYINT COMMENT '价差连续12日倒挂(WTI>Brent)',
        spread_gt10_12d TINYINT COMMENT '价差连续12日>10(极端溢价)',
        comboA_hot_demand TINYINT COMMENT '过热需求组合',
        comboB_mild_stagflation TINYINT COMMENT '温和滞胀组合',
        comboB_crisis_stagflation TINYINT COMMENT '危机滞胀组合',
        combo_c_demand_cool TINYINT COMMENT '需求降温组合',
        comboC_crisis_recession TINYINT COMMENT '危机衰退组合',
        comboD_special TINYINT COMMENT '特殊组合',
        comboE_strong_stagflation_evidence TINYINT COMMENT '强证据供给驱动滞胀',
        signal_B_confidence FLOAT COMMENT 'B组合可信度(0/0.5/1)',
        signal_C_confidence FLOAT COMMENT 'C组合可信度(0/0.5/1)',
        commodity_macro_score_v3 FLOAT COMMENT '大宗商品宏观打分V3(0-100,50中性)',
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    cur.execute(sql_signal)

    # 兼容老库：用 ALTER TABLE 补齐新字段
    upgrade_columns = [
        ("y2_cont_warning", "INT"),
        ("y2_cont_critical", "INT"),
        ("y10_cont_warning", "INT"),
        ("y10_cont_critical", "INT"),
        ("y30_cont_warning", "INT"),
        ("y30_cont_critical", "INT"),
        ("spread_narrowing_cont", "INT"),
        ("spread_widening_cont", "INT"),
        ("daily_comparison", "TEXT"),
        ("short_term_comparison", "TEXT"),
        ("long_term_comparison", "TEXT"),
        ("spread_change_comparison", "TEXT"),
        ("yield_level_analysis", "TEXT"),
        ("commodity_comparison", "TEXT"),
        ("spread_30y2y_info", "VARCHAR(256)"),
        ("brent_wti_spread", "FLOAT"),
        ("spread_gt7_12d", "TINYINT"),
        ("spread_lt0_12d", "TINYINT"),
        ("spread_gt10_12d", "TINYINT"),
        ("comboA_hot_demand", "TINYINT"),
        ("comboB_mild_stagflation", "TINYINT"),
        ("comboB_crisis_stagflation", "TINYINT"),
        ("combo_c_demand_cool", "TINYINT"),
        ("comboC_crisis_recession", "TINYINT"),
        ("comboD_special", "TINYINT"),
        ("comboE_strong_stagflation_evidence", "TINYINT"),
        ("signal_B_confidence", "FLOAT"),
        ("signal_C_confidence", "FLOAT"),
        ("commodity_macro_score_v3", "FLOAT"),
    ]
    for col_name, col_type in upgrade_columns:
        try:
            cur.execute(f"ALTER TABLE macro_daily_signal ADD COLUMN {col_name} {col_type}")
        except pymysql.err.OperationalError as e:
            if e.args[0] != 1060:
                raise

    # curve_type 字段升级：VARCHAR(512) → TEXT（多周期判定字符串变长）
    try:
        cur.execute("ALTER TABLE macro_daily_signal MODIFY COLUMN curve_type TEXT COMMENT '曲线形态(多周期5/10/30日三窗口判定)'")
    except pymysql.err.OperationalError:
        pass

    conn.commit()
    cur.close()
    conn.close()
    print("数据表初始化完成（研判信号表；原始行情读自 macro_market_daily_data）")

# ===================== 读取 macro_market_daily_data 并构建派生指标（利差、涨跌幅） =====================
# 原始行情采集由 monitor_tdx.py 通过豆包抓取并入库 macro_market_daily_data，本模块仅消费

# 数据库字段 → 内部字段（统一映射，避免外部 Decimal 类型污染计算）
_MARKET_FIELDS = ["y2", "y10", "y30", "brent", "wti", "copper"]

def _to_float(v):
    """把 Decimal/None/float 统一转成 float 或 None"""
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)

def load_macro_from_market_data() -> List[dict]:
    """从 macro_market_daily_data 读取6项指标，计算派生指标（利差、涨跌幅）
    - 跳过任一关键字段为 NULL 的行（不参与 prev 链）
    - chg 基于"上一个有效交易日"计算，避免节假日空行污染基准
    """
    conn = get_db_conn()
    cur = conn.cursor(pymysql.cursors.DictCursor)
    sql = """
        SELECT trade_date, y2, y10, y30, brent, wti, copper
        FROM macro_market_daily_data
        ORDER BY trade_date ASC;
    """
    cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    result_list = []
    prev_valid = None  # 上一个"有效交易日"的 data_item（关键字段非空）
    for r in rows:
        y2 = _to_float(r["y2"])
        y10 = _to_float(r["y10"])
        y30 = _to_float(r["y30"])
        brent = _to_float(r["brent"])
        wti = _to_float(r["wti"])
        copper = _to_float(r["copper"])

        spread_10y2y = (y10 - y2) if (y10 is not None and y2 is not None) else None
        spread_30y10y = (y30 - y10) if (y30 is not None and y10 is not None) else None
        spread_30y2y = (y30 - y2) if (y30 is not None and y2 is not None) else None

        # chg 基于"上一个有效交易日"，避免空行作为基准
        y2_chg = (y2 - prev_valid["y2"]) if (prev_valid and y2 is not None and prev_valid["y2"] is not None) else None
        y10_chg = (y10 - prev_valid["y10"]) if (prev_valid and y10 is not None and prev_valid["y10"] is not None) else None
        y30_chg = (y30 - prev_valid["y30"]) if (prev_valid and y30 is not None and prev_valid["y30"] is not None) else None
        brent_chg = (brent - prev_valid["brent"]) if (prev_valid and brent is not None and prev_valid["brent"] is not None) else None
        wti_chg = (wti - prev_valid["wti"]) if (prev_valid and wti is not None and prev_valid["wti"] is not None) else None
        copper_chg = (copper - prev_valid["copper"]) if (prev_valid and copper is not None and prev_valid["copper"] is not None) else None

        data_item = {
            "trade_date": r["trade_date"],
            "y2": y2,
            "y10": y10,
            "y30": y30,
            "spread_10y2y": spread_10y2y,
            "spread_30y10y": spread_30y10y,
            "spread_30y2y": spread_30y2y,
            "brent": brent,
            "wti": wti,
            "copper": copper,
            "y2_chg": y2_chg,
            "y10_chg": y10_chg,
            "y30_chg": y30_chg,
            "brent_chg": brent_chg,
            "wti_chg": wti_chg,
            "copper_chg": copper_chg,
        }
        result_list.append(data_item)

        # 只有当关键利率字段非空时，才更新 prev_valid，作为后续 chg 的基准
        if y2 is not None and y10 is not None and y30 is not None:
            prev_valid = data_item
    return result_list

# ===================== 通用连续天数计算函数 =====================
def calc_consecutive_days(series, threshold, direction="above"):
    """
    计算序列连续突破阈值天数
    :param series: 历史列表 [value1,value2,...] 最新数据放末尾
    :param threshold: 临界值
    :param direction: above / below
    :return: int 连续天数

    健壮性：遇 None 直接中断计数（break），而非跳过（continue）。
    业务上空值代表数据缺失/非交易日，趋势已经断裂，不应"穿透"空值继续累加历史。
    例：[5.3, None, 5.3] 最新为 None，应返回 0（最新交易日数据缺失，趋势断裂），
       而非跳过 None 算出 2。
    注意：当前调用方传入的序列通常已过滤 None，此保护为防御后续改动引入隐患。
    """
    count = 0
    for val in reversed(series):
        if val is None:
            break  # 空值直接中断连续计数，而不是跳过
        if direction == "above":
            if val >= threshold:
                count += 1
            else:
                break
        else:
            if val <= threshold:
                count += 1
            else:
                break
    return count

def calc_consecutive_direction(series):
    """计算序列连续同向变化天数（数据点数语义，与 calc_consecutive_days 一致）
    - 返回 (narrowing_days, widening_days)
    - narrowing: 连续收窄的数据点数（时间序列严格递减，旧值 > 新值）
    - widening:  连续扩大的数据点数（时间序列严格递增，旧值 < 新值）
    - 持平(val == prev_val)视为趋势中断
    - 遇 None 跳过（仅过滤无效数据点，不视为趋势中断）

    修正：原实现首次取最新值时不计数，导致连续N天实际只返回N-1
    例：利差时序 [0.5, 0.45, 0.4]（3个点全部收窄，最新0.4），原返回2，正确应返回3
    现按"数据点数"语义：N个严格同向的数据点返回N
    """
    # 过滤 None，reversed 后最新值在前：[最新, 次新, 更旧, ...]
    valid_vals = [v for v in reversed(series) if v is not None]
    if len(valid_vals) < 2:
        return 0, 0

    # 用最新两个值确定方向（valid_vals[1] 是次新=旧值，valid_vals[0] 是最新=新值）
    diff = valid_vals[1] - valid_vals[0]  # 旧值 - 新值
    if diff > 0:
        # 旧值 > 新值 → 时间序列递减 → 收窄
        direction = "narrowing"
    elif diff < 0:
        # 旧值 < 新值 → 时间序列递增 → 扩大
        direction = "widening"
    else:
        # 持平，趋势无法确立
        return 0, 0

    count = 2  # 前两个值已确认同向，算2个数据点
    prev_val = valid_vals[1]
    for val in valid_vals[2:]:
        if direction == "narrowing":
            # 收窄：旧值 > 新值，即更旧的值应该更大
            if val > prev_val:
                count += 1
            else:
                break
        else:  # widening
            # 扩大：旧值 < 新值，即更旧的值应该更小
            if val < prev_val:
                count += 1
            else:
                break
        prev_val = val

    return (count, 0) if direction == "narrowing" else (0, count)

# ===================== 多周期曲线形态分析（5/10/30/60日四窗口） =====================
def calc_single_shape(delta_y2, delta_y10, delta_spread):
    """单窗口曲线形态判定：利差方向 × 驱动端，四态完备划分（无"震荡"）

    - 熊陡：利差走阔 + 长端上行驱动（期限溢价/财政/长期通胀；即使短端同跌，只要长端上行也归此类）
    - 牛陡：利差走阔 + 短端下行驱动（降息预期主导，鸽派；长端未上行，短端下行更深）
    - 熊平：利差收窄 + 短端上行驱动（美联储鹰派/紧缩；即使长端同涨，只要短端上行也归此类）
    - 牛平：利差收窄 + 长端下行驱动（远期衰退/避险；短端未上行，长端下行更深）

    数学完备性（delta_spread = delta_y10 - delta_y2）：
    - 走阔(>0)且长端未上行(dy10<=0) ⇒ 必有 dy2<dy10<=0，短端下行更深 → 牛陡
    - 收窄(<0)且短端未上行(dy2<=0)  ⇒ 必有 dy10<dy2<=0，长端下行更深 → 牛平
    - 平行移位(==0)：斜率不变，按整体水位方向归并；实际行情几乎不会精确为0
    """
    if delta_spread > 0:
        # 走阔：长端相对短端抬升。长端绝对上行=期限溢价驱动(熊陡)；否则必然短端下行更深(牛陡)
        return "熊陡" if delta_y10 > 0 else "牛陡"
    if delta_spread < 0:
        # 收窄：短端相对长端抬升。短端绝对上行=联储紧缩驱动(熊平)；否则必然长端下行更深(牛平)
        return "熊平" if delta_y2 > 0 else "牛平"
    # 平行移位：斜率不变，仅水位牛熊
    return "熊平" if delta_y2 > 0 else "牛平"

# 形态家族：熊族=利率整体上行（熊陡/熊平），牛族=利率整体下行（牛陡/牛平）
BEAR_FAMILY = {"熊陡", "熊平"}
BULL_FAMILY = {"牛陡", "牛平"}

def shape_family(shape: str) -> str:
    """返回形态所属家族："熊"（利率上行）或"牛"（利率下行）"""
    return "熊" if shape in BEAR_FAMILY else "牛"

def multi_period_curve_analysis(y2_series, y10_series, thresh=THRESH_TREASURY):
    """多周期美债曲线形态分析：5/10/30/60交易日四窗口（无"震荡"，四态完备划分）
    :param y2_series:  2Y收益率序列，list[float]，最新值在末尾
    :param y10_series: 10Y收益率序列，list[float]，最新值在末尾
    :param thresh:     噪声过滤阈值，美债用 THRESH_TREASURY
    :return: dict 或 None（数据不足时返回 None）

    层级设计（长期趋势优先）：
    - 60日 = 长期底层基准：决定大周期牛熊方向（主形态来源）；数据不足时退化到30日
    - 30日 = 中期验证：与基准同向则趋势稳固；反向且非弱信号 → 中期背离（趋势转折预警）
    - 5/10日 = 短期脉冲：与基准反向且非弱信号 → 短期反向脉冲（交易盘博弈，不改变主方向）

    信号分级（避免旧版"30日震荡→无明确趋势"误判）：
    - signal_conflict（短期反向脉冲）：5/10日与基准分属牛/熊不同家族且非弱信号
    - mid_term_divergence（中期背离）：30日与基准分属不同家族且非弱信号
    - driver_rotation（驱动轮动）：同族内陡/平切换，方向不变仅驱动端变化，不构成背离
    - *_weak 弱信号标记：窗口内利差与两端收益率变化均低于噪声阈值，方向成立但幅度有限
    """
    # 安全校验：30窗口至少需要 31 条数据
    min_required = 31
    if not y2_series or not y10_series:
        return None
    if len(y2_series) < min_required or len(y10_series) < min_required:
        return None
    if len(y2_series) != len(y10_series):
        return None

    def get_delta(window):
        y2_now, y2_prev = y2_series[-1], y2_series[-1 - window]
        y10_now, y10_prev = y10_series[-1], y10_series[-1 - window]
        spread_now = y10_now - y2_now
        spread_prev = y10_prev - y2_prev
        return y2_now - y2_prev, y10_now - y10_prev, spread_now - spread_prev

    windows = [5, 10, 30]
    has_60 = len(y2_series) >= 61 and len(y10_series) >= 61
    if has_60:
        windows.append(60)

    shapes, weak, deltas = {}, {}, {}
    for w in windows:
        dy2, dy10, dsp = get_delta(w)
        shapes[w] = calc_single_shape(dy2, dy10, dsp)
        # 弱信号：利差与两端收益率变化均在噪声阈值内（方向由微小符号决定，幅度无意义）
        weak[w] = (abs(dsp) < thresh) and (max(abs(dy2), abs(dy10)) < thresh)
        deltas[w] = (dy2, dy10, dsp)

    # 主周期：优先60日长期基准，数据不足退化到30日
    base_w = 60 if has_60 else 30
    base_shape = shapes[base_w]
    base_family = shape_family(base_shape)

    # 中期背离：30日与基准分属不同家族（弱信号不触发，避免噪声误报趋势转折）
    mid_div = (30 in shapes) and (not weak[30]) and (shape_family(shapes[30]) != base_family)

    # 短期反向脉冲：5/10日与基准分属不同家族且非弱信号
    conflict_shapes = [shapes[w] for w in (5, 10) if w in shapes and (not weak[w]) and (shape_family(shapes[w]) != base_family)]
    pulse_conflict = len(conflict_shapes) > 0

    # 驱动轮动：非背离窗口中存在同族不同形态（陡平切换）
    rotation = any(
        (w in shapes) and (not weak[w]) and (shapes[w] != base_shape) and (shape_family(shapes[w]) == base_family)
        for w in (5, 10, 30)
    )

    # 人读信号注释
    notes = []
    if mid_div:
        notes.append(f"⚠中期背离：30日={shapes[30]}与主周期{base_w}日={base_shape}分属牛/熊不同家族，警惕大趋势内部转折/深度回调")
    if pulse_conflict:
        notes.append(f"⚠短期反向脉冲：5d={shapes.get(5)}/10d={shapes.get(10)}与主周期{base_shape}家族背离，属交易盘短期博弈")
    if rotation and not pulse_conflict and not mid_div:
        notes.append(f"驱动端轮动：5/10/30日在{base_family}族内陡平切换（方向不变，仅驱动端变化）")
    weak_wins = [w for w in windows if weak[w]]
    if weak_wins:
        notes.append("弱信号窗口：" + "、".join(f"{w}日" for w in weak_wins) + "（变化幅度低于噪声阈值，方向刚形成/幅度有限）")
    signal_note = "；".join(notes)

    result = {
        "base_window": base_w,
        "base_shape": base_shape,
        "n5_shape": shapes[5],
        "n10_shape": shapes[10],
        "n30_shape": shapes[30],
        "n5_weak": weak[5],
        "n10_weak": weak[10],
        "n30_weak": weak[30],
        "signal_conflict": pulse_conflict,
        "mid_term_divergence": mid_div,
        "driver_rotation": rotation,
        "signal_note": signal_note,
    }
    if has_60:
        result["n60_shape"] = shapes[60]
        result["n60_weak"] = weak[60]
    for w in windows:
        for key, idx in ((f"delta_y2_{w}", 0), (f"delta_y10_{w}", 1), (f"delta_spread_{w}", 2)):
            result[key] = round(deltas[w][idx], 4)
    return result

# ===================== 操作启示（基于多周期曲线形态） =====================
def get_curve_allocation_note(shape_dict: dict) -> str:
    """基于多周期曲线形态输出股票配置专业文本，纯条件分支，无AI

    结构：主基调（基准形态定方向与配置） + 修正语句（中期背离/短期脉冲/驱动轮动/弱信号）
    - 基准形态 = 60日长期窗口（数据不足退化30日），大周期必有方向（四态完备，无"震荡/无明确趋势"）
    - 方向感知：修正语句按基准形态的牛熊家族给出针对性描述，而非笼统的"短期脉冲"
    """
    if not shape_dict:
        return ""
    base = shape_dict.get("base_shape") or shape_dict.get("n30_shape")
    base_w = shape_dict.get("base_window", 30)
    s5 = shape_dict.get("n5_shape", "")
    s10 = shape_dict.get("n10_shape", "")
    s30 = shape_dict.get("n30_shape", "")
    conflict = shape_dict.get("signal_conflict", False)
    mid_div = shape_dict.get("mid_term_divergence", False)
    rotation = shape_dict.get("driver_rotation", False)
    base_weak = shape_dict.get(f"n{base_w}_weak", False)
    fam = shape_family(base)

    # ---- 主基调：基准形态 → 趋势定性 + 配置方向 ----
    base_note = {
        "熊陡": (f"{base_w}日大周期熊陡（利差走阔+长端上行驱动：期限溢价/财政供给/长期通胀），"
                 "长端利率趋势性上行，压制长久期资产估值。配置：主仓位偏向金融（息差受益）、"
                 "顺周期通胀板块（能源/资源）；高估值科技成长减仓/观望，仅保留现金流扎实的龙头；债券端控制久期"),
        "熊平": (f"{base_w}日大周期熊平（利差收窄+短端上行驱动：联储紧缩），短端利率趋势性上行，"
                 "经济与企业盈利承压风险抬升。配置：防御优先——高股息、必选消费、医药；"
                 "降低成长与顺周期仓位，提高现金与短债占比，控制总权益仓位"),
        "牛陡": (f"{base_w}日大周期牛陡（利差走阔+短端下行驱动：降息预期主导，鸽派），"
                 "流动性环境趋势性改善。配置：长久期科技成长提升仓位；陡峭曲线利好银行；"
                 "可配置黄金对冲衰退风险；密切跟踪后续数据验证降息逻辑"),
        "牛平": (f"{base_w}日大周期牛平（利差收窄+长端下行驱动：远期衰退/避险），"
                 "远期利率趋势性下行，利好长久期资产估值。配置：主仓位偏向科技成长、消费医药防御板块；"
                 "顺周期与金融降低配置；债券可适度拉长久期"),
    }[base]

    # ---- 修正语句：按严重程度叠加（方向感知） ----
    mods = []
    if mid_div:
        mods.append(f"中期背离：30日形态（{s30}）与{base_w}日基准（{base}）分属牛/熊不同家族，"
                    f"大趋势内部出现反向中期运动，若持续需警惕趋势转折，配置调整宜逐步分批而非一次性执行")
    if conflict:
        counter = s5 if shape_family(s5) != fam else s10
        counter_desc = {
            "牛陡": "短期降息博弈", "牛平": "短期避险/衰退交易",
            "熊陡": "短期期限溢价/再通胀交易", "熊平": "短期紧缩定价",
        }.get(counter, "反向交易")
        mods.append(f"短期反向脉冲：5/10日出现{counter}（{counter_desc}），属交易盘博弈，不作为主交易逻辑；"
                    "主仓位维持大周期方向，仅小仓位参与脉冲并严格止损")
    if rotation and not conflict and not mid_div:
        mods.append(f"驱动端轮动：5/10/30日（{s5}/{s10}/{s30}）在{fam}族内陡平切换，方向未变仅驱动端变化，"
                    "无需切换主仓位方向")
    if base_weak:
        mods.append(f"{base_w}日基准窗口变化幅度低于噪声阈值，形态方向刚形成/幅度有限，仓位调整宜渐进分批")

    text = "- 操作启示：" + base_note
    if mods:
        text += "。修正：" + "；".join(mods) + "。\n"
    else:
        text += "。\n"
    return text

# ===================== 大宗商品宏观V3：组合信号 + 打分 =====================
def _rolling_all_true(series, threshold, direction, window):
    """判断最近 window 个交易日是否全部满足条件（等价于 pandas rolling_stay_bool 在最新日的取值）
    - direction: 'gt' 严格大于 / 'lt' 严格小于
    - 遇 None 直接判 False（数据缺失无法构成"全部满足"）
    - 返回 bool
    """
    if series is None or len(series) < window:
        return False
    recent = series[-window:]
    for v in recent:
        if v is None:
            return False
        if direction == "gt" and not (v > threshold):
            return False
        if direction == "lt" and not (v < threshold):
            return False
    return True

def calc_commodity_macro_v3(brent_series, wti_series, cu_series):
    """大宗商品宏观V3 研判（Brent + WTI + LME铜 + Brent-WTI价差）
    :param brent_series: Brent 价格历史（list，最新在末尾）
    :param wti_series:   WTI 价格历史
    :param cu_series:    LME铜价格历史
    :return: dict，含 brent_wti_spread、各 combo 信号(0/1)、confidence(0/0.5/1)、commodity_macro_score_v3

    组合定义：
    - comboA_hot_demand:           Brent高位 + 铜高位 → 过热需求
    - comboB_mild_stagflation:     Brent高位 + 铜温和走弱 → 温和滞胀
    - comboB_crisis_stagflation:   Brent危机高位 + 铜危机走弱 → 危机滞胀
    - combo_c_demand_cool:         Brent低位 + 铜低位 → 需求降温
    - comboC_crisis_recession:     Brent危机低位 + 铜深度衰退 → 危机衰退
    - comboD_special:              Brent低位 + 铜高位 → 特殊组合（供给缓解+需求强）
    - comboE_strong_stagflation_evidence: comboB + 价差>7 → 强证据供给驱动滞胀

    信号可信度：
    - signal_B_confidence: 1=有价差佐证(供给驱动), 0.5=仅comboB, 0=未触发
    - signal_C_confidence: 1=价差不极端(过滤WTI库欣扰动假信号), 0.5=仅comboC, 0=未触发
    """
    brent_latest = brent_series[-1] if brent_series else None
    wti_latest = wti_series[-1] if wti_series else None
    cu_latest = cu_series[-1] if cu_series else None

    # Brent-WTI 价差
    brent_wti_spread = (brent_latest - wti_latest) if (brent_latest is not None and wti_latest is not None) else None

    # ============ 单品种滚动站稳信号 ============
    # Brent
    brent_above_92_20d  = _rolling_all_true(brent_series, BRENT_HOT_ABOVE,    "gt", WIN_BRENT_STD)
    brent_below_68_20d  = _rolling_all_true(brent_series, BRENT_COOL_BELOW,   "lt", WIN_BRENT_STD)
    brent_above_100_15d = _rolling_all_true(brent_series, BRENT_CRISIS_ABOVE, "gt", WIN_BRENT_FAST)
    brent_below_62_20d  = _rolling_all_true(brent_series, BRENT_CRISIS_BELOW, "lt", WIN_BRENT_STD)
    # WTI
    wti_above_89_20d  = _rolling_all_true(wti_series, WTI_HOT_ABOVE,    "gt", WIN_WTI_STD)
    wti_below_65_20d  = _rolling_all_true(wti_series, WTI_COOL_BELOW,   "lt", WIN_WTI_STD)
    wti_above_97_15d  = _rolling_all_true(wti_series, WTI_CRISIS_ABOVE, "gt", WIN_WTI_FAST)
    wti_below_59_20d  = _rolling_all_true(wti_series, WTI_CRISIS_BELOW, "lt", WIN_WTI_STD)
    # 铜
    cu_above_11800_25d = _rolling_all_true(cu_series, CU_HOT_ABOVE,     "gt", WIN_CU_LONG)
    cu_below_9500_25d  = _rolling_all_true(cu_series, CU_MILD_BELOW,    "lt", WIN_CU_LONG)
    cu_below_9200_25d  = _rolling_all_true(cu_series, CU_COOL_BELOW,    "lt", WIN_CU_LONG)
    cu_below_8500_20d  = _rolling_all_true(cu_series, CU_CRISIS_BELOW,  "lt", WIN_CU_STD)
    cu_below_8200_20d  = _rolling_all_true(cu_series, CU_DEEP_BELOW,    "lt", WIN_CU_STD)
    # 价差滚动信号
    spread_series = []
    if brent_wti_spread is not None:
        # 构建价差历史（按 brent/wti 同索引对齐过滤后的有效序列）
        n = min(len(brent_series), len(wti_series))
        for i in range(n):
            b = brent_series[i]
            w = wti_series[i]
            if b is not None and w is not None:
                spread_series.append(b - w)
    spread_gt7_12d  = _rolling_all_true(spread_series, SPREAD_GEOPOLITICAL_GT, "gt", WIN_SPREAD)
    spread_lt0_12d  = _rolling_all_true(spread_series, SPREAD_INVERSION_LT,    "lt", WIN_SPREAD)
    spread_gt10_12d = _rolling_all_true(spread_series, SPREAD_EXTREME_GT,      "gt", WIN_SPREAD)

    # ============ 油铜组合信号 ============
    comboA_hot_demand            = 1 if (brent_above_92_20d  and cu_above_11800_25d) else 0
    comboB_mild_stagflation      = 1 if (brent_above_92_20d  and cu_below_9500_25d)  else 0
    comboB_crisis_stagflation    = 1 if (brent_above_100_15d and cu_below_8500_20d)  else 0
    combo_c_demand_cool          = 1 if (brent_below_68_20d  and cu_below_9200_25d)  else 0
    comboC_crisis_recession      = 1 if (brent_below_62_20d  and cu_below_8200_20d)  else 0
    comboD_special               = 1 if (brent_below_68_20d  and cu_above_11800_25d) else 0
    # V3新增：强证据供给驱动温和滞胀（B + 价差>7）
    comboE_strong_stagflation_evidence = 1 if (comboB_mild_stagflation == 1 and spread_gt7_12d) else 0

    # ============ 信号可信度（0/0.5/1） ============
    if comboB_mild_stagflation == 1 and spread_gt7_12d:
        signal_B_confidence = 1.0
    elif comboB_mild_stagflation == 1:
        signal_B_confidence = 0.5
    else:
        signal_B_confidence = 0.0

    if combo_c_demand_cool == 1 and not spread_gt10_12d:
        signal_C_confidence = 1.0
    elif combo_c_demand_cool == 1:
        signal_C_confidence = 0.5
    else:
        signal_C_confidence = 0.0

    # ============ 基础宏观打分 ============
    score = V3_SCORE_BASE
    if comboA_hot_demand == 1:              score += V3_SCORE_COMBO_A_HOT
    if comboB_mild_stagflation == 1:        score += V3_SCORE_COMBO_B_MILD
    if comboB_crisis_stagflation == 1:      score += V3_SCORE_COMBO_B_CRISIS
    if combo_c_demand_cool == 1:            score += V3_SCORE_COMBO_C_COOL
    if comboC_crisis_recession == 1:        score += V3_SCORE_COMBO_C_CRISIS
    if comboD_special == 1:                 score += V3_SCORE_COMBO_D_SPECIAL
    # 裁剪到 [0, 100]
    score = float(max(0.0, min(100.0, score)))

    return {
        "brent_wti_spread": brent_wti_spread,
        "spread_gt7_12d": 1 if spread_gt7_12d  else 0,
        "spread_lt0_12d": 1 if spread_lt0_12d  else 0,
        "spread_gt10_12d": 1 if spread_gt10_12d else 0,
        "comboA_hot_demand": comboA_hot_demand,
        "comboB_mild_stagflation": comboB_mild_stagflation,
        "comboB_crisis_stagflation": comboB_crisis_stagflation,
        "combo_c_demand_cool": combo_c_demand_cool,
        "comboC_crisis_recession": comboC_crisis_recession,
        "comboD_special": comboD_special,
        "comboE_strong_stagflation_evidence": comboE_strong_stagflation_evidence,
        "signal_B_confidence": signal_B_confidence,
        "signal_C_confidence": signal_C_confidence,
        "commodity_macro_score_v3": score,
    }

def get_cont_status_text(cont_days):
    """连续天数翻译成定性描述"""
    if cont_days <= 0:
        return "未触发"
    elif 1 <= cont_days < CONT_CONFIRM_SHORT:
        return "短期脉冲，观察阶段"
    elif CONT_CONFIRM_SHORT <= cont_days < CONT_CONFIRM_LONG:
        return "初步确认趋势，边际调整仓位"
    else:
        return "趋势正式确立，环境切换"

def _safe_mean(lst):
    """安全求均值（过滤None）"""
    vals = [x for x in lst if x is not None]
    return sum(vals) / len(vals) if vals else None

def _safe_percentile(lst, val):
    """计算 val 在 lst 中的百分位（0-100），None 返回 None"""
    vals = sorted([x for x in lst if x is not None])
    if not vals or val is None:
        return None
    cnt = sum(1 for x in vals if x <= val)
    return round(cnt / len(vals) * 100, 1)

def _yield_level_info(name, val, threshold_warning, threshold_critical, cont_warning, cont_critical, impact_text):
    """统一生成单个期限收益率的水位标签 + 告警文案（消除业务逻辑重复）
    返回 dict:
      label: 展示用文本（"安全区/黄色警戒/红色高危 + 站稳N日确认/毛刺"）
      warn_level: None / "yellow" / "red"
      warn_text: 触发告警时的完整文案（含站稳过滤），未触发为 None
    impact_text: 该期限触发告警时的影响描述（由调用方传入，避免在此处耦合业务话术）
    """
    if val is None:
        return {"label": "数据不足", "warn_level": None, "warn_text": None}
    if val >= threshold_critical:
        is_stable = cont_critical >= YIELD_STABLE_WINDOW
        label = f"红色高危（≥{threshold_critical}）连续{cont_critical}天"
        label += f"，站稳{YIELD_STABLE_WINDOW}日确认" if is_stable else f"，未达站稳{YIELD_STABLE_WINDOW}日（毛刺）"
        warn_text = None
        if is_stable:
            warn_text = f"【红色高危·{name}】{val:.3f}%≥{threshold_critical}，连续站稳{cont_critical}天，{impact_text}"
        return {"label": label, "warn_level": "red" if is_stable else None, "warn_text": warn_text}
    if val >= threshold_warning:
        is_stable = cont_warning >= YIELD_STABLE_WINDOW
        label = f"黄色警戒（≥{threshold_warning}）连续{cont_warning}天"
        label += f"，站稳{YIELD_STABLE_WINDOW}日确认" if is_stable else f"，未达站稳{YIELD_STABLE_WINDOW}日（毛刺）"
        warn_text = None
        if is_stable:
            warn_text = f"【黄色警戒·{name}】{val:.3f}%≥{threshold_warning}，连续站稳{cont_warning}天，{impact_text}"
        return {"label": label, "warn_level": "yellow" if is_stable else None, "warn_text": warn_text}
    return {"label": f"安全区（<{threshold_warning}）", "warn_level": None, "warn_text": None}

# ===================== 核心宏观研判函数（重构：聚焦6项指标+多维对比） =====================
def analyse_macro(data: dict, full_history_list: list):
    """
    宏观流动性环境综合研判函数【精简重构版】
    数据源：y2/y10/y30/brent/wti/copper
    核心模块：曲线形态/倒挂/收益率水位/多维对比/大宗商品
    """
    res = {}
    warn_list = []

    # -------------------------- 基础变量提取 --------------------------
    y2 = data["y2"]
    y10 = data["y10"]
    y30 = data["y30"]
    sp102 = data["spread_10y2y"]
    sp3010 = data["spread_30y10y"]
    sp302 = data["spread_30y2y"]

    brent = data["brent"]
    wti = data["wti"]
    copper = data["copper"]

    y2_chg = data.get("y2_chg")
    y10_chg = data.get("y10_chg")
    y30_chg = data.get("y30_chg")
    brent_chg = data.get("brent_chg")
    wti_chg = data.get("wti_chg")
    copper_chg = data.get("copper_chg")

    # 30Y-2Y 全曲线斜率日变化（=30Y日变化 - 2Y日变化）
    sp302_chg = None
    if y30_chg is not None and y2_chg is not None:
        sp302_chg = y30_chg - y2_chg

    # -------------------------- 时序序列构建 + 连续计数 --------------------------
    hist_y2 = [x["y2"] for x in full_history_list if x["y2"] is not None]
    hist_y10 = [x["y10"] for x in full_history_list if x["y10"] is not None]
    hist_y30 = [x["y30"] for x in full_history_list if x["y30"] is not None]
    hist_sp102 = [x["spread_10y2y"] for x in full_history_list if x["spread_10y2y"] is not None]
    hist_sp3010 = [x["spread_30y10y"] for x in full_history_list if x["spread_30y10y"] is not None]
    hist_sp302 = [x["spread_30y2y"] for x in full_history_list if x["spread_30y2y"] is not None]
    hist_brent = [x["brent"] for x in full_history_list if x["brent"] is not None]
    hist_wti = [x["wti"] for x in full_history_list if x["wti"] is not None]
    hist_copper = [x["copper"] for x in full_history_list if x["copper"] is not None]

    # 分层连续计数：警戒线 + 红色高危，各期限独立统计
    res["y2_cont_warning"] = calc_consecutive_days(hist_y2, Y2_POLICY_THRESHOLD, "above")
    res["y2_cont_critical"] = calc_consecutive_days(hist_y2, Y2_CRITICAL, "above")
    res["y10_cont_warning"] = calc_consecutive_days(hist_y10, Y10_LONG_THRESHOLD, "above")
    res["y10_cont_critical"] = calc_consecutive_days(hist_y10, Y10_CRITICAL, "above")
    res["y30_cont_warning"] = calc_consecutive_days(hist_y30, Y30_FISCAL_THRESHOLD, "above")
    res["y30_cont_critical"] = calc_consecutive_days(hist_y30, Y30_CRITICAL, "above")
    res["curve_inversion_cont_days"] = calc_consecutive_days(hist_sp102, CURVE_INV_THRESHOLD, "below")

    narrowing_days, widening_days = calc_consecutive_direction(hist_sp102)
    res["spread_narrowing_cont"] = narrowing_days
    res["spread_widening_cont"] = widening_days

    # 30Y-2Y 全曲线斜率连续收窄/扩大天数（用于报告展示，不入库新字段）
    sp302_narrowing, sp302_widening = calc_consecutive_direction(hist_sp302)

    # ============ 新增：5日变化，用于曲线形态判定（替代单日chg，消除日噪声） ============
    def get_ndelta(hist_series, n):
        if len(hist_series) <= n:
            return None
        return hist_series[-1] - hist_series[-1-n]

    y2_5d_chg = get_ndelta(hist_y2, 5)
    y10_5d_chg = get_ndelta(hist_y10, 5)

    # ===================== 1、曲线形态判定（多周期：5/10/30/60日四窗口） =====================
    curve_type = "数据不足"
    inversion_status = "无倒挂"
    if sp102 is not None and sp102 < 0:
        inversion_status = f"倒挂，幅度：{sp102:.2f}，连续倒挂{res['curve_inversion_cont_days']}天 | {get_cont_status_text(res['curve_inversion_cont_days'])}"

    # 调用多周期曲线形态分析（60日为长期底层基准，30日为中期验证，5/10日为短期脉冲）
    shape_dict = multi_period_curve_analysis(hist_y2, hist_y10, thresh=THRESH_TREASURY)

    if shape_dict is not None:
        s5, s10, s30 = shape_dict["n5_shape"], shape_dict["n10_shape"], shape_dict["n30_shape"]
        # 形态中文释义映射（四态完备，无"震荡"）
        shape_meaning = {
            "牛平": "牛平（长端下行驱动+利差收窄，远期衰退/避险预期升温）",
            "熊陡": "熊陡（长端上行驱动+利差走阔，期限溢价/财政/长期通胀）",
            "牛陡": "牛陡（短端下行驱动+利差走阔，降息预期主导，鸽派环境）",
            "熊平": "熊平（短端上行驱动+利差收窄，美联储鹰派预期）",
        }
        # 主形态 = 基准窗口（60日长期优先，数据不足退化30日），必有方向
        main_shape = shape_dict["base_shape"]
        main_window = f"{shape_dict['base_window']}日"
        # 弱信号标注（基准窗口幅度低于噪声阈值时明示，而非误报"无趋势"）
        weak_tag = "(弱)" if shape_dict.get(f"n{shape_dict['base_window']}_weak") else ""
        # 各窗口形态展示（弱信号窗口加注）
        def _win_tag(w):
            s = shape_dict[f"n{w}_shape"]
            return f"{s}(弱)" if shape_dict.get(f"n{w}_weak") else s
        win_display = f"5d={_win_tag(5)}/10d={_win_tag(10)}/30d={_win_tag(30)}"
        if "n60_shape" in shape_dict:
            win_display = f"{win_display}/60d={_win_tag(60)}"
        curve_type = f"{shape_meaning[main_shape]}{weak_tag} | 主周期={main_window} | {win_display}"

        # 信号注释（中期背离/短期反向脉冲/驱动轮动/弱信号，见 multi_period_curve_analysis）
        if shape_dict["signal_note"]:
            curve_type += f" | {shape_dict['signal_note']}"

        # 倒挂状态补充
        if sp102 is not None and sp102 < 0:
            if sp102 <= -0.1:
                curve_type += " | 深度倒挂区间"
            else:
                curve_type += " | 轻度倒挂修复中"

        # 30Y远端辅助验证（30日窗口，避免短期噪声）
        dy10_30 = shape_dict["delta_y10_30"]
        # 用 30日窗口重新计算 30Y-10Y 期限溢价变化
        if len(hist_y30) > 30 and len(hist_y10) > 30:
            y30_30d_chg = hist_y30[-1] - hist_y30[-1-30]
            diff_30_10 = y30_30d_chg - dy10_30
            if diff_30_10 > THRESH_TREASURY:
                curve_type += f" | 30Y领涨(期限溢价扩张,+{diff_30_10:.3f}),长端抛压来自财政/长期通胀预期"
            elif diff_30_10 < -THRESH_TREASURY:
                curve_type += f" | 30Y滞涨(期限溢价收窄,{diff_30_10:.3f}),长端驱动集中在10Y段(政策利率预期)"
    else:
        # 数据不足时退化到5日单窗口判定（同样四态完备，无"震荡"）
        if y10 is not None and y2 is not None and y10_5d_chg is not None and y2_5d_chg is not None:
            delta_spread = y10_5d_chg - y2_5d_chg
            shape5 = calc_single_shape(y2_5d_chg, y10_5d_chg, delta_spread)
            weak5 = (abs(delta_spread) < THRESH_TREASURY) and (max(abs(y2_5d_chg), abs(y10_5d_chg)) < THRESH_TREASURY)
            shape_meaning5 = {
                "牛平": "牛平（长端下行驱动+利差收窄，远期衰退/避险预期升温）",
                "熊陡": "熊陡（长端上行驱动+利差走阔，期限溢价/财政/长期通胀）",
                "牛陡": "牛陡（短端下行驱动+利差走阔，降息预期主导，鸽派环境）",
                "熊平": "熊平（短端上行驱动+利差收窄，美联储鹰派预期）",
            }
            weak_tag5 = "(弱)" if weak5 else ""
            curve_type = f"{shape_meaning5[shape5]}{weak_tag5} | 主周期=5日（数据不足31条，退化5日判定）"

    # 保存多周期形态数据到 res（不入库新字段，仅用于报告展示）
    res["_multi_period_shape"] = shape_dict
    res["curve_type"] = curve_type
    res["inversion_status"] = inversion_status

    # 30Y-10Y期限溢价 + 30Y-2Y全曲线斜率
    spread_30y10y_info = "30Y-10Y期限溢价利差：数据不足"
    spread_30y2y_info = "30Y-2Y全曲线斜率：数据不足"
    if sp3010 is not None:
        spread_30y10y_info = f"30Y-10Y期限溢价利差：{sp3010:.3f}"
        if sp3010 > 0.5:
            spread_30y10y_info += "（偏高，长期通胀/财政不确定性溢价大）"
        elif sp3010 < 0:
            spread_30y10y_info += "（倒挂，异常信号，需警惕）"
    if sp302 is not None:
        spread_30y2y_info = f"30Y-2Y全曲线斜率：{sp302:.3f}"
        if sp302 < 0:
            spread_30y2y_info += "【整条曲线倒挂，衰退预警增强】"
    res["spread_30y10y_info"] = spread_30y10y_info
    res["spread_30y2y_info"] = spread_30y2y_info

    # ===================== 2、日度对比（今天 vs 昨天） =====================
    daily_lines = []
    daily_lines.append(f"2Y: {y2:.3f}% (日变化 {y2_chg:+.3f})" if y2 and y2_chg is not None else f"2Y: {y2}")
    daily_lines.append(f"10Y: {y10:.3f}% (日变化 {y10_chg:+.3f})" if y10 and y10_chg is not None else f"10Y: {y10}")
    daily_lines.append(f"30Y: {y30:.3f}% (日变化 {y30_chg:+.3f})" if y30 and y30_chg is not None else f"30Y: {y30}")
    if sp302 is not None:
        # 30Y-2Y 全曲线斜率：日变化 + 连续扩大/收窄观察
        if sp302_chg is not None:
            chg_dir = "扩大" if sp302_chg > 0 else ("收窄" if sp302_chg < 0 else "持平")
            daily_lines.append(f"30Y-2Y利差: {sp302:.3f} (日变化 {sp302_chg:+.3f}, {chg_dir})")
        else:
            daily_lines.append(f"30Y-2Y利差: {sp302:.3f}")
        # 连续观察提示
        if sp302_widening > 0:
            daily_lines.append(f"  └ 30Y-2Y利差连续扩大{sp302_widening}天 | {get_cont_status_text(sp302_widening)}")
        elif sp302_narrowing > 0:
            daily_lines.append(f"  └ 30Y-2Y利差连续收窄{sp302_narrowing}天 | {get_cont_status_text(sp302_narrowing)}")
    if brent is not None:
        daily_lines.append(f"Brent: {brent:.2f} (日变化 {brent_chg:+.2f})" if brent_chg is not None else f"Brent: {brent:.2f}")
    if wti is not None:
        daily_lines.append(f"WTI: {wti:.2f} (日变化 {wti_chg:+.2f})" if wti_chg is not None else f"WTI: {wti:.2f}")
    if copper is not None:
        daily_lines.append(f"铜: {copper:.0f} (日变化 {copper_chg:+.0f})" if copper_chg is not None else f"铜: {copper:.0f}")
    res["daily_comparison"] = "\n".join(daily_lines)

    # ===================== 3、短期对比（5日均线 vs 当前） =====================
    short_lines = []
    for name, val, hist in [("2Y", y2, hist_y2), ("10Y", y10, hist_y10), ("30Y", y30, hist_y30)]:
        ma5 = _safe_mean(hist[-MA_SHORT:]) if len(hist) >= 2 else None
        if val is not None and ma5 is not None:
            dev = val - ma5
            direction = "高于" if dev > 0 else "低于"
            short_lines.append(f"{name}={val:.3f}% vs 5日均线{ma5:.3f}%，{direction}{abs(dev):.3f}")
    if sp302 is not None and len(hist_sp302) >= 2:
        ma5_sp = _safe_mean(hist_sp302[-MA_SHORT:])
        if ma5_sp is not None:
            dev_sp = sp302 - ma5_sp
            direction = "扩张" if dev_sp > 0 else "收窄"
            short_lines.append(f"30Y-2Y利差={sp302:.3f} vs 5日均{ma5_sp:.3f}，短期{direction}{abs(dev_sp):.3f}")
    for name, val, hist in [("Brent", brent, hist_brent), ("WTI", wti, hist_wti), ("铜", copper, hist_copper)]:
        ma5 = _safe_mean(hist[-MA_SHORT:]) if len(hist) >= 2 else None
        if val is not None and ma5 is not None:
            dev = val - ma5
            direction = "高于" if dev > 0 else "低于"
            short_lines.append(f"{name}={val:.2f} vs 5日均{ma5:.2f}，{direction}{abs(dev):.2f}")
    res["short_term_comparison"] = "\n".join(short_lines) if short_lines else "数据不足"

    # ===================== 4、长期对比（60日均线 vs 当前） =====================
    long_lines = []
    for name, val, hist in [("2Y", y2, hist_y2), ("10Y", y10, hist_y10), ("30Y", y30, hist_y30)]:
        ma60 = _safe_mean(hist[-MA_LONG:]) if len(hist) >= 2 else None
        if val is not None and ma60 is not None:
            dev = val - ma60
            direction = "高于" if dev > 0 else "低于"
            trend = "长期上行趋势" if dev > 0.1 else ("长期下行趋势" if dev < -0.1 else "长期震荡")
            long_lines.append(f"{name}={val:.3f}% vs 60日均线{ma60:.3f}%，{direction}{abs(dev):.3f}（{trend}）")
    if sp302 is not None and len(hist_sp302) >= 2:
        ma60_sp = _safe_mean(hist_sp302[-MA_LONG:])
        if ma60_sp is not None:
            dev_sp = sp302 - ma60_sp
            direction = "高于" if dev_sp > 0 else "低于"
            long_lines.append(f"30Y-2Y利差={sp302:.3f} vs 60日均{ma60_sp:.3f}，{direction}{abs(dev_sp):.3f}")
    # 历史分位数
    pct_sp = _safe_percentile(hist_sp302[-HIST_PERCENTILE_WINDOW:], sp302)
    if pct_sp is not None:
        long_lines.append(f"30Y-2Y利差历史分位(近{HIST_PERCENTILE_WINDOW}日): {pct_sp}%")
    for name, val, hist in [("10Y", y10, hist_y10), ("30Y", y30, hist_y30)]:
        pct = _safe_percentile(hist[-HIST_PERCENTILE_WINDOW:], val)
        if pct is not None:
            long_lines.append(f"{name}历史分位(近{HIST_PERCENTILE_WINDOW}日): {pct}%")
    res["long_term_comparison"] = "\n".join(long_lines) if long_lines else "数据不足"

    # ===================== 5、利差变化对比（短期 vs 长期利差变化，基于 30Y-2Y 全曲线斜率） =====================
    spread_change_lines = []
    if len(hist_sp302) >= MA_SHORT + 1:
        sp_now = sp302
        sp_5d_ago = hist_sp302[-(MA_SHORT + 1)]
        sp_20d_ago = hist_sp302[-(MA_MID + 1)] if len(hist_sp302) >= MA_MID + 1 else None
        sp_60d_ago = hist_sp302[-(MA_LONG + 1)] if len(hist_sp302) >= MA_LONG + 1 else None
        if sp_now is not None and sp_5d_ago is not None:
            chg_5d = sp_now - sp_5d_ago
            direction = "扩大" if chg_5d > 0 else "收窄"
            spread_change_lines.append(f"30Y-2Y利差5日变化: {direction}{abs(chg_5d):.3f}（{sp_5d_ago:.3f}→{sp_now:.3f}）")
        if sp_now is not None and sp_20d_ago is not None:
            chg_20d = sp_now - sp_20d_ago
            direction = "扩大" if chg_20d > 0 else "收窄"
            spread_change_lines.append(f"30Y-2Y利差20日变化: {direction}{abs(chg_20d):.3f}（{sp_20d_ago:.3f}→{sp_now:.3f}）")
        if sp_now is not None and sp_60d_ago is not None:
            chg_60d = sp_now - sp_60d_ago
            direction = "扩大" if chg_60d > 0 else "收窄"
            spread_change_lines.append(f"30Y-2Y利差60日变化: {direction}{abs(chg_60d):.3f}（{sp_60d_ago:.3f}→{sp_now:.3f}）")
    # 30Y-2Y 连续扩大/收窄天数（直接展示，覆盖原 10Y-2Y 的 narrowing/widening 字段语义）
    if sp302_narrowing > 0:
        spread_change_lines.append(f"30Y-2Y利差连续收窄{sp302_narrowing}天 | {get_cont_status_text(sp302_narrowing)}")
    if sp302_widening > 0:
        spread_change_lines.append(f"30Y-2Y利差连续扩大{sp302_widening}天 | {get_cont_status_text(sp302_widening)}")
    # 30Y-10Y 期限溢价变化（保留原有，补充中长端视角）
    if len(hist_sp3010) >= MA_SHORT + 1 and sp3010 is not None:
        sp3010_5d_ago = hist_sp3010[-(MA_SHORT + 1)]
        if sp3010_5d_ago is not None:
            chg = sp3010 - sp3010_5d_ago
            direction = "扩张" if chg > 0 else "收窄"
            spread_change_lines.append(f"30Y-10Y期限溢价5日变化: {direction}{abs(chg):.3f}")
    res["spread_change_comparison"] = "\n".join(spread_change_lines) if spread_change_lines else "数据不足"

    # ===================== 6、收益率水位分析（分层警戒 + 站稳过滤毛刺，单一数据源） =====================
    # 统一调用 _yield_level_info：标签 + 告警文案一次生成，消除重复 if 链
    level_specs = [
        ("2Y",  y2,  Y2_POLICY_THRESHOLD,  Y2_CRITICAL,  res["y2_cont_warning"],  res["y2_cont_critical"],  "政策利率高位区间，成长股估值边际承压"),
        ("10Y", y10, Y10_LONG_THRESHOLD,   Y10_CRITICAL, res["y10_cont_warning"], res["y10_cont_critical"], "资本成本上升，长久期成长股/半导体/存储芯片谨慎"),
        ("30Y", y30, Y30_FISCAL_THRESHOLD, Y30_CRITICAL, res["y30_cont_warning"], res["y30_cont_critical"], "财政供给压力，长端融资成本偏高"),
    ]
    level_lines = []
    level_info_cache = {}  # 供后续告警收集复用
    for name, val, tw, tc, cw, cc, impact in level_specs:
        info = _yield_level_info(name, val, tw, tc, cw, cc, impact)
        level_info_cache[name] = info
        level_lines.append(f"{name}={val:.3f}% | {info['label']}（警戒线{tw} / 高危{tc}）" if val is not None else f"{name}=数据不足")
    # 2Y vs 10Y 水位对比
    if y2 is not None and y10 is not None:
        level_gap = y10 - y2
        if level_gap > 1.0:
            level_lines.append(f"10Y-2Y={level_gap:.3f}%，曲线陡峭，长端利率远高于短端（经济预期乐观或通胀预期强）")
        elif level_gap > 0:
            level_lines.append(f"10Y-2Y={level_gap:.3f}%，曲线正常向上倾斜")
        elif level_gap < 0:
            level_lines.append(f"10Y-2Y={level_gap:.3f}%，曲线倒挂，短端利率高于长端（衰退预警）")
    # 站稳过滤说明
    level_lines.append(f"〔站稳定义：连续{YIELD_STABLE_WINDOW}个交易日高于阈值，过滤毛刺；3=灵敏, 5=默认, 7=保守〕")
    res["yield_level_analysis"] = "\n".join(level_lines) if level_lines else "数据不足"

    # ===================== 7、大宗商品对比 =====================
    commodity_lines = []
    for name, val, hist, chg in [("Brent", brent, hist_brent, brent_chg), ("WTI", wti, hist_wti, wti_chg), ("铜", copper, hist_copper, copper_chg)]:
        if val is None:
            continue
        parts = [f"{name}={val:.2f}"]
        if chg is not None:
            parts.append(f"日变化{chg:+.2f}")
        ma5 = _safe_mean(hist[-MA_SHORT:]) if len(hist) >= 2 else None
        ma20 = _safe_mean(hist[-MA_MID:]) if len(hist) >= 2 else None
        ma60 = _safe_mean(hist[-MA_LONG:]) if len(hist) >= 2 else None
        if ma5 is not None:
            parts.append(f"5日均{ma5:.2f}")
        if ma20 is not None:
            parts.append(f"20日均{ma20:.2f}")
        if ma60 is not None:
            parts.append(f"60日均{ma60:.2f}")
        pct = _safe_percentile(hist[-HIST_PERCENTILE_WINDOW:], val)
        if pct is not None:
            parts.append(f"分位{pct}%")
        commodity_lines.append(" | ".join(parts))
    # 原油 vs 铜 同向性分析（用百分比变化率 + THRESH_COMMODITY 过滤噪声）
    if brent_chg is not None and copper_chg is not None and brent and copper:
        brent_pct = brent_chg / brent * 100
        copper_pct = copper_chg / copper * 100
        brent_dir = "up" if brent_pct > THRESH_COMMODITY else ("down" if brent_pct < -THRESH_COMMODITY else "flat")
        copper_dir = "up" if copper_pct > THRESH_COMMODITY else ("down" if copper_pct < -THRESH_COMMODITY else "flat")
        if brent_dir == "up" and copper_dir == "up":
            commodity_lines.append(f"原油+铜同涨：需求侧驱动，经济景气预期升温（Brent {brent_pct:+.3f}% / 铜 {copper_pct:+.3f}%）")
        elif brent_dir == "down" and copper_dir == "down":
            commodity_lines.append(f"原油+铜同跌：需求侧走弱，衰退预期升温（Brent {brent_pct:+.3f}% / 铜 {copper_pct:+.3f}%）")
        elif brent_dir == "up" and copper_dir == "down":
            commodity_lines.append(f"原油涨+铜跌：供给冲击（地缘/OPEC减产），需求并未改善（Brent {brent_pct:+.3f}% / 铜 {copper_pct:+.3f}%）")
        elif brent_dir == "down" and copper_dir == "up":
            commodity_lines.append(f"原油跌+铜涨：供给缓解+需求复苏，良性组合（Brent {brent_pct:+.3f}% / 铜 {copper_pct:+.3f}%）")
        else:
            commodity_lines.append(f"原油/铜方向不一致或未达阈值{THRESH_COMMODITY}%（Brent {brent_pct:+.3f}%[{brent_dir}] / 铜 {copper_pct:+.3f}%[{copper_dir}]）")

    # ===================== V3 大宗商品宏观组合信号 + 打分 =====================
    v3 = calc_commodity_macro_v3(hist_brent, hist_wti, hist_copper)
    res.update(v3)  # 合并 brent_wti_spread / 各 combo / confidence / score_v3

    # V3 价差信息行
    if v3["brent_wti_spread"] is not None:
        sp = v3["brent_wti_spread"]
        spread_flags = []
        if v3["spread_gt7_12d"] == 1:
            spread_flags.append("连续12日>7（地缘溢价扩大）")
        if v3["spread_lt0_12d"] == 1:
            spread_flags.append("连续12日倒挂（WTI>Brent）")
        if v3["spread_gt10_12d"] == 1:
            spread_flags.append("连续12日>10（极端溢价）")
        flag_txt = "；".join(spread_flags) if spread_flags else "无显著异常"
        commodity_lines.append(f"Brent-WTI价差={sp:.2f}美元 | {flag_txt}")

    # V3 组合信号命中展示
    combo_hits = []
    combo_desc = {
        "comboA_hot_demand": "过热需求(A)",
        "comboB_mild_stagflation": "温和滞胀(B)",
        "comboB_crisis_stagflation": "危机滞胀(B+)",
        "combo_c_demand_cool": "需求降温(C)",
        "comboC_crisis_recession": "危机衰退(C+)",
        "comboD_special": "特殊组合(D)",
        "comboE_strong_stagflation_evidence": "强证据供给驱动滞胀(E)",
    }
    for k, desc in combo_desc.items():
        if v3[k] == 1:
            combo_hits.append(desc)
    if combo_hits:
        commodity_lines.append("组合命中: " + "、".join(combo_hits))
    else:
        commodity_lines.append("组合命中: 无（各品种均在中间区间）")

    # 可信度展示
    commodity_lines.append(
        f"信号可信度: B={v3['signal_B_confidence']:.1f}(1=有价差佐证) / C={v3['signal_C_confidence']:.1f}(1=已过滤库欣扰动)"
    )
    commodity_lines.append(f"大宗商品宏观打分V3: {v3['commodity_macro_score_v3']:.1f}（50=中性，<50滞胀/衰退偏空，>50过热偏多）")

    res["commodity_comparison"] = "\n".join(commodity_lines) if commodity_lines else "数据不足"

    # ===================== 风险预警（单一数据源：复用 level_info_cache，不再写第二套 if 链） =====================
    # 红色高危优先于黄色，避免同期限重复告警
    for name in ["2Y", "10Y", "30Y"]:
        info = level_info_cache.get(name)
        if info and info["warn_level"] == "red" and info["warn_text"]:
            warn_list.append(info["warn_text"])
    for name in ["2Y", "10Y", "30Y"]:
        info = level_info_cache.get(name)
        if info and info["warn_level"] == "yellow" and info["warn_text"]:
            warn_list.append(info["warn_text"])

    # 曲线倒挂预警（独立于收益率水位）
    if sp102 is not None and sp102 < 0:
        warn_list.append(f"【倒挂预警】10Y-2Y={sp102:.3f}，连续倒挂{res['curve_inversion_cont_days']}天 | {get_cont_status_text(res['curve_inversion_cont_days'])}，衰退风险升温")
    if sp102 is not None and 0 <= sp102 < SPREAD_FLAT_THRESHOLD:
        warn_list.append(f"【平坦化预警】10Y-2Y={sp102:.3f}，利差极度收窄（<{SPREAD_FLAT_THRESHOLD}），曲线接近倒挂")
    if sp302 is not None and sp302 < 0:
        warn_list.append(f"【全曲线倒挂】30Y-2Y={sp302:.3f}，整条曲线倒挂，强衰退信号")

    # V3 大宗商品预警（基于组合信号 + 可信度）
    if v3["comboB_crisis_stagflation"] == 1:
        warn_list.append("【危机滞胀预警】Brent危机高位+铜危机走弱，大宗商品V3打分显著偏空")
    if v3["comboC_crisis_recession"] == 1:
        warn_list.append("【危机衰退预警】Brent危机低位+铜深度衰退，需求侧全面崩塌")
    if v3["comboE_strong_stagflation_evidence"] == 1:
        warn_list.append("【强证据滞胀预警】温和滞胀组合+Brent-WTI价差>7，供给驱动型滞胀证据强化")
    if v3["comboA_hot_demand"] == 1:
        warn_list.append("【过热需求预警】Brent高位+铜高位，大宗商品V3打分偏多，通胀压力升温")
    res["warning_list"] = warn_list

    # analyse_macro 仅做纯计算，不拼接 summary 文本
    # summary 由 render_summary() 渲染，便于回测/告警复用结构化字段
    return res

# ===================== 文本摘要渲染（与计算解耦） =====================
def render_summary(signal_result: dict, data: dict) -> str:
    """将结构化研判结果渲染为可读文本。
    - 回测/外部调用可直接用 signal_result（dict），无需渲染大文本
    - 推送告警可复用 signal_result['warning_list']
    """
    summary_text = "\n========== 宏观流动性综合研判报告 ==========\n"
    summary_text += f"【交易日】{data['trade_date']}\n"
    summary_text += "\n--- 日度对比(今天vs昨天) ---\n"
    summary_text += signal_result["daily_comparison"] + "\n"
    summary_text += "\n--- 短期对比(5日均线) ---\n"
    summary_text += signal_result["short_term_comparison"] + "\n"
    summary_text += "\n--- 长期对比(60日均线+历史分位) ---\n"
    summary_text += signal_result["long_term_comparison"] + "\n"
    summary_text += "\n--- 利差变化对比 ---\n"
    summary_text += signal_result["spread_change_comparison"] + "\n"
    summary_text += "\n--- 收益率水位分析 ---\n"
    summary_text += signal_result["yield_level_analysis"] + "\n"
    summary_text += "\n--- 大宗商品对比 ---\n"
    summary_text += signal_result["commodity_comparison"] + "\n"

    if len(signal_result["warning_list"]) > 0:
        summary_text += "\n【风险预警】\n"
        for w in signal_result["warning_list"]:
            summary_text += f"- {w}\n"

    summary_text += f"\n【曲线形态】{signal_result['curve_type']}\n"
    summary_text += f"【倒挂状态】{signal_result['inversion_status']}\n"
    summary_text += f"【期限溢价(30Y-10Y)】{signal_result['spread_30y10y_info']}\n"
    summary_text += f"【全曲线斜率(30Y-2Y)】{signal_result['spread_30y2y_info']}\n"
    # V3 大宗商品宏观打分概览（突出展示，详情见大宗商品对比段）
    v3_score = signal_result.get("commodity_macro_score_v3")
    if v3_score is not None:
        bias = "中性"
        if v3_score < 40:
            bias = "偏空（滞胀/衰退）"
        elif v3_score < 50:
            bias = "略偏空"
        elif v3_score > 60:
            bias = "偏多（过热）"
        elif v3_score > 50:
            bias = "略偏多"
        summary_text += f"【大宗商品V3打分】{v3_score:.1f}/100 | {bias}\n"
    # 操作启示（基于多周期曲线形态，追加在最末）
    shape_dict = signal_result.get("_multi_period_shape")
    if shape_dict is not None:
        summary_text += "\n--- 操作启示 ---\n"
        summary_text += get_curve_allocation_note(shape_dict)
    return summary_text

# ===================== 研判结果写入信号表 =====================
def save_signal_to_db(trade_dt, signal_result: dict, summary_text: str):
    """signal_result: 结构化研判 dict（无 summary 字段）
    summary_text: 由 render_summary() 生成的可读文本，单独入库
    """
    conn = get_db_conn()
    cur = conn.cursor()
    warn_str = ";".join(signal_result["warning_list"])
    sql = """
    INSERT INTO macro_daily_signal
    (trade_date,y2_cont_warning,y2_cont_critical,
     y10_cont_warning,y10_cont_critical,
     y30_cont_warning,y30_cont_critical,
     curve_inversion_cont_days,spread_narrowing_cont,spread_widening_cont,
     curve_type,inversion_status,spread_30y10y_info,spread_30y2y_info,
     daily_comparison,short_term_comparison,long_term_comparison,spread_change_comparison,
     yield_level_analysis,commodity_comparison,warning_list,summary,
     brent_wti_spread,spread_gt7_12d,spread_lt0_12d,spread_gt10_12d,
     comboA_hot_demand,comboB_mild_stagflation,comboB_crisis_stagflation,
     combo_c_demand_cool,comboC_crisis_recession,comboD_special,
     comboE_strong_stagflation_evidence,
     signal_B_confidence,signal_C_confidence,commodity_macro_score_v3)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
    y2_cont_warning=VALUES(y2_cont_warning),
    y2_cont_critical=VALUES(y2_cont_critical),
    y10_cont_warning=VALUES(y10_cont_warning),
    y10_cont_critical=VALUES(y10_cont_critical),
    y30_cont_warning=VALUES(y30_cont_warning),
    y30_cont_critical=VALUES(y30_cont_critical),
    curve_inversion_cont_days=VALUES(curve_inversion_cont_days),
    spread_narrowing_cont=VALUES(spread_narrowing_cont),
    spread_widening_cont=VALUES(spread_widening_cont),
    curve_type=VALUES(curve_type),
    inversion_status=VALUES(inversion_status),
    spread_30y10y_info=VALUES(spread_30y10y_info),
    spread_30y2y_info=VALUES(spread_30y2y_info),
    daily_comparison=VALUES(daily_comparison),
    short_term_comparison=VALUES(short_term_comparison),
    long_term_comparison=VALUES(long_term_comparison),
    spread_change_comparison=VALUES(spread_change_comparison),
    yield_level_analysis=VALUES(yield_level_analysis),
    commodity_comparison=VALUES(commodity_comparison),
    warning_list=VALUES(warning_list),
    summary=VALUES(summary),
    brent_wti_spread=VALUES(brent_wti_spread),
    spread_gt7_12d=VALUES(spread_gt7_12d),
    spread_lt0_12d=VALUES(spread_lt0_12d),
    spread_gt10_12d=VALUES(spread_gt10_12d),
    comboA_hot_demand=VALUES(comboA_hot_demand),
    comboB_mild_stagflation=VALUES(comboB_mild_stagflation),
    comboB_crisis_stagflation=VALUES(comboB_crisis_stagflation),
    combo_c_demand_cool=VALUES(combo_c_demand_cool),
    comboC_crisis_recession=VALUES(comboC_crisis_recession),
    comboD_special=VALUES(comboD_special),
    comboE_strong_stagflation_evidence=VALUES(comboE_strong_stagflation_evidence),
    signal_B_confidence=VALUES(signal_B_confidence),
    signal_C_confidence=VALUES(signal_C_confidence),
    commodity_macro_score_v3=VALUES(commodity_macro_score_v3)
    """
    params = (
        trade_dt,
        signal_result["y2_cont_warning"],
        signal_result["y2_cont_critical"],
        signal_result["y10_cont_warning"],
        signal_result["y10_cont_critical"],
        signal_result["y30_cont_warning"],
        signal_result["y30_cont_critical"],
        signal_result["curve_inversion_cont_days"],
        signal_result["spread_narrowing_cont"],
        signal_result["spread_widening_cont"],
        signal_result["curve_type"],
        signal_result["inversion_status"],
        signal_result["spread_30y10y_info"],
        signal_result["spread_30y2y_info"],
        signal_result["daily_comparison"],
        signal_result["short_term_comparison"],
        signal_result["long_term_comparison"],
        signal_result["spread_change_comparison"],
        signal_result["yield_level_analysis"],
        signal_result["commodity_comparison"],
        warn_str,
        summary_text,
        signal_result["brent_wti_spread"],
        signal_result["spread_gt7_12d"],
        signal_result["spread_lt0_12d"],
        signal_result["spread_gt10_12d"],
        signal_result["comboA_hot_demand"],
        signal_result["comboB_mild_stagflation"],
        signal_result["comboB_crisis_stagflation"],
        signal_result["combo_c_demand_cool"],
        signal_result["comboC_crisis_recession"],
        signal_result["comboD_special"],
        signal_result["comboE_strong_stagflation_evidence"],
        signal_result["signal_B_confidence"],
        signal_result["signal_C_confidence"],
        signal_result["commodity_macro_score_v3"],
    )
    cur.execute(sql, params)
    conn.commit()
    cur.close()
    conn.close()

# ===================== 主流程入口 =====================
def main():
    init_mysql_tables()

    # 原始行情由 monitor_tdx.py 维护入库 macro_market_daily_data，本模块直接消费
    print("===== 从 macro_market_daily_data 读取原始行情并构建派生指标 =====")
    full_data_list = load_macro_from_market_data()
    if len(full_data_list) < 2:
        print("历史数据不足，无法执行研判")
        return

    latest_item = None
    for item in reversed(full_data_list):
        if item.get("y2") is not None and item.get("y10") is not None:
            latest_item = item
            break
    if latest_item is None:
        print("⚠️ 数据库中没有包含完整利率数据的记录，无法执行研判")
        return
    trade_date = latest_item["trade_date"]
    print(f"准备执行宏观研判，交易日：{trade_date}")

    signal_res = analyse_macro(latest_item, full_data_list)
    summary_text = render_summary(signal_res, latest_item)

    save_signal_to_db(trade_date, signal_res, summary_text)
    print(summary_text)
    print(f"✅ {trade_date}宏观研判完成并入库")
    return summary_text


if __name__ == "__main__":
    main()
