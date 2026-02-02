# quant/consumers.py
import asyncio
import json
import os
from datetime import datetime
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from quant.services.stock_service import StockDataService, send_execution_request
# from quant.services.monitor_manager import monitor_manager # 移动到方法内
from quant.models import TradeSetting, Account, TradeRecord, TradeLoop
from decimal import Decimal
from django.utils import timezone

# 同步辅助函数
def get_trade_setting_sync(stock_code):
    """获取交易设置（同步函数）"""
    try:
        # 使用 values() 直接获取字典数据，绕过模型实例缓存
        setting_dict = TradeSetting.objects.filter(stock_code=stock_code).values().first()
        
        if not setting_dict:
            print(f"DEBUG WS: 未找到股票 {stock_code} 的设置，创建新设置")
            new_setting = TradeSetting.objects.create(
                stock_code=stock_code,
                sell_threshold=Decimal('0.5'),
                buy_threshold=Decimal('0.5'),
                update_interval=5,
                is_active=True,
                is_executing=False
            )
            setting_dict = TradeSetting.objects.filter(id=new_setting.id).values().first()
        else:
            print(f"DEBUG WS: 获取到股票 {stock_code} 的设置, pending_type={setting_dict.get('pending_loop_type')}")
        
        # 将 Decimal 转换为 float，处理 datetime
        if setting_dict:
            for key, value in setting_dict.items():
                if isinstance(value, Decimal):
                    setting_dict[key] = float(value)
                elif isinstance(value, datetime):
                    setting_dict[key] = value.strftime('%Y-%m-%d %H:%M:%S')
                    
        return setting_dict
    except Exception as e:
        print(f"获取交易设置失败: {e}")
        return None

def get_account_sync(stock_code):
    """获取账户信息（同步函数，包含T+1同步逻辑）"""
    account, created = Account.objects.get_or_create(
        stock_code=stock_code,
        defaults={
            'balance': Decimal('100000.00'),
            'shares': 3000,
            'available_shares': 3000
        }
    )
    
    # T+1 同步逻辑：如果当前日期大于上次更新日期，则将可用持仓同步为当前总持仓
    now = timezone.now()
    if not created and account.updated_at.date() < now.date():
        old_available = account.available_shares
        account.available_shares = account.shares
        account.save()
        print(f"DEBUG WS: 账户 {stock_code} 可用持仓已根据 T+1 规则同步: {old_available} -> {account.available_shares}")
    
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
    setting_query = TradeSetting.objects.filter(stock_code=stock_code)
    setting = setting_query.first()
    if setting.pending_loop_type is None:
        # 开启新闭环
        setting_query.update(
            pending_loop_type='buy_first' if trade_type == 'buy' else 'sell_first',
            pending_price=price,
            pending_volume=volume,
            pending_timestamp=trade_record.timestamp
        )
        
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
        setting_query.update(
            pending_loop_type=None,
            pending_price=None,
            pending_volume=None,
            pending_timestamp=None
        )
        
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
    setting_query = TradeSetting.objects.filter(stock_code=setting.stock_code)
    if setting.pending_loop_type is None:
        # 开启新闭环
        setting_query.update(
            pending_loop_type='buy_first' if trade_record.trade_type == 'buy' else 'sell_first',
            pending_price=trade_record.price,
            pending_volume=trade_record.volume,
            pending_timestamp=trade_record.timestamp
        )
        
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
        setting_query.update(
            pending_loop_type=None,
            pending_price=None,
            pending_volume=None,
            pending_timestamp=None
        )

def set_trade_executing_sync(stock_code, is_executing):
    """更新交易执行状态（同步函数）"""
    TradeSetting.objects.filter(stock_code=stock_code).update(is_executing=is_executing)

def try_lock_trade_executing_sync(stock_code):
    """尝试获取交易执行锁（原子操作）"""
    # 仅当 is_executing 为 False 时，才更新为 True
    updated_count = TradeSetting.objects.filter(
        stock_code=stock_code, 
        is_executing=False
    ).update(is_executing=True)
    return updated_count > 0

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
        self.stock_name = "未知股票"
        self.monitoring = False
        self.monitor_task = None
        self.recorded_data = []
        self.record_data_enabled = False
        self.mock_file_path = None
    
    async def connect(self):
        """处理WebSocket连接"""
        # 获取股票代码
        self.stock_code = self.scope['url_route']['kwargs']['stock_code']
        self.group_name = f"stock_{self.stock_code}"
        
        # 加入频道组
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
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
        # 离开频道组
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """处理从客户端接收的消息"""
        text_data_json = json.loads(text_data)
        message_type = text_data_json.get('type')
        
        if message_type == 'start_monitoring':
            self.record_data_enabled = text_data_json.get('record_data', False)
            self.mock_file_path = text_data_json.get('mock_file_path')
            await self.start_monitoring()
        elif message_type == 'stop_monitoring':
            await self.stop_monitoring()
    
    async def start_monitoring(self):
        """开始监控股票数据"""
        try:
            from quant.services.monitor_manager import monitor_manager
            # 调用全局监控管理器启动任务
            print(f"DEBUG WS: 正在为 {self.stock_code} 启动监控任务...")
            await monitor_manager.start_monitoring(
                self.stock_code, 
                self.record_data_enabled, 
                self.mock_file_path
            )
            
            self.monitoring = True
            
            # 发送开始监控消息
            await self.send(text_data=json.dumps({
                'type': 'monitoring_status',
                'status': 'started',
                'message': '后台监控任务已启动'
            }))
            print(f"DEBUG WS: {self.stock_code} 监控任务启动成功消息已发送")
        except Exception as e:
            print(f"ERROR WS: 启动监控任务失败 {self.stock_code}: {e}")
            import traceback
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'启动监控失败: {str(e)}'
            }))

    async def stop_monitoring(self):
        """停止监控股票数据"""
        if not self.monitoring:
            return
            
        from quant.services.monitor_manager import monitor_manager
        # 调用全局监控管理器停止任务
        await monitor_manager.stop_monitoring(self.stock_code)
        
        self.monitoring = False
        
        # 发送停止监控消息
        await self.send(text_data=json.dumps({
            'type': 'monitoring_status',
            'status': 'stopped',
            'message': '后台监控任务已停止'
        }))

    async def stock_update(self, event):
        """处理来自频道组的股票更新消息"""
        try:
            # 使用自定义 JSON 序列化处理 Decimal 等类型
            class DecimalEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, Decimal):
                        return float(obj)
                    if isinstance(obj, datetime):
                        return obj.strftime('%Y-%m-%d %H:%M:%S')
                    return super(DecimalEncoder, self).default(obj)

            payload = json.dumps(event['data'], cls=DecimalEncoder)
            await self.send(text_data=payload)
        except Exception as e:
            print(f"ERROR WS: 序列化或发送数据失败: {e}")
            import traceback
            traceback.print_exc()
            # 尝试发送错误消息，但不抛出异常以防止 1011 错误
            try:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'数据转发失败: {str(e)}'
                }))
            except:
                pass


