import asyncio
import json
import logging
from datetime import datetime
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from quant.services.stock_service import StockDataService, send_execution_request
from quant.models import TradeSetting, Account, TradeRecord, TradeLoop
from decimal import Decimal

logger = logging.getLogger(__name__)

class MonitorManager:
    """
    全局监控管理器，负责管理所有股票的后台监控任务。
    将交易逻辑与 WebSocket 解耦，确保即使前端关闭，监控和交易也能继续（如果需要）。
    """
    _instance = None
    _tasks = {}  # stock_code -> task

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MonitorManager, cls).__new__(cls)
        return cls._instance

    async def start_monitoring(self, stock_code, record_data=False, mock_file_path=None):
        """启动特定股票的监控任务"""
        try:
            if stock_code in self._tasks:
                # 如果已经在运行，先停止旧的
                print(f"DEBUG: 股票 {stock_code} 已有监控任务，正在停止旧任务...")
                await self.stop_monitoring(stock_code)
            
            task = asyncio.create_task(self._run_monitor(stock_code, record_data, mock_file_path))
            self._tasks[stock_code] = task
            print(f"DEBUG: 启动股票 {stock_code} 的后台监控任务")
            return True
        except Exception as e:
            print(f"ERROR: 启动监控任务失败 {stock_code}: {e}")
            import traceback
            traceback.print_exc()
            raise e

    async def stop_monitoring(self, stock_code):
        """停止特定股票的监控任务"""
        if stock_code in self._tasks:
            task = self._tasks[stock_code]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                print(f"DEBUG: 停止任务时捕获到异常 (任务可能已崩溃) {stock_code}: {e}")
            
            if stock_code in self._tasks:
                del self._tasks[stock_code]
            print(f"DEBUG: 停止股票 {stock_code} 的后台监控任务")
            return True
        return False

    async def get_current_state(self, stock_code):
        """获取特定股票的当前监控状态数据"""
        trade_setting = await self._get_trade_setting(stock_code)
        account = await self._get_account(stock_code)
        trade_records = await self._get_trade_records(stock_code)
        trade_loops = await self._get_trade_loops(stock_code)
        
        # 获取最新价格数据（不增加模拟数据索引）
        stock_data = await sync_to_async(StockDataService.get_stock_data)(stock_code)
        
        return {
            'type': 'stock_data',
            'stock_data': stock_data,
            'account': account,
            'trade_setting': trade_setting,
            'trade_records': trade_records,
            'trade_loops': trade_loops
        }

    async def _run_monitor(self, stock_code, record_data, mock_file_path):
        """核心监控循环"""
        channel_layer = get_channel_layer()
        group_name = f"stock_{stock_code}"
        recorded_data = []
        stock_name = "未知股票"
        
        print(f"DEBUG: 开始运行 {stock_code} 的监控循环")
        
        try:
            while True:
                try:
                    # 1. 获取最新设置
                    trade_setting = await self._get_trade_setting(stock_code)
                    if not trade_setting:
                        await asyncio.sleep(1)
                        continue
                        
                    # 如果未激活，仅发送数据但不处理交易
                    is_active = trade_setting.get('is_active', False)

                    # 2. 获取股票数据 (这里是请求拿数据的接口)
                    stock_data = await sync_to_async(StockDataService.get_stock_data)(stock_code, mock_file_path)
                    
                    if stock_data:
                        # 记录数据
                        if record_data and 'raw_response' in stock_data:
                            recorded_data.append(stock_data['raw_response'])
                        
                        if stock_data.get('name'):
                            stock_name = stock_data['name']

                        # 3. 检查交易逻辑 (无论是否激活，都运行策略以获取分析数据)
                        await self._process_trade_logic(stock_code, stock_data, trade_setting)
                        
                        # 4. 获取账户和记录信息
                        account = await self._get_account(stock_code)
                        trade_records = await self._get_trade_records(stock_code)
                        trade_loops = await self._get_trade_loops(stock_code)
                        
                        # 5. 广播数据到 Channel Group
                        await channel_layer.group_send(
                            group_name,
                            {
                                "type": "stock_update",
                                "data": {
                                    'type': 'stock_data',
                                    'stock_data': stock_data,
                                    'account': account,
                                    'trade_setting': trade_setting,
                                    'trade_records': trade_records,
                                    'trade_loops': trade_loops
                                }
                            }
                        )
                    
                    # 6. 严格执行后等待：无论上面逻辑花了多久，都从现在开始睡足 N 秒
                    # 这样保证了两次“请求接口”之间至少有 N 秒的间隔
                    interval = trade_setting.get('update_interval', 5)
                    await asyncio.sleep(interval)
                    
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    print(f"ERROR: 监控循环 {stock_code} 发生错误: {e}")
                    await asyncio.sleep(2)
        finally:
            # 停止时保存录制的数据
            if record_data and recorded_data:
                await self._save_recorded_data(stock_code, stock_name, recorded_data)

    async def _save_recorded_data(self, stock_code, stock_name, recorded_data):
        """保存录制的数据"""
        import os
        try:
            now = datetime.now()
            date_str = now.strftime('%Y-%m-%d')
            time_str = now.strftime('%H%M%S')
            filename = f"{date_str}-{stock_code}-{stock_name}-{time_str}.json"
            
            # 获取项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
            file_path = os.path.join(root_dir, filename)
            
            print(f"DEBUG: 引擎正在保存录制数据到 {file_path}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(recorded_data, f, ensure_ascii=False, indent=2)
            
            print(f"DEBUG: 录制数据保存成功")
        except Exception as e:
            print(f"ERROR: 保存录制数据失败: {e}")

    async def _process_trade_logic(self, stock_code, stock_data, trade_setting):
        """处理交易决策逻辑"""
        # 1. 初始检查：如果正在执行中，直接跳过
        is_executing = trade_setting.get('is_executing', False)
        if is_executing:
            print(f"DEBUG: 股票 {stock_code} ({stock_data.get('name')}) 正在执行交易中 (is_executing=True)，跳过本次检查")
            return

        # 2. 检查交易信号
        should_trade, trade_type, reason, extra_info = await sync_to_async(StockDataService.check_trade_condition)(
            stock_data, 
            trade_setting
        )

        # 将 extra_info 注入到 stock_data 中，以便广播到前端
        if extra_info:
            stock_data['strategy_info'] = extra_info

        # 检查是否激活交易，未激活仅分析不执行
        is_active = trade_setting.get('is_active', False)
        if not is_active:
            # 仅当策略有信号且未激活时打印提示
            if should_trade:
                print(f"[MONITOR] [{stock_code}] 策略触发信号 ({trade_type}) 但自动交易未激活，仅作记录")
            return

        if not should_trade:
            # 只有当原因不为 None 时才打印，避免刷屏
            if reason and "未触发" not in reason:
                print(f"[MONITOR] [{stock_code}] 策略未触发, 原因: {reason}")
            return

        # 3. 信号触发，获取最新设置进行二次验证 (防止信号检测期间状态已变更)
        latest_setting = await self._get_trade_setting(stock_code)
        if not latest_setting:
            return

        # 检查是否由于并发或回调已在执行中
        if latest_setting.get('is_executing'):
            print(f"[MONITOR] [{stock_code}] 二次验证拦截：交易正在执行中")
            return

        # 检查闭环一致性：如果当前已有待闭环任务，则当前信号必须是闭环信号
        pending_loop_type = latest_setting.get('pending_loop_type')

        # 下午 14:30 以后禁止新开 T 操作 (交易结束前 30 分钟)
        now = datetime.now()
        current_time_str = now.strftime('%H:%M')
        if not pending_loop_type and current_time_str >= "14:30":
            print(f"[MONITOR] [{stock_code}] 下午 14:30 以后禁止新开 T 操作 (当前时间: {current_time_str})")
            return

        if pending_loop_type:
            is_valid_closing_trade = False
            if pending_loop_type == 'buy_first' and trade_type == 'sell':
                is_valid_closing_trade = True
            elif pending_loop_type == 'sell_first' and trade_type == 'buy':
                is_valid_closing_trade = True
            
            if not is_valid_closing_trade:
                print(f"[MONITOR] [{stock_code}] 闭环保护二次验证拦截：当前处于 {pending_loop_type} 状态，拦截非闭环信号 {trade_type}")
                return
        else:
            # 如果没有待闭环任务，但信号是卖出且没有可用持仓，也拦截 (针对卖出开仓的情况)
            if trade_type == 'sell':
                account = await self._get_account(stock_code)
                if account.get('available_shares', 0) < 100:
                    print(f"[MONITOR] [{stock_code}] 拦截：无待闭环任务且无可用持仓，无法发起卖出信号")
                    return

        print(f"[MONITOR] [{stock_code}] 策略触发信号: {trade_type}, 原因: {reason}")

        # 4. 获取账户信息用于验证
        account = await self._get_account(stock_code)
        
        # 5. 执行交易处理
        if trade_type == 'buy':
            await self._handle_buy(stock_code, stock_data, latest_setting, account)
        elif trade_type == 'sell':
            await self._handle_sell(stock_code, stock_data, latest_setting, account)

    async def _handle_buy(self, stock_code, stock_data, trade_setting, account):
        """处理买入逻辑"""
        # 确定买入数量
        pending_loop_type = trade_setting.get('pending_loop_type')
        if pending_loop_type == 'sell_first':
            # 如果有闭环任务，取 闭环计划量 和 用户设置量 的最小值
            planned_volume = trade_setting['pending_volume']
            if trade_setting['buy_shares']:
                planned_volume = min(planned_volume, trade_setting['buy_shares'])
            trade_volume = planned_volume
            print(f"[MONITOR] [{stock_code}] 闭环买入: 计划 {trade_setting['pending_volume']}, 用户设置 {trade_setting['buy_shares']} -> 实际执行 {trade_volume}")
        else:
            trade_volume = trade_setting['buy_shares'] or 100
            
        # 股数取整到 100
        trade_volume = max(100, (trade_volume // 100) * 100)
        
        # 检查余额
        current_price = Decimal(str(stock_data['current_price']))
        trade_amount = current_price * Decimal(str(trade_volume))
        if Decimal(str(account['balance'])) < trade_amount:
            # 如果余额不足，尝试缩减到 100 股
            if trade_volume > 100:
                trade_volume = 100
                trade_amount = current_price * Decimal(str(trade_volume))
                if Decimal(str(account['balance'])) < trade_amount:
                    print(f"[MONITOR] [{stock_code}] 买入拦截: 余额不足(即使缩减到100股). 需要 {trade_amount}, 实际 {account['balance']}")
                    return
            else:
                print(f"[MONITOR] [{stock_code}] 买入拦截: 余额不足. 需要 {trade_amount}, 实际 {account['balance']}")
                return

        # 原子加锁
        locked = await sync_to_async(self._try_lock)(stock_code)
        if locked:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            print(f"[EXECUTION_DEBUG] [{timestamp}] 后台引擎发起买入请求: {stock_code}, {trade_volume}股")
            
            success = await sync_to_async(send_execution_request)(
                stock_code, 'buy', float(current_price), trade_volume, stock_data.get('name', '')
            )
            
            if not success:
                print(f"[EXECUTION_DEBUG] [{timestamp}] 发送失败，释放锁")
                await sync_to_async(self._unlock)(stock_code)
            else:
                # 发送成功，锁保持 True，等待 trade-callback 回调来重置 is_executing
                print(f"[EXECUTION_DEBUG] [{timestamp}] 发送成功，等待回调释放锁...")

    async def _handle_sell(self, stock_code, stock_data, trade_setting, account):
        """处理卖出逻辑"""
        available_shares = account.get('available_shares', 0)
        print(f"DEBUG: [{stock_code}] ({stock_data.get('name')}) 处理卖出逻辑, 可用持仓: {available_shares}, 待闭环类型: {trade_setting.get('pending_loop_type')}")
        
        # 确定卖出数量
        if trade_setting.get('pending_loop_type') == 'buy_first':
            # 如果有闭环任务，取 闭环计划量、用户设置量 和 可用持仓 的最小值
            planned_volume = trade_setting['pending_volume']
            if trade_setting['sell_shares']:
                planned_volume = min(planned_volume, trade_setting['sell_shares'])
            
            if available_shares < planned_volume:
                print(f"[MONITOR] [{stock_code}] 卖出拦截: 可用持仓不足. 计划 {planned_volume}, 实际可用 {available_shares}")
            
            trade_volume = min(planned_volume, available_shares)
            print(f"[MONITOR] [{stock_code}] 闭环卖出: 计划 {trade_setting['pending_volume']}, 用户设置 {trade_setting['sell_shares']}, 可用 {available_shares} -> 实际执行 {trade_volume}")
        else:
            trade_volume = trade_setting['sell_shares'] or 100
            if available_shares < trade_volume:
                print(f"[MONITOR] [{stock_code}] 卖出拦截: 可用持仓不足. 需要 {trade_volume}, 实际可用 {available_shares}")
            trade_volume = min(trade_volume, available_shares)
            
        # 股数取整到 100，且确保不为 0
        trade_volume = (trade_volume // 100) * 100
        
        if trade_volume < 100:
            print(f"[MONITOR] [{stock_code}] 卖出拦截: 计算出的交易量 {trade_volume} 小于 100 股 (可用持仓: {available_shares})")
            return

        if available_shares >= trade_volume:
            locked = await sync_to_async(self._try_lock)(stock_code)
            if locked:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
                print(f"[EXECUTION_DEBUG] [{timestamp}] 后台引擎发起卖出请求: {stock_code}, {trade_volume}股")
                
                success = await sync_to_async(send_execution_request)(
                    stock_code, 'sell', stock_data['current_price'], trade_volume, stock_data.get('name', '')
                )
                
                if not success:
                    print(f"[EXECUTION_DEBUG] [{timestamp}] 发送失败，释放锁")
                    await sync_to_async(self._unlock)(stock_code)
                else:
                    # 发送成功，锁保持 True，等待 trade-callback 回调来重置 is_executing
                    print(f"[EXECUTION_DEBUG] [{timestamp}] 发送成功，等待回调释放锁...")

    # --- 数据库操作辅助方法 ---
    
    def _try_lock(self, stock_code):
        from quant.consumers import try_lock_trade_executing_sync
        return try_lock_trade_executing_sync(stock_code)

    def _unlock(self, stock_code):
        from quant.consumers import set_trade_executing_sync
        return set_trade_executing_sync(stock_code, False)

    async def _get_trade_setting(self, stock_code):
        from quant.consumers import get_trade_setting_sync
        return await sync_to_async(get_trade_setting_sync)(stock_code)

    async def _get_account(self, stock_code):
        from quant.consumers import get_account_sync
        res = await sync_to_async(get_account_sync)(stock_code)
        if res:
            res['balance'] = float(res['balance'])
        return res

    async def _get_trade_records(self, stock_code):
        from quant.consumers import get_trade_records_sync
        return await sync_to_async(get_trade_records_sync)(stock_code)

    async def _get_trade_loops(self, stock_code):
        from quant.consumers import get_trade_loops_sync
        return await sync_to_async(get_trade_loops_sync)(stock_code)

# 单例对象
monitor_manager = MonitorManager()
