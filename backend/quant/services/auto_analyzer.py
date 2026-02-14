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
WX_IMAGE = r"d:\traeProject\backend\quant\services\monitor_images\wx.png"
AVATAR_IMAGE = r"d:\traeProject\backend\quant\services\monitor_images\avtar.png"
AVATAR1_IMAGE = r"d:\traeProject\backend\quant\services\monitor_images\avtar1.png"
SEND_IMAGE = r"d:\traeProject\backend\quant\services\monitor_images\send.png"

# 用于存储上次发送过的预警，避免重复发送 (格式: {stock_code_alert_type: last_date})
SENT_ALERTS = {}

def send_wechat_message(content):
    """通过 pyautogui 模拟微信发送消息给多个联系人"""
    if not content:
        return
    
    # 定义需要发送的联系人头像列表
    target_avatars = [AVATAR_IMAGE, AVATAR1_IMAGE]
    
    try:
        logger.info(f"Attempting to send WeChat message to {len(target_avatars)} targets")
        
        # 1. 点击微信图标 (尝试激活窗口)
        wx_pos = pyautogui.locateCenterOnScreen(WX_IMAGE, confidence=0.8)
        if wx_pos:
            x, y = int(wx_pos.x), int(wx_pos.y)
            logger.info(f"Found WeChat icon at ({x}, {y})")
            pyautogui.click(x, y)
            time.sleep(1)
        else:
            logger.error(f"Could not find WeChat icon on screen using {WX_IMAGE}")
            return

        for avatar_path in target_avatars:
            logger.info(f"Sending to avatar: {os.path.basename(avatar_path)}")
            
            # 2. 点击头像/联系人
            avatar_pos = pyautogui.locateCenterOnScreen(avatar_path, confidence=0.8)
            if avatar_pos:
                ax, ay = int(avatar_pos.x), int(avatar_pos.y)
                logger.info(f"Found Avatar at ({ax}, {ay})")
                # 点击头像选择联系人
                pyautogui.click(ax, ay)
                time.sleep(1)
                
                # 检查是否能找到发送按钮/发送区域标识
                send_pos = pyautogui.locateCenterOnScreen(SEND_IMAGE, confidence=0.8)
                if send_pos:
                    logger.info(f"Found send indicator at {send_pos}, proceeding to send.")
                else:
                    logger.info("Send indicator not found, clicking avatar again to focus input box...")
                    pyautogui.click(ax, ay)
                    time.sleep(0.5)
                
                # 3. 粘贴内容并发送
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
                logger.info(f"Message sent to {os.path.basename(avatar_path)} successfully")
                time.sleep(1) # 两个联系人之间稍作停顿
            else:
                logger.error(f"Could not find Avatar icon on screen using {avatar_path}")
                continue
                
    except Exception as e:
        logger.error(f"Error sending WeChat message: {type(e).__name__}: {e}")
        import traceback
        logger.error(traceback.format_exc())

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
                
                # 返回日期和收盘价的列表
                data = []
                for index, row in latest_df.iterrows():
                    data.append({
                        "date": str(row['date']),
                        "close": float(row['close'])
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
    """获取最新实时股价和名称 (支持多接口重试)"""
    if not is_trade_day():
        logger.info(f"Today is not a trade day, skipping realtime fetch for {stock_code}")
        return None, None

    clean_code = ''.join(filter(str.isdigit, stock_code))
    
    # 优先使用传入的 spot_df (来自 AKShare EM)
    if spot_df is not None and not spot_df.empty:
        try:
            target = spot_df[spot_df['代码'] == clean_code]
            if not target.empty:
                price = float(target.iloc[0]['最新价'])
                name = target.iloc[0]['名称']
                return price, name
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
                if len(parts) > 3:
                    name = parts[0]
                    price = float(parts[3])
                    if price > 0:
                        logger.info(f"Successfully fetched realtime data for {stock_code} via Sina: {price}")
                        return price, name
    except Exception as e:
        logger.error(f"Sina HQ failed for {stock_code}: {e}")

    return None, None

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
            
        # 获取实时价格 (传入 spot_df)
        realtime_price, _ = fetch_realtime_price(code, spot_df=spot_df)
            
        if realtime_price:
            today_str = now.strftime("%Y-%m-%d")
            if full_data and full_data[-1]['date'].startswith(today_str):
                full_data[-1]['close'] = realtime_price
            else:
                full_data.append({
                    "date": now_str,
                    "close": realtime_price
                })
        
        prices = [item["close"] for item in full_data]
        ema12 = calculate_ema(prices, 12)
        ema25 = calculate_ema(prices, 25)
        A1 = [ema12[i] - ema25[i] for i in range(len(prices))]
        A2 = calculate_ema(A1, 6)
        
        all_signals = []
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

        # 预警逻辑
        if len(all_signals) >= 2:
            prev_main, prev_aux = all_signals[-2]
            curr_main, curr_aux = all_signals[-1]
            curr_date_only = now.strftime("%Y-%m-%d")
            
            alert_type = None
            custom_msg = None
            
            if prev_main == "red" and prev_aux == "gray" and curr_aux == "white":
                alert_type = "下降通道"
            elif prev_main == "green" and prev_aux == "yellow" and curr_main == "green" and curr_aux == "gray":
                alert_type = "下降通道"
            elif prev_main == "green" and prev_aux == "gray" and curr_main == "green" and curr_aux == "yellow":
                alert_type = "企稳拉升"
            elif prev_main == "red" and prev_aux == "white" and curr_main == "red" and curr_aux == "gray":
                alert_type = "继续拉升"
                custom_msg = f"{stock_name} {code}, 白点消失，可能继续拉升"
            
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
    # run_analysis("Manual")


if __name__ == "__main__":
    # 独立运行测试
    start_scheduler()
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        pass
