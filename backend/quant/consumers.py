# quant/consumers.py
import asyncio
import json
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from quant.services.stock_service import StockDataService
from quant.models import TradeSetting, Account, TradeRecord
from decimal import Decimal

# 同步辅助函数
def get_trade_setting_sync(stock_code):
    """获取或创建交易设置（同步函数）"""
    return TradeSetting.objects.get_or_create(
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

def get_account_sync(stock_code):
    """获取或创建账户信息（同步函数）"""
    return Account.objects.get_or_create(
        stock_code=stock_code,
        defaults={
            'balance': Decimal('100000.00'),
            'shares': 3000,
            'available_shares': 3000
        }
    )

def save_account_sync(account):
    """保存账户信息（同步函数）"""
    account.save()

def create_trade_record_sync(
    stock_code, trade_type, price, volume, amount, reason
):
    """创建交易记录（同步函数）"""
    return TradeRecord.objects.create(
        stock_code=stock_code,
        trade_type=trade_type,
        price=price,
        volume=volume,
        amount=amount,
        reason=reason
    )

def get_trade_records_sync(stock_code):
    """获取交易记录（同步函数）"""
    return list(
        TradeRecord.objects.filter(stock_code=stock_code)
        .order_by('-timestamp')[:50]
    )

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
                    # 获取或创建交易设置
                    trade_setting, _ = await sync_to_async(get_trade_setting_sync)(self.stock_code)
                    
                    # 获取或创建账户信息
                    account, _ = await sync_to_async(get_account_sync)(self.stock_code)
                    
                    # 检查交易条件
                    should_trade, trade_type, reason = await sync_to_async(StockDataService.check_trade_condition)(
                        stock_data, 
                        trade_setting.sell_threshold, 
                        trade_setting.buy_threshold
                    )
                    
                    trade_record = None
                    
                    if should_trade:
                        # 执行交易
                        if trade_type == 'buy':
                            # 计算买入股数
                            if trade_setting.buy_shares:
                                trade_volume = trade_setting.buy_shares
                            else:
                                buy_amount = trade_setting.buy_amount or Decimal('10000')
                            current_price = Decimal(str(stock_data['current_price']))
                            trade_volume = int(buy_amount / current_price / Decimal('100')) * 100
                            
                            # 确保是100股的倍数且至少100股
                            trade_volume = max(100, (trade_volume // 100) * 100)
                            
                            # 计算实际交易金额
                            actual_trade_amount = current_price * Decimal(str(trade_volume))
                            
                            # 检查账户余额是否足够
                            if account.balance >= actual_trade_amount:
                                # 更新账户信息
                                account.balance -= actual_trade_amount
                                account.shares += trade_volume
                                # T+1机制：买入的股票当天不可卖出
                                # available_shares保持不变，新买入的股票明天才能卖出
                                await sync_to_async(save_account_sync)(account)
                                
                                # 保存交易记录
                                trade_record = await sync_to_async(create_trade_record_sync)(
                                    self.stock_code,
                                    'buy',
                                    stock_data['current_price'],
                                    trade_volume,
                                    actual_trade_amount,
                                    reason
                                )
                        
                        elif trade_type == 'sell':
                            # 计算卖出股数
                            if trade_setting.sell_shares:
                                trade_volume = trade_setting.sell_shares
                            else:
                                sell_amount = trade_setting.sell_amount or Decimal('10000')
                            current_price = Decimal(str(stock_data['current_price']))
                            trade_volume = int(sell_amount / current_price / Decimal('100')) * 100
                            
                            # 确保是100股的倍数且至少100股
                            trade_volume = max(100, (trade_volume // 100) * 100)
                            
                            # 检查可用持股数量是否足够（T+1）
                            if account.available_shares >= trade_volume:
                                # 计算实际交易金额
                                actual_trade_amount = current_price * Decimal(str(trade_volume))
                                
                                # 更新账户信息
                                account.balance += actual_trade_amount
                                account.shares -= trade_volume
                                account.available_shares -= trade_volume
                                await sync_to_async(save_account_sync)(account)
                                
                                # 保存交易记录
                                trade_record = await sync_to_async(create_trade_record_sync)(
                                    self.stock_code,
                                    'sell',
                                    stock_data['current_price'],
                                    trade_volume,
                                    actual_trade_amount,
                                    reason
                                )
                    
                    # 获取最新的交易记录
                    trade_records = await sync_to_async(get_trade_records_sync)(self.stock_code)
                    
                    # 构建交易记录列表
                    trade_records_list = []
                    for record in trade_records:
                        trade_records_list.append({
                            'id': record.id,
                            'stock_code': record.stock_code,
                            'trade_type': record.trade_type,
                            'price': float(record.price),
                            'volume': record.volume,
                            'amount': float(record.amount),
                            'reason': record.reason,
                            'timestamp': record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                        })
                    
                    # 发送股票数据给客户端
                    await self.send(text_data=json.dumps({
                        'type': 'stock_data',
                        'stock_data': stock_data,
                        'account': {
                            'balance': float(account.balance),
                            'shares': account.shares,
                            'available_shares': account.available_shares
                        },
                        'trade_record': trade_record and {
                        'id': trade_record.id,
                        'stock_code': trade_record.stock_code,
                        'trade_type': trade_record.trade_type,
                        'price': float(trade_record.price),
                        'volume': trade_record.volume,
                        'amount': float(trade_record.amount),
                        'reason': trade_record.reason,
                        'timestamp': trade_record.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                    } or None,
                        'trade_records': trade_records_list
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
