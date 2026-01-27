# quant/consumers.py
import asyncio
import json
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from quant.services.stock_service import StockDataService
from quant.models import TradeSetting, Account, TradeRecord, TradeLoop
from decimal import Decimal
from django.utils import timezone

# 同步辅助函数
def get_trade_setting_sync(stock_code):
    """获取交易设置（同步函数）"""
    setting, _ = TradeSetting.objects.get_or_create(
        stock_code=stock_code,
        defaults={
            'sell_threshold': Decimal('0.5'),
            'buy_threshold': Decimal('0.5'),
            'buy_amount': Decimal('10000'),
            'sell_amount': Decimal('10000'),
            'update_interval': 5,
            'is_active': True
        }
    )
    return {
        'id': setting.id,
        'stock_code': setting.stock_code,
        'strategy': setting.strategy,
        'sell_threshold': float(setting.sell_threshold),
        'buy_threshold': float(setting.buy_threshold),
        'buy_amount': float(setting.buy_amount) if setting.buy_amount else None,
        'sell_amount': float(setting.sell_amount) if setting.sell_amount else None,
        'buy_shares': setting.buy_shares,
        'sell_shares': setting.sell_shares,
        'pending_loop_type': setting.pending_loop_type,
        'pending_price': float(setting.pending_price) if setting.pending_price else None,
        'pending_volume': setting.pending_volume,
        'pending_timestamp': setting.pending_timestamp,
        'overnight_sell_ratio': float(setting.overnight_sell_ratio),
        'overnight_buy_ratio': float(setting.overnight_buy_ratio),
    }

def get_account_sync(stock_code):
    """获取账户信息（同步函数）"""
    account, _ = Account.objects.get_or_create(
        stock_code=stock_code,
        defaults={
            'balance': Decimal('100000.00'),
            'shares': 3000,
            'available_shares': 3000
        }
    )
    return {
        'id': account.id,
        'balance': float(account.balance),
        'shares': account.shares,
        'available_shares': account.available_shares
    }

def update_account_after_trade_sync(stock_code, trade_type, volume, amount):
    """交易后更新账户信息（同步函数）"""
    account = Account.objects.get(stock_code=stock_code)
    if trade_type == 'buy':
        account.balance -= Decimal(str(amount))
        account.shares += volume
    else:
        account.balance += Decimal(str(amount))
        account.shares -= volume
        account.available_shares -= volume
    account.save()
    return {
        'balance': float(account.balance),
        'shares': account.shares,
        'available_shares': account.available_shares
    }

def create_trade_and_update_loop_sync(stock_code, trade_type, price, volume, amount, reason):
    """创建交易记录并更新闭环（同步函数）"""
    # 1. 创建交易记录
    trade_record = TradeRecord.objects.create(
        stock_code=stock_code,
        trade_type=trade_type,
        price=price,
        volume=volume,
        amount=amount,
        reason=reason
    )
    
    # 2. 更新闭环状态
    setting = TradeSetting.objects.get(stock_code=stock_code)
    if setting.pending_loop_type is None:
        # 开启新闭环
        setting.pending_loop_type = 'buy_first' if trade_type == 'buy' else 'sell_first'
        setting.pending_price = price
        setting.pending_volume = volume
        setting.pending_timestamp = trade_record.timestamp
        setting.save()
        
        # 创建待闭环记录
        TradeLoop.objects.create(
            stock_code=stock_code,
            loop_type='buy_sell' if trade_type == 'buy' else 'sell_buy',
            open_record=trade_record,
            is_closed=False
        )
    else:
        # 完成闭环
        loop = TradeLoop.objects.filter(stock_code=stock_code, is_closed=False).last()
        if loop:
            loop.close_record = trade_record
            loop.is_closed = True
            loop.closed_at = trade_record.timestamp
            # 计算盈亏
            if loop.loop_type == 'buy_sell':
                loop.profit = (Decimal(str(price)) - loop.open_record.price) * Decimal(str(volume))
            else:
                loop.profit = (loop.open_record.price - Decimal(str(price))) * Decimal(str(volume))
            loop.save()
            
        # 清除设置中的待闭环状态
        setting.pending_loop_type = None
        setting.pending_price = None
        setting.pending_volume = None
        setting.pending_timestamp = None
        setting.save()
        
    return {
        'id': trade_record.id,
        'stock_code': trade_record.stock_code,
        'trade_type': trade_record.trade_type,
        'price': float(trade_record.price),
        'volume': trade_record.volume,
        'amount': float(trade_record.amount),
        'reason': trade_record.reason,
        'timestamp': trade_record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    }

def get_trade_records_sync(stock_code):
    """获取交易记录（同步函数）"""
    records = TradeRecord.objects.filter(stock_code=stock_code).order_by('-timestamp')[:50]
    result = []
    for record in records:
        result.append({
            'id': record.id,
            'stock_code': record.stock_code,
            'trade_type': record.trade_type,
            'price': float(record.price),
            'volume': record.volume,
            'amount': float(record.amount),
            'reason': record.reason,
            'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
        })
    return result

def update_trade_loop_sync(setting, trade_record):
    """更新交易闭环状态（同步函数）"""
    if setting.pending_loop_type is None:
        # 开启新闭环
        setting.pending_loop_type = 'buy_first' if trade_record.trade_type == 'buy' else 'sell_first'
        setting.pending_price = trade_record.price
        setting.pending_volume = trade_record.volume
        setting.pending_timestamp = trade_record.timestamp
        setting.save()
        
        # 创建待闭环记录
        TradeLoop.objects.create(
            stock_code=setting.stock_code,
            loop_type='buy_sell' if trade_record.trade_type == 'buy' else 'sell_buy',
            open_record=trade_record,
            is_closed=False
        )
    else:
        # 完成闭环
        loop = TradeLoop.objects.filter(stock_code=setting.stock_code, is_closed=False).last()
        if loop:
            loop.close_record = trade_record
            loop.is_closed = True
            loop.closed_at = trade_record.timestamp
            # 计算盈亏：(卖出价 - 买入价) * 数量
            if loop.loop_type == 'buy_sell':
                loop.profit = (trade_record.price - loop.open_record.price) * Decimal(str(trade_record.volume))
            else:
                loop.profit = (loop.open_record.price - trade_record.price) * Decimal(str(trade_record.volume))
            loop.save()
            
        # 清除设置中的待闭环状态
        setting.pending_loop_type = None
        setting.pending_price = None
        setting.pending_volume = None
        setting.pending_timestamp = None
        setting.save()

def get_trade_loops_sync(stock_code):
    """获取闭环交易记录（同步函数）"""
    loops = TradeLoop.objects.filter(stock_code=stock_code)\
        .select_related('open_record', 'close_record')\
        .order_by('-created_at')[:20]
    result = []
    for loop in loops:
        result.append({
            'id': loop.id,
            'loop_type': loop.loop_type,
            'loop_type_display': loop.get_loop_type_display(),
            'open_price': float(loop.open_record.price),
            'open_volume': loop.open_record.volume,
            'open_time': loop.open_record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'close_price': float(loop.close_record.price) if loop.close_record else None,
            'close_volume': loop.close_record.volume if loop.close_record else None,
            'close_time': loop.close_record.timestamp.strftime('%Y-%m-%d %H:%M:%S') if loop.close_record else None,
            'is_closed': loop.is_closed,
            'profit': float(loop.profit),
            'created_at': loop.created_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    return result

class StockDataConsumer(AsyncWebsocketConsumer):
    """
    股票数据WebSocket消费者
    处理实时股票数据的WebSocket连接
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stock_code = None
        self.monitoring = False
        self.monitor_task = None
    
    async def connect(self):
        """处理WebSocket连接"""
        # 获取股票代码
        self.stock_code = self.scope['url_route']['kwargs']['stock_code']
        
        # 接受连接
        await self.accept()
        
        # 发送初始连接消息
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': '连接已建立',
            'stock_code': self.stock_code
        }))
    
    async def disconnect(self, close_code):
        """处理WebSocket断开连接"""
        # 停止监控
        await self.stop_monitoring()
    
    async def receive(self, text_data):
        """处理从客户端接收的消息"""
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'start_monitoring':
            await self.start_monitoring()
        elif message_type == 'stop_monitoring':
            await self.stop_monitoring()
    
    async def start_monitoring(self):
        """开始监控股票数据"""
        if self.monitoring:
            return
        
        self.monitoring = True
        
        # 发送开始监控消息
        await self.send(text_data=json.dumps({
            'type': 'monitoring_status',
            'status': 'started',
            'message': '开始监控股票数据'
        }))
        
        # 启动监控任务
        self.monitor_task = asyncio.create_task(self.monitor_stock_data())
    
    async def stop_monitoring(self):
        """停止监控股票数据"""
        self.monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            self.monitor_task = None
        
        # 发送停止监控消息
        await self.send(text_data=json.dumps({
            'type': 'monitoring_status',
            'status': 'stopped',
            'message': '停止监控股票数据'
        }))
    
    async def monitor_stock_data(self):
        """监控股票数据，定时获取并发送给客户端"""
        try:
            while self.monitoring:
                # 获取股票数据
                stock_data = await sync_to_async(StockDataService.get_stock_data)(self.stock_code)
                
                if stock_data:
                    # 获取交易设置（返回字典）
                    trade_setting = await sync_to_async(get_trade_setting_sync)(self.stock_code)
                    
                    # 获取账户信息（返回字典）
                    account = await sync_to_async(get_account_sync)(self.stock_code)
                    
                    # 检查交易条件
                    should_trade, trade_type, reason = await sync_to_async(StockDataService.check_trade_condition)(
                        stock_data, 
                        trade_setting
                    )
                    
                    trade_record = None
                    
                    if should_trade:
                        # 执行交易
                        if trade_type == 'buy':
                            # 计算买入股数
                            if trade_setting['pending_loop_type'] == 'sell_first':
                                # 如果是卖出闭环，买入数量必须等于之前的卖出数量
                                trade_volume = trade_setting['pending_volume']
                            elif trade_setting['buy_shares']:
                                trade_volume = trade_setting['buy_shares']
                            else:
                                # 计算交易数量，向下取整到100股的倍数
                                _temp_buy_amount = Decimal(str(trade_setting['buy_amount'] or '10000'))
                                _temp_price = Decimal(str(stock_data['current_price']))
                                trade_volume = int(_temp_buy_amount / _temp_price / Decimal('100')) * 100
                            
                            # 确保是100股的倍数且至少100股
                            trade_volume = max(100, (trade_volume // 100) * 100)
                            
                            # 计算实际交易金额
                            current_price = Decimal(str(stock_data['current_price']))
                            actual_trade_amount = current_price * Decimal(str(trade_volume))
                            
                            # 检查账户余额是否足够
                            if Decimal(str(account['balance'])) >= actual_trade_amount:
                                # 保存交易记录并更新闭环
                                trade_record = await sync_to_async(create_trade_and_update_loop_sync)(
                                    self.stock_code,
                                    'buy',
                                    stock_data['current_price'],
                                    trade_volume,
                                    actual_trade_amount,
                                    reason
                                )
                                
                                # 更新账户信息
                                account = await sync_to_async(update_account_after_trade_sync)(
                                    self.stock_code,
                                    'buy',
                                    trade_volume,
                                    actual_trade_amount
                                )
                                
                                # 重新获取交易设置以获取最新闭环状态
                                trade_setting = await sync_to_async(get_trade_setting_sync)(self.stock_code)
                        
                        elif trade_type == 'sell':
                            # 计算卖出股数
                            if trade_setting['pending_loop_type'] == 'buy_first':
                                # 如果是买入闭环，卖出数量必须等于之前的买入数量
                                trade_volume = trade_setting['pending_volume']
                            elif trade_setting['sell_shares']:
                                trade_volume = trade_setting['sell_shares']
                            else:
                                # 计算交易数量，向下取整到100股的倍数
                                _temp_sell_amount = Decimal(str(trade_setting['sell_amount'] or '10000'))
                                _temp_price = Decimal(str(stock_data['current_price']))
                                trade_volume = int(_temp_sell_amount / _temp_price / Decimal('100')) * 100
                            
                            # 确保是100股的倍数且至少100股
                            trade_volume = max(100, (trade_volume // 100) * 100)
                            
                            # 检查可用持股数量是否足够（T+1）
                            if account['available_shares'] >= trade_volume:
                                # 计算实际交易金额
                                current_price = Decimal(str(stock_data['current_price']))
                                actual_trade_amount = current_price * Decimal(str(trade_volume))
                                
                                # 保存交易记录并更新闭环
                                trade_record = await sync_to_async(create_trade_and_update_loop_sync)(
                                    self.stock_code,
                                    'sell',
                                    stock_data['current_price'],
                                    trade_volume,
                                    actual_trade_amount,
                                    reason
                                )
                                
                                # 更新账户信息
                                account = await sync_to_async(update_account_after_trade_sync)(
                                    self.stock_code,
                                    'sell',
                                    trade_volume,
                                    actual_trade_amount
                                )
                                
                                # 重新获取交易设置以获取最新闭环状态
                                trade_setting = await sync_to_async(get_trade_setting_sync)(self.stock_code)
                    
                    # 获取最新的交易记录和闭环记录
                    trade_records_list = await sync_to_async(get_trade_records_sync)(self.stock_code)
                    trade_loops_list = await sync_to_async(get_trade_loops_sync)(self.stock_code)
                    
                    # 发送股票数据给客户端
                    await self.send(text_data=json.dumps({
                        'type': 'stock_data',
                        'stock_data': stock_data,
                        'account': {
                            'balance': float(account['balance']),
                            'shares': account['shares'],
                            'available_shares': account['available_shares']
                        },
                        'trade_setting': {
                            'pending_loop_type': trade_setting['pending_loop_type'],
                            'pending_price': float(trade_setting['pending_price']) if trade_setting['pending_price'] else None,
                            'pending_volume': trade_setting['pending_volume'],
                            'pending_timestamp': trade_setting['pending_timestamp'].strftime('%Y-%m-%d %H:%M:%S') if trade_setting['pending_timestamp'] else None,
                            'overnight_sell_ratio': float(trade_setting['overnight_sell_ratio']),
                            'overnight_buy_ratio': float(trade_setting['overnight_buy_ratio']),
                        },
                        'trade_record': trade_record,
                        'trade_records': trade_records_list,
                        'trade_loops': trade_loops_list
                    }))
                else:
                    # 股票数据获取失败，发送错误信息
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'获取股票 {self.stock_code} 数据失败，请检查网络连接或股票代码是否正确',
                        'stock_code': self.stock_code
                    }))
                
                # 等待一段时间后再次获取数据
                await asyncio.sleep(5)  # 每5秒获取一次数据
        except asyncio.CancelledError:
            # 任务被取消，正常退出
            pass
        except Exception as e:
            # 发送错误消息
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
