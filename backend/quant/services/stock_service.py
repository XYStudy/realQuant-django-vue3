import random
from datetime import datetime
import time
import requests
from decimal import Decimal

class StockDataService:
    """
    股票数据服务类，用于获取和处理股票数据
    """
    
    @staticmethod
    def get_stock_data(stock_code):
        """
        获取股票实时数据（支持沪市/深市/北交所）
        """
        # --- 优化后的股票代码解析逻辑 ---
        code_str = str(stock_code).strip().lower()
        
        # 去掉 sh/sz 这种前缀
        clean_code = code_str
        if code_str.startswith(('sh', 'sz', 'bj')):
            clean_code = code_str[2:]
        
        # 确定市场前缀 (secid)
        # 沪市: 1.xxxxxx, 深市/北交所: 0.xxxxxx
        if clean_code.startswith(('60', '688', '689')):
            secid = f"1.{clean_code}"  # 沪市
        elif clean_code.startswith(('00', '30', '002', '8', '4', '9')):
            secid = f"0.{clean_code}"  # 深市/创业板/北交所
        else:
            # 如果无法确定，尝试根据原始输入的前缀判断
            if code_str.startswith('sh'):
                secid = f"1.{clean_code}"
            else:
                secid = f"0.{clean_code}"
        
        print(f"DEBUG: stock_code={stock_code}, clean_code={clean_code}, secid={secid}")
        HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://quote.eastmoney.com/"
        }
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "insecure": 1,
            "secid": secid
        }

        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            print(data)
            # 检查接口业务错误
            if data.get("rc") != 0:
                print("接口返回错误:", data.get("msg", "未知错误"))
                return None

            # ⚠️ 关键修复：检查 data["data"] 是否为 None
            quote = data.get("data")
            if quote is None:
                print(f"股票 {stock_code} 返回数据为空（可能停牌、代码错误或接口限制）")
                return None

            # 安全获取字段（防止 KeyError 或 None）
            f43 = quote.get("f43")  # 最新价（单位：分）
            f44 = quote.get("f44")  # 最高价（单位：分）
            f45 = quote.get("f45")  # 最低价（单位：分）
            f47 = quote.get("f47")  # 成交量（手）
            f48 = quote.get("f48")  # 成交额（元）
            f58 = quote.get("f58", "")

            # 验证价格字段是否存在
            if f43 is None:
                print(f"股票 {stock_code} 缺少最新价格数据 (f43)")
                return None

            latest_price = f43 / 100.0
            # 直接截断到两位小数，不四舍五入
            latest_price = float(int(latest_price * 100)) / 100

            # 获取最高价和最低价
            high_price = f44 / 100.0 if f44 is not None else latest_price
            low_price = f45 / 100.0 if f45 is not None else latest_price
            # 直接截断到两位小数
            high_price = float(int(high_price * 100)) / 100
            low_price = float(int(low_price * 100)) / 100

            # 计算均价：成交额 / 总股数（1手 = 100股）
            if f47 is not None and f48 is not None and f47 > 0:
                average_price = f48 / (f47 * 100.0)
            else:
                average_price = latest_price  # 无成交时用最新价代替
            # 直接截断到两位小数，不四舍五入
            average_price = float(int(average_price * 100)) / 100

            # 计算价格差异和差异百分比
            price_diff = latest_price - average_price
            # 直接截断到两位小数，不四舍五入
            price_diff = float(int(price_diff * 100)) / 100
            price_diff_percent = (price_diff / average_price) * 100 if average_price > 0 else 0
            
            return {
                "stock_code": stock_code,
                "name": f58,
                "current_price": latest_price,
                "high": high_price,
                "low": low_price,
                "average_price": average_price,
                "volume": f47,
                "price_diff": price_diff,
                "price_diff_percent": round(price_diff_percent, 2),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            print(f"请求股票 {stock_code} 失败: {e}")
            # API调用失败时，返回None，让调用者处理
            return None
    
    @staticmethod
    def get_grid_step(high, low):
        """
        计算格子步长（同步前端算法）
        """
        range_val = high - low
        if range_val <= 0:
            return 0.01

        # 尝试不同格子数（6～8），选最合适的 nice step
        candidates = []
        for n in range(6, 9):
            step = range_val / n
            candidates.append(step)
        ideal = min(candidates)

        # 美化序列（包含0.06）
        nice = [0.01, 0.02, 0.05, 0.06, 0.08, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10]
        for v in nice:
            if v >= ideal * 0.9:  # 允许90%容差
                return v
        return ideal

    @staticmethod
    def check_trade_condition(stock_data, setting):
        """
        检查交易条件（支持闭环交易逻辑）
        """
        current_price = Decimal(str(stock_data['current_price']))
        
        # 获取设置值（支持字典或模型对象）
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        pending_loop_type = get_val(setting, 'pending_loop_type')
        pending_price = get_val(setting, 'pending_price')
        pending_timestamp = get_val(setting, 'pending_timestamp')
        overnight_sell_ratio = get_val(setting, 'overnight_sell_ratio', 1.0)
        overnight_buy_ratio = get_val(setting, 'overnight_buy_ratio', 1.0)

        # 1. 检查是否有未完成的闭环
        if pending_loop_type:
            pending_price_dec = Decimal(str(pending_price))
            # 检查是否为隔夜
            is_overnight = False
            if pending_timestamp:
                # 兼容 naive and aware datetime
                from django.utils.timezone import now as dj_now
                current_now = dj_now()
                # 如果 pending_timestamp 是字符串（可能在某些情况下），先转换
                if isinstance(pending_timestamp, str):
                    try:
                        pending_timestamp = datetime.strptime(pending_timestamp, '%Y-%m-%d %H:%M:%S')
                    except:
                        pass
                
                # 确保比较的是 date
                if hasattr(pending_timestamp, 'date'):
                    if current_now.date() > pending_timestamp.date():
                        is_overnight = True
            
            if pending_loop_type == 'buy_first':
                # 待卖出
                if is_overnight:
                    # 隔夜卖出比例
                    threshold_price = pending_price_dec * (1 + Decimal(str(overnight_sell_ratio)) / 100)
                    if current_price >= threshold_price:
                        return True, 'sell', f'隔夜闭环：当前价 {current_price} >= 目标价 {threshold_price:.2f} (买入价 {pending_price_dec} + {overnight_sell_ratio}%)'
                else:
                    # 当天卖出：使用正常策略逻辑查找卖出信号
                    should_trade, trade_type, reason = StockDataService._check_strategy_signal(stock_data, setting)
                    if should_trade and trade_type == 'sell':
                        return True, 'sell', reason
            
            elif pending_loop_type == 'sell_first':
                # 待买入
                if is_overnight:
                    # 隔夜买入比例
                    threshold_price = pending_price_dec * (1 - Decimal(str(overnight_buy_ratio)) / 100)
                    if current_price <= threshold_price:
                        return True, 'buy', f'隔夜闭环：当前价 {current_price} <= 目标价 {threshold_price:.2f} (卖出价 {pending_price_dec} - {overnight_buy_ratio}%)'
                else:
                    # 当天买入：使用正常策略逻辑查找买入信号
                    should_trade, trade_type, reason = StockDataService._check_strategy_signal(stock_data, setting)
                    if should_trade and trade_type == 'buy':
                        return True, 'buy', reason
            
            # 如果有闭环要求但未触发，则不进行任何新交易
            return False, None, None

        # 2. 没有未完成闭环，按照策略查找新交易
        return StockDataService._check_strategy_signal(stock_data, setting)

    @staticmethod
    def _check_strategy_signal(stock_data, setting):
        """
        基础策略信号检查
        """
        # 获取设置值（支持字典或模型对象）
        def get_val(obj, key, default=None):
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        strategy = get_val(setting, 'strategy', 'percentage')
        market_stage = get_val(setting, 'market_stage', 'oscillation')

        # 目前只处理震荡阶段
        if market_stage != 'oscillation':
            return False, None, None

        if strategy == 'grid':
            # 格子策略逻辑
            high = stock_data.get('high', stock_data['current_price'])
            low = stock_data.get('low', stock_data['current_price'])
            current_price = stock_data['current_price']
            average_price = stock_data['average_price']
            
            step = StockDataService.get_grid_step(high, low)
            grid_buy_count = get_val(setting, 'grid_buy_count', 1)
            grid_sell_count = get_val(setting, 'grid_sell_count', 1)
            
            # 计算价格偏离了多少个格子
            price_diff = current_price - average_price
            grid_diff = price_diff / step if step > 0 else 0
            
            print(f"DEBUG GRID: price={current_price}, avg={average_price}, step={step}, grid_diff={grid_diff}")
            
            if grid_diff >= grid_sell_count:
                return True, 'sell', f'当前价格高于均价 {grid_diff:.2f} 个格子（阈值: {grid_sell_count}），触发卖出'
            elif grid_diff <= -grid_buy_count:
                return True, 'buy', f'当前价格低于均价 {abs(grid_diff):.2f} 个格子（阈值: {grid_buy_count}），触发买入'
                
        else:
            # 百分比策略逻辑
            sell_threshold = get_val(setting, 'sell_threshold', 0.5)
            buy_threshold = get_val(setting, 'buy_threshold', 0.5)
            price_diff_percent = stock_data['price_diff_percent']
            
            # 调试信息：打印价格差异和阈值
            print(f"DEBUG PERCENT: price_diff_percent={price_diff_percent}, sell_threshold={sell_threshold}, buy_threshold={buy_threshold}")
            
            if price_diff_percent >= sell_threshold:
                return True, 'sell', f'当前价格高于均价{price_diff_percent}%，触发卖出'
            elif price_diff_percent <= -buy_threshold:
                return True, 'buy', f'当前价格低于均价{abs(price_diff_percent)}%，触发买入'
        
        return False, None, None

