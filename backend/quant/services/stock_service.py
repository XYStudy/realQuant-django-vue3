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
        # --- 内联 get_secid 逻辑 ---
        code_str = str(stock_code).strip()
        if code_str.startswith(('60', '688', '689')):
            secid = f"1.{code_str}"  # 沪市 A 股 / 科创板
        elif code_str.startswith(('00', '30', '8')):
            secid = f"0.{code_str}"  # 深市主板 / 创业板 / 北交所
        else:
            # 默认尝试深市（或可根据需求抛异常）
            secid = f"0.{code_str}"
            # 或 raise ValueError(f"无法识别的股票市场: {stock_code}")
        print(secid)
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
                "high_price": high_price,
                "low_price": low_price,
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
    def check_trade_condition(stock_data, sell_threshold, buy_threshold):
        """
        检查交易条件
        
        Args:
            stock_data: 股票数据
            sell_threshold: 卖出阈值(%)
            buy_threshold: 买入阈值(%)
            
        Returns:
            tuple: (是否交易, 交易类型, 交易原因)
        """
        price_diff_percent = stock_data['price_diff_percent']
        
        # 调试信息：打印价格差异和阈值
        print(f"DEBUG: price_diff_percent={price_diff_percent}, sell_threshold={sell_threshold}, buy_threshold={buy_threshold}")
        
        if price_diff_percent >= sell_threshold:
            return True, 'sell', f'当前价格高于均价{price_diff_percent}%，触发卖出'
        elif price_diff_percent <= -buy_threshold:
            return True, 'buy', f'当前价格低于均价{abs(price_diff_percent)}%，触发买入'
        
        return False, None, None

