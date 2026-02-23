import random
from datetime import datetime
import time
import requests
import os
import json
from decimal import Decimal

STRATEGY_CALL_COUNT = 0

def send_execution_request(stock_code, action, price, quantity, name):
    """
    向执行端发送交易请求
    """
    url = "http://192.168.0.107:5000/execute"
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
    print(f"\n[EXECUTION_DEBUG] [{timestamp}] 开始发送执行请求: {stock_code}({name}), {action}, 价格:{price}, 数量:{quantity}")
    
    data = {
        "price": str(price),
        "action": action,
        "symbol": stock_code,
        "name": name,
        "quantity": str(quantity)
    }
    try:
        # 这里使用同步请求，如果执行端是异步的并立即返回，则没问题
        # 如果执行端需要很久，可能需要考虑异步或增加超时
        response = requests.post(url, json=data, timeout=10)
        print(f"[EXECUTION_DEBUG] [{timestamp}] 执行请求响应: {response.status_code}, 内容: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"[EXECUTION_DEBUG] [{timestamp}] 发送执行请求失败: {e}")
        return False

class StockDataService:
    """
    股票数据服务类，用于获取和处理股票数据
    """
    _mock_data_index = {} # 用于记录每个股票代码读取到的模拟数据索引

    @staticmethod
    def get_stock_data(stock_code, mock_file_path=None):
        """
        获取股票实时数据（支持沪市/深市/北交所/模拟数据）
        """
        # 尝试读取模拟数据文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(current_dir))
        
        # 查找模拟数据文件
        mock_file = None
        stock_code_str = str(stock_code)
        
        # 优先使用前端指定的路径
        if mock_file_path and os.path.exists(mock_file_path):
            mock_file = mock_file_path
        else:
            # 自动查找逻辑
            try:
                for file in os.listdir(root_dir):
                    # 匹配规则：包含股票代码，或者在回测海汽集团时匹配特定名称
                    if file.endswith(".json") and (stock_code_str in file or "海汽集团" in file):
                        mock_file = os.path.join(root_dir, file)
                        break
            except Exception as e:
                print(f"DEBUG: 遍历目录失败: {e}")
        
        if mock_file and os.path.exists(mock_file):
            print(f"DEBUG: 发现模拟文件: {mock_file}")
            try:
                with open(mock_file, 'r', encoding='utf-8') as f:
                    mock_data_list = json.load(f)
                
                if mock_data_list and isinstance(mock_data_list, list):
                    # 获取当前索引
                    idx = StockDataService._mock_data_index.get(stock_code_str, 0)
                    if idx >= len(mock_data_list):
                        idx = 0 # 循环读取
                    
                    data = mock_data_list[idx]
                    StockDataService._mock_data_index[stock_code_str] = idx + 1
                    
                    # 兼容性处理：有些记录的是整个响应，有些可能是 data 部分
                    quote = data.get("data") if isinstance(data, dict) and "data" in data else data
                    
                    if quote:
                        f43 = quote.get("f43")
                        f44 = quote.get("f44")
                        f45 = quote.get("f45")
                        f47 = quote.get("f47")
                        f48 = quote.get("f48")
                        f58 = quote.get("f58", "模拟股票")

                        latest_price = f43 / 100.0 if f43 else 0
                        latest_price = float(int(latest_price * 100)) / 100
                        high_price = f44 / 100.0 if f44 else latest_price
                        low_price = f45 / 100.0 if f45 else latest_price
                        high_price = float(int(high_price * 100)) / 100
                        low_price = float(int(low_price * 100)) / 100

                        if f47 and f48 and f47 > 0:
                            average_price = f48 / (f47 * 100.0)
                        else:
                            average_price = latest_price
                        average_price = float(int(average_price * 100)) / 100

                        price_diff = latest_price - average_price
                        price_diff = float(int(price_diff * 100)) / 100
                        price_diff_percent = (price_diff / average_price) * 100 if average_price > 0 else 0

                        print(f"DEBUG: 使用模拟数据 (索引 {idx}/{len(mock_data_list)}): {f58}({stock_code_str}) {latest_price}")
                        
                        return {
                            "stock_code": stock_code_str,
                            "name": f58,
                            "current_price": latest_price,
                            "high": high_price,
                            "low": low_price,
                            "average_price": average_price,
                            "volume": f47,
                            "price_diff": price_diff,
                            "price_diff_percent": round(price_diff_percent, 2),
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "raw_response": data
                        }
            except Exception as e:
                print(f"DEBUG: 读取模拟数据失败: {e}")
        else:
            print(f"DEBUG: 未找到股票 {stock_code_str} 的模拟文件，将请求真实接口")

        # --- 如果没有模拟数据，则请求真实 API ---
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
            f46 = quote.get("f46")  # 今开（单位：分）
            f60 = quote.get("f60")  # 昨收（单位：分）
            f47 = quote.get("f47")  # 成交量（手）
            f48 = quote.get("f48")  # 成交额（元）
            f58 = quote.get("f58", "")

            # 验证价格字段是否存在，如果 f43 (最新价) 为 None 或 0，尝试用 f46 (今开) 或 f60 (昨收)
            if f43 is None or f43 == 0 or str(f43) == '-':
                if f46 is not None and f46 != 0 and str(f46) != '-':
                    f43 = f46
                    print(f"DEBUG: 股票 {stock_code} 最新价 f43 为空，使用今开 f46: {f43}")
                elif f60 is not None and f60 != 0 and str(f60) != '-':
                    f43 = f60
                    print(f"DEBUG: 股票 {stock_code} 最新价 f43 和今开 f46 均为空，使用昨收 f60: {f43}")
                else:
                    print(f"股票 {stock_code} 缺少所有价格数据 (f43/f46/f60)")
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
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "raw_response": data  # 记录完整的 API 响应数据
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
        try:
            # 转换为 float 进行计算，避免 Decimal 和 float 混合运算错误
            h = float(high)
            l = float(low)
            range_val = h - l
        except (TypeError, ValueError):
            return 0.01
            
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
            val = None
            if isinstance(obj, dict):
                val = obj.get(key, default)
            else:
                val = getattr(obj, key, default)
            
            # 处理空值和各种形式的空字符串
            if val is None:
                return default
            
            val_str = str(val).strip()
            if val_str == '' or val_str.lower() == 'null' or val_str.lower() == 'undefined':
                return default
            return val

        pending_loop_type = get_val(setting, 'pending_loop_type')
        pending_price = get_val(setting, 'pending_price')
        pending_timestamp = get_val(setting, 'pending_timestamp')
        overnight_sell_ratio = get_val(setting, 'overnight_sell_ratio', 1.0)
        overnight_buy_ratio = get_val(setting, 'overnight_buy_ratio', 1.0)

        # 1. 检查是否有未完成的闭环
        if pending_loop_type:
            try:
                pending_price_dec = Decimal(str(pending_price))
            except:
                return False, None, f"无效的待处理价格: {pending_price}", None
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
                # 待卖出：此时应屏蔽买入条件，只监控卖出条件
                
                # 1. 优先检查隔夜达标
                if is_overnight:
                    # 隔夜卖出比例
                    threshold_price = pending_price_dec * (1 + Decimal(str(overnight_sell_ratio)) / 100)
                    if current_price >= threshold_price:
                        return True, 'sell', f'隔夜闭环：当前价 {current_price} >= 目标价 {threshold_price:.2f} (买入价 {pending_price_dec} + {overnight_sell_ratio}%)', None
                
                # 2. 如果隔夜未达标，或者不是隔夜，则检查常规策略信号
                if isinstance(setting, dict):
                    setting_copy = setting.copy()
                else:
                    # 从模型对象提取所有字段
                    setting_copy = {f.name: getattr(setting, f.name) for f in setting._meta.fields}
                
                setting_copy['grid_buy_count'] = None
                setting_copy['buy_avg_line_range_minus'] = None
                setting_copy['buy_avg_line_range_plus'] = None
                setting_copy['buy_threshold'] = 999  # 极大值屏蔽百分比买入
                
                should_trade, trade_type, reason, extra_info = StockDataService._check_strategy_signal(stock_data, setting_copy)
                
                # 同步格子信息到外部 stock_data
                if 'grid_step' in stock_data:
                    stock_data['grid_step'] = stock_data['grid_step']
                if 'grid_diff' in stock_data:
                    stock_data['grid_diff'] = stock_data['grid_diff']
                
                # 增加调试日志
                if not should_trade:
                    print(f"DEBUG: [{stock_data.get('name')}] (待卖出闭环) 未触发卖出信号. 原因: {reason if reason else '未达阈值'}")
                
                if should_trade and (trade_type == 'sell' or trade_type == 'both'):
                    actual_reason = reason
                    if trade_type == 'both' and "卖: " in reason:
                        actual_reason = reason.split("卖: ")[1]
                    return True, 'sell', actual_reason, extra_info
            
            elif pending_loop_type == 'sell_first':
                # 待买入：此时应屏蔽卖出条件，只监控买入条件
                
                # 1. 优先检查隔夜达标
                if is_overnight:
                    # 隔夜买入比例
                    threshold_price = pending_price_dec * (1 - Decimal(str(overnight_buy_ratio)) / 100)
                    if current_price <= threshold_price:
                        return True, 'buy', f'隔夜闭环：当前价 {current_price} <= 目标价 {threshold_price:.2f} (卖出价 {pending_price_dec} - {overnight_buy_ratio}%)', None
                
                # 2. 如果隔夜未达标，或者不是隔夜，则检查常规策略信号
                if isinstance(setting, dict):
                    setting_copy = setting.copy()
                else:
                    # 从模型对象提取所有字段
                    setting_copy = {f.name: getattr(setting, f.name) for f in setting._meta.fields}
                    
                setting_copy['grid_sell_count'] = None
                setting_copy['sell_avg_line_range_minus'] = None
                setting_copy['sell_avg_line_range_plus'] = None
                setting_copy['sell_threshold'] = 999  # 极大值屏蔽百分比卖出
                
                should_trade, trade_type, reason, extra_info = StockDataService._check_strategy_signal(stock_data, setting_copy)
                
                # 增加调试日志
                if not should_trade:
                    print(f"DEBUG: [{stock_data.get('name')}] (待买入闭环) 未触发买入信号. 原因: {reason if reason else '未达阈值'}")
                
                if should_trade and (trade_type == 'buy' or trade_type == 'both'):
                    actual_reason = reason
                    if trade_type == 'both' and "买: " in reason:
                        actual_reason = reason.split("买: ")[1].split(" |")[0]
                    return True, 'buy', actual_reason, extra_info
            
            # 如果有闭环要求但未触发，则不进行任何新交易
            return False, None, None, None

        # 2. 没有未完成闭环，按照策略查找新交易
        should_trade, trade_type, reason, extra_info = StockDataService._check_strategy_signal(stock_data, setting)
        
        # 增加调试日志
        if not should_trade:
             print(f"DEBUG: [{stock_data.get('name')}] 未触发新交易信号. 原因: {reason if reason else '未达阈值'}")
        
        if should_trade:
            # 如果是 both，在没有闭环的情况下，根据持仓情况决定优先买入还是卖出
            if trade_type == 'both':
                try:
                    from quant.models import Account
                    account = Account.objects.filter(stock_code=stock_data['stock_code']).first()
                    # 如果有持仓，优先卖出；否则优先买入
                    if account and account.available_shares > 0:
                        trade_type = 'sell'
                        if "卖: " in reason:
                            reason = reason.split("卖: ")[1]
                        print(f"DEBUG BOTH: 同时触发买卖信号，检测到持仓 {account.available_shares}，优先执行卖出")
                    else:
                        trade_type = 'buy'
                        if "买: " in reason:
                            reason = reason.split("买: ")[1].split(" |")[0]
                        print(f"DEBUG BOTH: 同时触发买卖信号，未检测到可用持仓，优先执行买入")
                except Exception as e:
                    print(f"DEBUG BOTH: 获取账户信息失败，默认优先买入: {e}")
                    trade_type = 'buy'
                    if "买: " in reason:
                        reason = reason.split("买: ")[1].split(" |")[0]
            
            # 获取震荡类型
            oscillation_type = get_val(setting, 'oscillation_type', 'normal')
            
            # 限制：低位震荡只能先买后卖 (不能作为第一笔卖出)
            if oscillation_type == 'low' and trade_type == 'sell':
                print(f"DEBUG: 低位震荡限制，拦截 {stock_data.get('name')} 的第一笔卖出交易 (原因: {reason})")
                return False, None, f"低位震荡限制: {reason}", extra_info
            
            # 限制：高位震荡只能先卖后买 (不能作为第一笔买入)
            if oscillation_type == 'high' and trade_type == 'buy':
                print(f"DEBUG: 高位震荡限制，拦截 {stock_data.get('name')} 的第一笔买入交易 (原因: {reason})")
                return False, None, f"高位震荡限制: {reason}", extra_info
                
        return should_trade, trade_type, reason, extra_info

    @staticmethod
    def _check_strategy_signal(stock_data, setting):
        """
        基础策略信号检查
        """
        # 获取设置值（支持字典或模型对象）
        def get_val(obj, key, default=None):
            val = None
            if isinstance(obj, dict):
                val = obj.get(key, default)
            else:
                val = getattr(obj, key, default)
            
            # 处理空值和各种形式的空字符串
            if val is None:
                return default
            
            val_str = str(val).strip()
            if val_str == '' or val_str.lower() == 'null' or val_str.lower() == 'undefined':
                return default
            return val

        strategy = get_val(setting, 'strategy', 'percentage')
        
        # 多因子策略处理
        if strategy == 'multi_factor':
            try:
                from quant.services.multi_factor_strategy import MultiFactorStrategy
                stock_code = stock_data.get('stock_code')
                if stock_code:
                    strategy_instance = MultiFactorStrategy.get_instance(stock_code)
                    
                    # 调用前
                    global STRATEGY_CALL_COUNT
                    STRATEGY_CALL_COUNT += 1
                    print(f"\n[TEST] ========== 第{STRATEGY_CALL_COUNT}次调用 ==========")
                    print(f"[TEST] 当前时间：{datetime.now()}")

                    # 调用
                    result = strategy_instance.check_signal(stock_data, setting)
                    
                    # 调用后
                    print(f"[TEST] 返回结果：{result}")
                    print(f"[TEST] ========== 调用结束 ==========\n")
                    
                    return result
            except Exception as e:
                print(f"多因子策略出错: {e}")
                import traceback
                traceback.print_exc()
                return False, None, f"多因子策略出错: {e}", None

        market_stage = get_val(setting, 'market_stage', 'oscillation')
        
        try:
            current_price = Decimal(str(stock_data['current_price']))
            average_price = Decimal(str(stock_data['average_price']))
        except Exception as e:
            print(f"Decimal 转换失败 (stock_data): {e}")
            return False, None, None, None
        
        # 目前只处理震荡阶段
        if market_stage != 'oscillation':
            return False, None, None, None

        potential_trade_type = None
        reason = ""

        # 获取格子步长（仅在格子策略或需要按格子计算范围时使用）
        high = stock_data.get('high', stock_data['current_price'])
        low = stock_data.get('low', stock_data['current_price'])
        try:
            step = Decimal(str(StockDataService.get_grid_step(high, low)))
        except:
            step = Decimal('0.01')

        # 获取原始参数值，用于判断用户填了哪个
        raw_grid_buy = get_val(setting, 'grid_buy_count')
        raw_grid_sell = get_val(setting, 'grid_sell_count')
        raw_range_buy_minus = get_val(setting, 'buy_avg_line_range_minus')
        raw_range_buy_plus = get_val(setting, 'buy_avg_line_range_plus')
        raw_range_sell_minus = get_val(setting, 'sell_avg_line_range_minus')
        raw_range_sell_plus = get_val(setting, 'sell_avg_line_range_plus')

        print(f"DEBUG PARAMS: buy_minus={raw_range_buy_minus}, buy_plus={raw_range_buy_plus}, sell_minus={raw_range_sell_minus}, sell_plus={raw_range_sell_plus}, grid_buy={raw_grid_buy}")

        # 转换数值
        grid_buy_count = Decimal(str(raw_grid_buy)) if raw_grid_buy is not None else None
        grid_sell_count = Decimal(str(raw_grid_sell)) if raw_grid_sell is not None else None
        
        try:
            sell_threshold = Decimal(str(get_val(setting, 'sell_threshold', 0.5)))
            buy_threshold = Decimal(str(get_val(setting, 'buy_threshold', 0.5)))
        except:
            sell_threshold = Decimal('0.5')
            buy_threshold = Decimal('0.5')
            
        price_diff = current_price - average_price
        grid_diff = price_diff / step if step > 0 else Decimal('0')
        price_diff_percent = (current_price - average_price) / average_price * 100 if average_price > 0 else 0

        print(f"DEBUG STRATEGY [{stock_data.get('name', 'Unknown')}({stock_data.get('stock_code', 'Unknown')})]: "
              f"当前价={current_price}, 均价={average_price}, 格子步长={step}, 偏离格子数={grid_diff:.4f}, "
              f"待闭环={get_val(setting, 'pending_loop_type', 'None')}")

        # 强制更新 stock_data 里的格子信息，以便外部打印
        stock_data['grid_step'] = float(step)
        stock_data['grid_diff'] = float(grid_diff)

        # 获取待闭环类型
        pending_loop_type = get_val(setting, 'pending_loop_type')

        # 检查买入信号
        is_buy_signal = False
        buy_reason = ""
        
        # 如果当前有卖出待闭环（即买入回补），或者没有待闭环任务，才允许检查买入信号
        if pending_loop_type is None or pending_loop_type == 'sell_first':
            # 买入逻辑判断：优先检查区间范围是否填值，如果填了则按区间来，否则看格子是否填值
            if raw_range_buy_minus is not None or raw_range_buy_plus is not None:
                # 按均价线区间买入
                # 逻辑：
                # 1. 如果设置了 minus，则下限为 avg - minus*step；否则下限为 avg
                # 2. 如果设置了 plus，则上限为 avg + plus*step；否则上限为 avg
                lower_bound_b = average_price
                upper_bound_b = average_price
                
                if raw_range_buy_minus is not None:
                    lower_offset = Decimal(str(raw_range_buy_minus)) * step
                    lower_bound_b = average_price - lower_offset
                
                if raw_range_buy_plus is not None:
                    upper_offset = Decimal(str(raw_range_buy_plus)) * step
                    upper_bound_b = average_price + upper_offset
                
                # 容差判断
                tolerance = Decimal('0.0001')
                if (lower_bound_b - tolerance) <= current_price <= (upper_bound_b + tolerance):
                    is_buy_signal = True
                    buy_reason = f"均价线区间买入触发：当前价 {current_price} 在范围 [{lower_bound_b:.4f}, {upper_bound_b:.4f}] (格子大小: {step}, 偏离格子数: {grid_diff:.2f})"
                else:
                    # 优化调试日志
                    if current_price < lower_bound_b:
                        print(f"DEBUG RANGE [BUY] [{stock_data.get('name')}]: 未触发。当前价 {current_price} 低于区间下限 {lower_bound_b:.4f}")
                    elif current_price > upper_bound_b:
                        print(f"DEBUG RANGE [BUY] [{stock_data.get('name')}]: 未触发。当前价 {current_price} 高于区间上限 {upper_bound_b:.4f}")
            elif grid_buy_count is not None:
                # 按格子数买入
                if grid_diff <= -grid_buy_count:
                    is_buy_signal = True
                    buy_reason = f'格子法买入：偏离 {grid_diff:.2f} 格 <= -{grid_buy_count}'
            elif strategy == 'percentage':
                # 兜底：按百分比买入
                if price_diff_percent <= -buy_threshold:
                    is_buy_signal = True
                    buy_reason = f'百分比买入：偏离 {price_diff_percent:.2f}% <= -{buy_threshold}%'
        else:
            print(f"DEBUG STRATEGY [{stock_data.get('name')}]: 闭环锁定中 ({pending_loop_type})，跳过买入检查")

        # 检查卖出信号
        is_sell_signal = False
        sell_reason = ""

        # 如果当前有买入待闭环（即卖出平仓），或者没有待闭环任务，才允许检查卖出信号
        if pending_loop_type is None or pending_loop_type == 'buy_first':
            # 卖出逻辑判断：优先检查区间范围是否填值，如果填了则按区间来，否则看格子是否填值
            if raw_range_sell_minus is not None or raw_range_sell_plus is not None:
                # 按均价线区间卖出
                # 逻辑：
                # 1. 如果设置了 minus，则下限为 avg - minus*step；否则下限为 avg
                # 2. 如果设置了 plus，则上限为 avg + plus*step；否则上限为 avg
                lower_bound_s = average_price
                upper_bound_s = average_price
                
                if raw_range_sell_minus is not None:
                    lower_offset = Decimal(str(raw_range_sell_minus)) * step
                    lower_bound_s = average_price - lower_offset
                
                if raw_range_sell_plus is not None:
                    upper_offset = Decimal(str(raw_range_sell_plus)) * step
                    upper_bound_s = average_price + upper_offset
                
                # 容差判断
                tolerance = Decimal('0.0001')
                if (lower_bound_s - tolerance) <= current_price <= (upper_bound_s + tolerance):
                    is_sell_signal = True
                    sell_reason = f"均价线区间卖出触发：当前价 {current_price} 在范围 [{lower_bound_s:.4f}, {upper_bound_s:.4f}] (格子大小: {step}, 偏离格子数: {grid_diff:.2f})"
                else:
                    if current_price < lower_bound_s:
                        print(f"DEBUG RANGE [SELL] [{stock_data.get('name')}]: 未触发。当前价 {current_price} 低于区间下限 {lower_bound_s:.4f}")
                    elif current_price > upper_bound_s:
                        print(f"DEBUG RANGE [SELL] [{stock_data.get('name')}]: 未触发。当前价 {current_price} 高于区间上限 {upper_bound_s:.4f}")
            elif grid_sell_count is not None:
                # 按格子数卖出
                if grid_diff >= grid_sell_count:
                    is_sell_signal = True
                    sell_reason = f'格子法卖出：偏离 {grid_diff:.2f} 格 >= {grid_sell_count}'
            elif strategy == 'percentage':
                # 兜底：按百分比卖出
                if price_diff_percent >= float(sell_threshold):
                    is_sell_signal = True
                    sell_reason = f'百分比卖出：偏离 {price_diff_percent:.2f}% >= {sell_threshold}%'
        else:
            print(f"DEBUG STRATEGY [{stock_data.get('name')}]: 闭环锁定中 ({pending_loop_type})，跳过卖出检查")

        # 返回结果：如果同时有买卖信号，返回一个包含两者的元组
        # 这里的 trade_type 可以是 'buy', 'sell' 或 'both'
        if is_buy_signal and is_sell_signal:
            return True, 'both', f"同时触发买卖信号 | 买: {buy_reason} | 卖: {sell_reason}", None
        
        if is_buy_signal:
            return True, 'buy', buy_reason, None
            
        if is_sell_signal:
            return True, 'sell', sell_reason, None

        return False, None, None, None


