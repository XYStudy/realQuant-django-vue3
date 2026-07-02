import requests
import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import logging
import akshare as ak
import pyautogui
import pyperclip
import os

# 禁用 ImageNotFoundException，使其返回 None
pyautogui.useImageNotFoundException(False)

# 配置日志
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoAnalyzer")
logger.setLevel(logging.INFO)

# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

# 文件输出 (确保 UTF-8 编码)
file_handler = logging.FileHandler("analyzer_error.log", encoding='utf-8')
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

# 微信预警配置
current_dir = os.path.dirname(os.path.abspath(__file__))
image_dir = os.path.join(current_dir, "monitor_images")

WX_IMAGE = os.path.join(image_dir, "wx.png")
AVATAR_IMAGE = os.path.join(image_dir, "avtar.png")
AVATAR1_IMAGE = os.path.join(image_dir, "avtar1.png")
AVATAR2_IMAGE = os.path.join(image_dir, "avtar2.png")
MSG_FAIL_IMAGE = os.path.join(image_dir, "messageFail.png")
SEND_IMAGE = os.path.join(image_dir, "send.png")
SEND2_IMAGE = os.path.join(image_dir, "send2.png")

# 用于存储上次发送过的预警，避免重复发送 (格式: {stock_code_alert_type: last_date})
SENT_ALERTS = {}

def _safe_locate_center_on_screen(img_path, confidence=0.8):
    """找图前先校验文件存在，避免因缺图直接抛异常中断流程。"""
    if not os.path.exists(img_path):
        logger.warning(f"Image file not found, skipping locate: {img_path}")
        return None

    try:
        return pyautogui.locateCenterOnScreen(img_path, confidence=confidence)
    except Exception as e:
        logger.warning(f"Locate image failed for {img_path}: {type(e).__name__}: {e}")
        return None

def _focus_input_above_send(send_pos, offset_y=20):
    """点击发送按钮上方一点的位置，尽量让聊天输入框获得焦点。"""
    focus_x = int(send_pos.x)
    focus_y = max(int(send_pos.y) - offset_y, 0)
    pyautogui.click(focus_x, focus_y)
    time.sleep(0.5)

def _find_send_indicator(timeout=3.0, step=0.4):
    """在短时间内重复查找发送区标识，优先返回 send2。"""
    end = time.time() + timeout
    while time.time() < end:
        send2_pos = _safe_locate_center_on_screen(SEND2_IMAGE, confidence=0.8)
        if send2_pos:
            return "send2", send2_pos

        send_pos = _safe_locate_center_on_screen(SEND_IMAGE, confidence=0.8)
        if send_pos:
            return "send", send_pos

        time.sleep(step)

    return None, None

def _ensure_chat_input_focused(ax, ay):
    """尽量确保聊天输入框已聚焦，再执行粘贴发送。"""
    indicator_type, indicator_pos = _find_send_indicator(timeout=2.0)
    if indicator_type == "send2":
        logger.info(f"Found send2 indicator at {indicator_pos}, clicking 20px above it to focus input box...")
        _focus_input_above_send(indicator_pos, offset_y=20)
        return True
    if indicator_type == "send":
        logger.info(f"Found send indicator at {indicator_pos}, proceeding to send.")
        return True

    logger.info("Send indicators not found on first pass, clicking avatar once and retrying focus...")
    pyautogui.click(ax, ay)
    time.sleep(1.0)

    indicator_type, indicator_pos = _find_send_indicator(timeout=2.5)
    if indicator_type == "send2":
        logger.info(f"Found send2 indicator after retry at {indicator_pos}, clicking 20px above it to focus input box...")
        _focus_input_above_send(indicator_pos, offset_y=20)
        return True
    if indicator_type == "send":
        logger.info(f"Found send indicator after retry at {indicator_pos}, proceeding to send.")
        return True

    logger.warning("Send indicators still not found after retry; sending may not land in the intended input box.")
    return False

def send_wechat_message(content):
    """通过 pyautogui 模拟微信发送消息给多个联系人"""
    if not content:
        return
    
    # 定义需要发送的联系人头像列表
    target_avatars = [avatar for avatar in [AVATAR_IMAGE, AVATAR1_IMAGE, AVATAR2_IMAGE] if os.path.exists(avatar)]
    
    try:
        logger.info(f"Attempting to send WeChat message to {len(target_avatars)} targets")
        
        # 1. 点击微信图标 (优先 wx.png，找不到则回退到 wx2.png)
        wx_pos = None
        wx_image_used = None
        for wx_image in [WX_IMAGE]:
            wx_pos = _safe_locate_center_on_screen(wx_image, confidence=0.8)
            if wx_pos:
                wx_image_used = wx_image
                break

        if wx_pos:
            x, y = int(wx_pos.x), int(wx_pos.y)
            logger.info(f"Found WeChat icon via {os.path.basename(wx_image_used)} at ({x}, {y})")
            pyautogui.click(x, y)
            time.sleep(1)
        else:
            logger.error(f"Could not find WeChat icon on screen using {WX_IMAGE}")
            return

        for avatar_path in target_avatars:
            logger.info(f"Sending to avatar: {os.path.basename(avatar_path)}")
            
            # 2. 点击头像/联系人
            avatar_pos = _safe_locate_center_on_screen(avatar_path, confidence=0.8)
            if not avatar_pos and wx_pos:
                logger.info(f"{os.path.basename(avatar_path)} not found after WeChat activation, clicking {os.path.basename(wx_image_used)} once more and retrying...")
                pyautogui.click(x, y)
                time.sleep(1)
                avatar_pos = _safe_locate_center_on_screen(avatar_path, confidence=0.8)

            if avatar_pos:
                ax, ay = int(avatar_pos.x), int(avatar_pos.y)
                logger.info(f"Found Avatar at ({ax}, {ay})")
                pyautogui.click(ax, ay)
                time.sleep(1)
                
                # 先尽量确认输入框已聚焦，避免后续粘贴落到错误位置。
                input_focused = _ensure_chat_input_focused(ax, ay)
                
                # 3. 粘贴内容并发送
                def _do_paste_and_send():
                    pyperclip.copy(content)
                    time.sleep(0.5)
                    # 确保输入框干净
                    pyautogui.hotkey('ctrl', 'a')
                    time.sleep(0.3)
                    pyautogui.press('backspace')
                    time.sleep(0.3)
                    # 粘贴
                    pyautogui.hotkey('ctrl', 'v')
                    time.sleep(1)
                    # 发送
                    pyautogui.press('enter')
                
                _do_paste_and_send()
                
                # 检查是否发送失败 (出现了 messageFail.png)
                time.sleep(2)
                fail_pos = _safe_locate_center_on_screen(MSG_FAIL_IMAGE, confidence=0.8)
                if fail_pos:
                    logger.warning(f"Message send failed (found {os.path.basename(MSG_FAIL_IMAGE)}), clicking to clear and retrying...")
                    pyautogui.click(int(fail_pos.x), int(fail_pos.y))
                    time.sleep(1)
                    # 再次点击头像确保焦点
                    pyautogui.click(ax, ay)
                    time.sleep(0.5)
                    # 重试发送
                    _do_paste_and_send()
                    logger.info(f"Retry attempt finished for {os.path.basename(avatar_path)}")
                
                if input_focused:
                    logger.info(f"Send action completed for {os.path.basename(avatar_path)}")
                else:
                    logger.warning(f"Send action completed for {os.path.basename(avatar_path)}, but input focus was not confirmed")
                time.sleep(1) # 两个联系人之间稍作停顿
            else:
                logger.error(f"Could not find Avatar icon on screen using {avatar_path}")
                continue
                
    except Exception as e:
        logger.error(f"Error sending WeChat message: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

# 配置区域
# 配置区域
STOCK_CODES = ['300169','300065','603881','600710','603069','000901','000021','600592','600150','300627','002703','300019','600006','600718','000421']  # 股票代码数组
EXECUTION_TIMES = ["11:00", "14:00"]  # 执行时间数组

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://quote.eastmoney.com/"
}

def calculate_ema(prices, period):
    """
    计算指数移动平均线（EMA），严格对齐通达信/TradingView 行为
    - 前 period-1 个值返回 0（或 None）
    - 第 period 个值 = SMA(period)
    - 之后使用 EMA 递推公式
    """
    if not prices or len(prices) < period:
        return [0.0] * len(prices)
    
    ema = [0.0] * len(prices)
    
    # 第 period 天：用 SMA 作为初始 EMA
    sma = sum(prices[:period]) / period
    ema[period - 1] = sma
    
    # 从第 period+1 天开始递推
    multiplier = 2 / (period + 1)
    for i in range(period, len(prices)):
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1]
    
    return ema

def get_secid(stock_code):
    """根据股票代码获取东财 API 所需的 secid"""
    code_str = str(stock_code).strip().lower()
    clean_code = code_str
    if code_str.startswith(('sh', 'sz', 'bj')):
        clean_code = code_str[2:]
    
    if clean_code.startswith(('60', '688', '689')):
        return f"1.{clean_code}"
    elif clean_code.startswith(('00', '30', '002', '8', '4', '9')):
        return f"0.{clean_code}"
    else:
        if code_str.startswith('sh'):
            return f"1.{clean_code}"
        else:
            return f"0.{clean_code}"

def fetch_historical_prices(stock_code, limit=300):
    """获取股票历史收盘价 (获取 300 条以供 EMA 充分稳定)"""
    # Sina 接口需要 sh600519 这种格式，STOCK_CODES 已经是这种格式
    # 如果是纯数字，需要补全前缀
    if stock_code.isdigit():
        if stock_code.startswith('6'):
            stock_code = 'sh' + stock_code
        else:
            stock_code = 'sz' + stock_code
            
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # 获取日线行情，使用前复权
            # 往前推 450 天确保有足够的交易日数据
            start_date = (datetime.now() - timedelta(days=450)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            
            # stock_zh_a_daily 默认使用新浪接口，通常不会被封 IP
            df = ak.stock_zh_a_daily(symbol=stock_code, 
                                     start_date=start_date, end_date=end_date, 
                                     adjust="qfq")
            
            if not df.empty:
                # 获取最后 limit 条数据
                latest_df = df.tail(limit)
                
                # 返回日期、收盘价和成交量的列表
                data = []
                for index, row in latest_df.iterrows():
                    data.append({
                        "date": str(row['date']),
                        "open": float(row['open']),
                        "close": float(row['close']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "volume": float(row['volume'])
                    })
                
                logger.info(f"Successfully fetched {len(data)} historical prices for {stock_code} via AKShare(Sina)")
                return data
            
            logger.warning(f"Attempt {attempt + 1} returned empty data for {stock_code} via AKShare(Sina)")
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} error for {stock_code} using AKShare(Sina): {e}")
        
        time.sleep(0.5)
    return []

def is_trade_day():
    """判断今天是否为交易日"""
    try:
        # 获取交易日历
        df_trade_date = ak.tool_trade_date_hist_sina()
        trade_dates = df_trade_date['trade_date'].tolist()
        today = datetime.now().date()
        return today in trade_dates
    except Exception as e:
        logger.error(f"Error checking trade day: {e}")
        # 如果获取失败，保守起见判断是否为周六日
        return datetime.now().weekday() < 5

def get_stock_name(stock_code):
    """获取股票名称 (支持非交易日)"""
    clean_code = ''.join(filter(str.isdigit, stock_code))
    try:
        # 使用新浪接口获取名称，通常比较稳定且支持周末
        url = f"http://hq.sinajs.cn/list=sh{clean_code}" if clean_code.startswith('6') else f"http://hq.sinajs.cn/list=sz{clean_code}"
        headers = {"Referer": "http://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'gbk'  # 新浪接口通常使用 GBK 编码
        if resp.status_code == 200 and '="' in resp.text:
            content = resp.text.split('="')[1]
            if content:
                return content.split(',')[0]
    except Exception as e:
        logger.error(f"Error fetching stock name from Sina for {stock_code}: {e}")
    
    try:
        # 备选方案：ak.stock_info_a_code_name
        df = ak.stock_info_a_code_name()
        if not df.empty:
            target = df[df['code'] == clean_code]
            if not target.empty:
                return target.iloc[0]['name']
    except Exception as e:
        logger.error(f"Error fetching stock name from AKShare for {stock_code}: {e}")
        
    return stock_code

def fetch_realtime_price(stock_code, spot_df=None):
    """获取最新实时股价、名称和成交量 (支持多接口重试)"""
    if not is_trade_day():
        logger.info(f"Today is not a trade day, skipping realtime fetch for {stock_code}")
        return None, None, None, None, None, None

    clean_code = ''.join(filter(str.isdigit, stock_code))
    
    # 优先使用传入的 spot_df (来自 AKShare EM)
    if spot_df is not None and not spot_df.empty:
        try:
            target = spot_df[spot_df['代码'] == clean_code]
            if not target.empty:
                price = float(target.iloc[0]['最新价'])
                name = target.iloc[0]['名称']
                volume = float(target.iloc[0]['成交量'])
                open_p = float(target.iloc[0]['今开'])
                high_p = float(target.iloc[0]['最高'])
                low_p = float(target.iloc[0]['最低'])
                return price, name, volume, open_p, high_p, low_p
        except Exception as e:
            logger.warning(f"Error extracting data from spot_df for {stock_code}: {e}")
    
    # 如果 spot_df 无效，则使用 Sina HQ 作为备选 (按需获取，速度快)
    try:
        symbol = f"sh{clean_code}" if clean_code.startswith('6') else f"sz{clean_code}"
        url = f"http://hq.sinajs.cn/list={symbol}"
        headers = {"Referer": "http://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'gbk'  # 显式指定 GBK 编码
        if resp.status_code == 200 and '="' in resp.text:
            content = resp.text.split('="')[1]
            if content:
                parts = content.split(',')
                if len(parts) > 30:
                    name = parts[0]
                    open_p = float(parts[1])
                    price = float(parts[3])
                    high_p = float(parts[4])
                    low_p = float(parts[5])
                    volume = float(parts[8])
                    if price > 0:
                        logger.info(f"Successfully fetched realtime data for {stock_code} via Sina: {price}, vol: {volume}")
                        return price, name, volume, open_p, high_p, low_p
    except Exception as e:
        logger.error(f"Sina HQ failed for {stock_code}: {e}")

    return None, None, None, None, None, None

def check_long_upper_shadow(open_price, high_price, low_price, close_price):
    """
    判断当天是否出现长上影线
    参数:
        open_price: 开盘价
        high_price: 最高价
        low_price: 最低价
        close_price: 收盘价
    返回:
        dict: 包含判断结果和操作提示
    """
    
    # ========== 1. 计算上影线、下影线、实体 ==========
    if close_price >= open_price:  # 阳线
        upper_shadow = high_price - close_price
        lower_shadow = open_price - low_price
        body = close_price - open_price
        candle_type = "阳线"
    else:  # 阴线
        upper_shadow = high_price - open_price
        lower_shadow = close_price - low_price
        body = open_price - close_price
        candle_type = "阴线"
    
    total_range = high_price - low_price
    
    # 避免除以0
    if total_range == 0:
        return {
            'is_long_shadow': False,
            'signal': '无波动',
            'action': '观望',
            'reason': '当日无价格波动'
        }
    
    # ========== 2. 计算上影线占比 ==========
    shadow_ratio = upper_shadow / total_range  # 上影线占整根K线的比例
    
    # ========== 3. 判断是否长上影线 ==========
    # 条件1：上影线占比 ≥ 60%
    # 条件2：上影线长度 ≥ 实体长度的2倍
    # 条件3：下影线 < 上影线的50%（可选，增强信号）
    
    is_long = (
        shadow_ratio >= 0.6 and
        (body == 0 or upper_shadow >= body * 2) and
        lower_shadow < upper_shadow * 0.5
    )
    
    # ========== 4. 生成信号和提示 ==========
    if is_long and shadow_ratio >= 0.7:
        signal = "🔴 强烈长上影"
        action = "建议卖出/减仓"
        reason = f"上影线占比{shadow_ratio:.1%}，抛压沉重，短期可能回调"
    elif is_long and shadow_ratio >= 0.6:
        signal = "🟠 长上影线"
        action = "建议逢高减仓"
        reason = f"上影线占比{shadow_ratio:.1%}，上方遇阻，注意风险"
    elif shadow_ratio >= 0.5:
        signal = "🟡 上影线偏长"
        action = "谨慎持有"
        reason = f"上影线占比{shadow_ratio:.1%}，有一定压力"
    else:
        signal = "🟢 正常K线"
        action = "正常操作"
        reason = f"上影线占比{shadow_ratio:.1%}，无明显压力"
    
    return {
        'is_long_shadow': is_long,
        'candle_type': candle_type,
        'shadow_ratio': shadow_ratio,
        'upper_shadow': upper_shadow,
        'lower_shadow': lower_shadow,
        'body': body,
        'signal': signal,
        'action': action,
        'reason': reason
    }

def run_analysis(scheduled_time=None):
    """执行分析任务"""
    now = datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"Starting analysis at {now_str} (Scheduled: {scheduled_time})")
    all_alert_messages = []
    
    # 获取当前是哪个执行时间点，用于去重
    current_window = scheduled_time if scheduled_time else now.strftime("%H:%M")
    
    # 提前获取一次全市场实时行情 (AKShare EM)，减少循环内的网络请求
    spot_df = None
    if is_trade_day():
        for attempt in range(2):
            try:
                logger.info(f"Fetching market spot data (Attempt {attempt+1})...")
                spot_df = ak.stock_zh_a_spot_em()
                if spot_df is not None and not spot_df.empty:
                    logger.info("Market spot data fetched successfully.")
                    break
            except Exception as e:
                logger.warning(f"Failed to fetch market spot data: {e}")
                time.sleep(1)

    for code in STOCK_CODES:
        logger.info(f"Analyzing {code}...")
        # 获取历史数据
        full_data = fetch_historical_prices(code, limit=500)
        time.sleep(0.1) # 稍微缩短等待时间
        
        if not full_data:
            logger.error(f"Failed to fetch historical data for {code}")
            continue
            
        # 获取股票名称
        stock_name = get_stock_name(code)
            
        # 获取实时价格和成交量 (传入 spot_df)
        realtime_price, _, realtime_vol, open_p, high_p, low_p = fetch_realtime_price(code, spot_df=spot_df)
            
        if realtime_price:
            today_str = now.strftime("%Y-%m-%d")
            if full_data and full_data[-1]['date'].startswith(today_str):
                full_data[-1]['close'] = realtime_price
                if realtime_vol:
                    full_data[-1]['volume'] = realtime_vol
                # 更新 OHLC 数据 (如果获取到)
                if open_p: full_data[-1]['open'] = open_p
                if high_p: full_data[-1]['high'] = high_p
                if low_p: full_data[-1]['low'] = low_p
            else:
                full_data.append({
                    "date": now_str,
                    "close": realtime_price,
                    "volume": realtime_vol if realtime_vol else 0,
                    "open": open_p if open_p else realtime_price, # 缺省用 close
                    "high": high_p if high_p else realtime_price,
                    "low": low_p if low_p else realtime_price
                })
        
        # 长上影线判断逻辑 (使用 full_data[-1]，兼容历史数据和实时数据)
        if full_data and len(full_data) > 0:
            last_candle = full_data[-1]
            c_open = last_candle.get('open')
            c_high = last_candle.get('high')
            c_low = last_candle.get('low')
            c_close = last_candle.get('close')
            
            if c_open and c_high and c_low and c_close:
                 shadow_result = check_long_upper_shadow(c_open, c_high, c_low, c_close)
                 if shadow_result['is_long_shadow']:
                     alert_type = shadow_result['signal']
                     custom_msg = f"{stock_name} {code}，{shadow_result['signal']}，{shadow_result['action']}，{shadow_result['reason']}"
                     
                     # 修改去重逻辑：同一个时间点（11:00 或 14:00）只发一次
                     alert_key = f"{code}_{alert_type}_{current_window}_{curr_date_only}"
                     if alert_key not in SENT_ALERTS:
                        msg = custom_msg
                        all_alert_messages.append(msg)
                        SENT_ALERTS[alert_key] = True
                        logger.info(f"ALERT TRIGGERED for {code}: {msg}")

        prices = [item["close"] for item in full_data]
        volumes = [item.get("volume", 0) for item in full_data]
        ema12 = calculate_ema(prices, 12)
        ema25 = calculate_ema(prices, 25)
        A1 = [ema12[i] - ema25[i] for i in range(len(prices))]
        A2 = calculate_ema(A1, 6)
        
        all_signals = []
        logger.info(f"--- {stock_name}({code}) Signal Calculation Details (Latest 10 days) ---")
        for i in range(len(full_data)):
            if A1[i] >= 0: main_color = "red" 
            else: main_color = "green" 
            
            if A1[i] > 0 and A2[i] < 0: aux_color = "yellow"
            elif A1[i] < 0 and A2[i] >= 0: aux_color = "white"
            elif (abs(A1[i]) == abs(A2[i]) and A1[i] < 0) or abs(A1[i]) > abs(A2[i]): aux_color = "gray"
            else:
                if A2[i] >= 0: aux_color = "white"
                else: aux_color = "yellow" 
            all_signals.append((main_color, aux_color))
            
            # 打印每天的计算数值和颜色结果
            print(f"Date: {full_data[i]['date']}, A1: {A1[i]:.4f}, A2: {A2[i]:.4f}, Main: {main_color}, Aux: {aux_color}")
        logger.info(f"--- End of Signal Details ---")

        # 预警逻辑
        if len(all_signals) >= 2:
            prev_main, prev_aux = all_signals[-2]
            curr_main, curr_aux = all_signals[-1]
            curr_date_only = now.strftime("%Y-%m-%d")
            
            alert_type = None
            custom_msg = None
            
            if prev_main == "red" and prev_aux == "gray" and curr_aux == "white":
                alert_type = "下降通道"
                custom_msg = f"{stock_name} {code}，下降通道，请分批逢高减仓"
            elif prev_main == "green" and prev_aux == "yellow" and curr_main == "green" and curr_aux == "gray":
                alert_type = "下降通道"
                custom_msg = f"{stock_name} {code}，下降通道，请分批逢高减仓"
            elif prev_main == "green" and prev_aux == "gray" and curr_main == "green" and curr_aux == "yellow":
                alert_type = "企稳拉升"
                custom_msg = f"{stock_name} {code}，开始企稳了！请逢低买入或放量突破时买入！"
            elif prev_main == "red" and prev_aux == "white" and curr_main == "red" and curr_aux == "gray":
                alert_type = "继续拉升"
                custom_msg = f"{stock_name} {code}, 白点消失，可能继续拉升"
            
            # 新增：连续两天/三天/四天白点判断
            if len(all_signals) >= 4:
                s4_main, s4_aux = all_signals[-4]
                s3_main, s3_aux = all_signals[-3]
                s2_main, s2_aux = all_signals[-2]
                s1_main, s1_aux = all_signals[-1] # Current
                
                # 连续四天逻辑：第一天 Gray，后三天 White (Red + White)
                if (s4_main == "red" and s4_aux == "gray" and
                    s3_main == "red" and s3_aux == "white" and
                    s2_main == "red" and s2_aux == "white" and
                    s1_main == "red" and s1_aux == "white"):
                    alert_type = "清仓预警"
                    custom_msg = f"{stock_name} {code}，下降通道，连续三天出现白点，请及时清仓，等待反转信号"
                
                # 连续两天白点 (前天 Gray -> 昨天 White -> 今天 White)
                elif (s3_main == "red" and s3_aux == "gray" and
                      s2_main == "red" and s2_aux == "white" and
                      s1_main == "red" and s1_aux == "white"):
                    alert_type = "减仓预警"
                    custom_msg = f"{stock_name} {code}，下降通道，连续两天出现白点，请继续逢高减仓"
            
            # 兼容数据不足4天但足3天的情况
            elif len(all_signals) == 3:
                s3_main, s3_aux = all_signals[-3]
                s2_main, s2_aux = all_signals[-2]
                s1_main, s1_aux = all_signals[-1] # Current
                 
                # 连续三天白点 (Red + White)
                if (s3_main == "red" and s3_aux == "white" and
                    s2_main == "red" and s2_aux == "white" and
                    s1_main == "red" and s1_aux == "white"):
                    alert_type = "清仓预警"
                    custom_msg = f"{stock_name} {code}，下降通道，连续三天出现白点，请及时清仓，等待反转信号"
                
                # 连续两天白点 (前天 Gray -> 昨天 White -> 今天 White)
                elif (s3_main == "red" and s3_aux == "gray" and
                      s2_main == "red" and s2_aux == "white" and
                      s1_main == "red" and s1_aux == "white"):
                    alert_type = "减仓预警"
                    custom_msg = f"{stock_name} {code}，下降通道，连续两天出现白点，请继续逢高减仓"

            # 新增：成交量翻倍且绿柱变窄判断
            if len(volumes) >= 2 and len(A1) >= 2:
                prev_vol = volumes[-2]
                curr_vol = volumes[-1]
                # 绿色柱体变窄：前后期都是绿柱 (A1 < 0)，且后期值大于前期值 (更接近0)
                if prev_main == "green" and curr_main == "green" and A1[-1] > A1[-2]:
                    # 情况1：成交量翻倍
                    if prev_vol > 0 and curr_vol >= 2 * prev_vol:
                        alert_type = "急速补仓"
                        custom_msg = f"{stock_name} {code}, 绿柱变窄，成交量翻倍，极其可能下跌末期，上涨初期，建议急速补仓！"
                    # 情况2：涨幅大于 5%
                    elif len(prices) >= 2:
                        prev_close = prices[-2]
                        curr_price = prices[-1]
                        if prev_close > 0:
                            change_pct = (curr_price - prev_close) / prev_close
                            if change_pct > 0.05:
                                alert_type = "强势买入"
                                custom_msg = f"{stock_name} {code}, 绿柱变窄，股价上涨幅度大于5%，强势买入！"
                
                # 红色趋势中白柱变窄：前后期都是红柱 (A1 >= 0)，且后期值大于前期值 (向上拐头/修复)
                elif prev_main == "red" and curr_main == "red" and curr_aux == "white" and A1[-1] > A1[-2]:
                    if prev_vol > 0 and curr_vol >= 2 * prev_vol:
                        alert_type = "急速补仓"
                        custom_msg = f"{stock_name} {code}, 白柱变窄，成交量翻倍，极其可能反转继续拉升，建议急速补仓！"
                
                # 新增：连续三天成交量缩量且 Main: red, Aux: gray 判断
                if len(all_signals) >= 3 and len(volumes) >= 3:
                    s3_main, s3_aux = all_signals[-3]
                    s2_main, s2_aux = all_signals[-2]
                    s1_main, s1_aux = all_signals[-1]
                    v3, v2, v1 = volumes[-3], volumes[-2], volumes[-1]
                    
                    if (s3_main == "red" and s3_aux == "gray" and
                        s2_main == "red" and s2_aux == "gray" and
                        s1_main == "red" and s1_aux == "gray"):
                        if v1 < v2 < v3:
                            alert_type = "缩量偏离"
                            custom_msg = f"{stock_name} {code}，连续三天成交量缩量，请观察5日线，如偏离5日线过多请减仓！"
            
            if alert_type:
                # 修改去重逻辑：同一个时间点（11:00 或 14:00）只发一次
                # 如果是手动运行，current_window 是当前时间
                alert_key = f"{code}_{alert_type}_{current_window}_{curr_date_only}"
                if alert_key not in SENT_ALERTS:
                    msg = custom_msg if custom_msg else f"{stock_name} {code}，开始{alert_type}了！"
                    all_alert_messages.append(msg)
                    SENT_ALERTS[alert_key] = True
                    logger.info(f"ALERT TRIGGERED for {code}: {msg}")

    # 发送微信
    if all_alert_messages:
        combined_msg = f"【预警报告 {current_window}】\n" + "\n".join(all_alert_messages)
        send_wechat_message(combined_msg)
    else:
        send_wechat_message(f"分析完成 ({now_str})：当前监控的股票暂无新信号。")

def start_scheduler():
    """启动调度器"""
    scheduler = BackgroundScheduler()
    
    # 启用定时任务：11:00 和 14:00
    for t_str in EXECUTION_TIMES:
        hour, minute = map(int, t_str.split(':'))
        # 使用 lambda 传递预定时间字符串
        scheduler.add_job(lambda t=t_str: run_analysis(t), 'cron', hour=hour, minute=minute)
        logger.info(f"Added scheduled job for {t_str}")
    
    scheduler.start()
    logger.info("Scheduler started.")
    
    # 首次运行一次
    run_analysis("Manual")


if __name__ == "__main__":
    # 独立运行测试
    start_scheduler()
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
