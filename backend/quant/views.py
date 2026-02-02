from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from .models import StockData, TradeRecord, TradeSetting, Account, TradeLoop
from .services.stock_service import StockDataService, send_execution_request

def safe_decimal(value, default=None):
    """
    安全地将值转换为 Decimal，如果为空或无效则返回 default (默认为 None)
    """
    if value is None:
        return default
    
    val_str = str(value).strip()
    if val_str == '' or val_str.lower() == 'null' or val_str.lower() == 'undefined':
        return default
        
    try:
        # 如果已经是 Decimal，直接返回
        if isinstance(value, Decimal):
            return value
        return Decimal(val_str)
    except Exception as e:
        print(f"Decimal 转换失败: value={value}, type={type(value)}, error={e}")
        return default

class StockDataViewSet(viewsets.ReadOnlyModelViewSet):
    """
    股票数据视图集
    """
    queryset = StockData.objects.all()
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

class TradeRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """
    交易记录视图集
    """
    queryset = TradeRecord.objects.all()
    ordering_fields = ['timestamp']
    ordering = ['-timestamp']

class TradeSettingViewSet(viewsets.ModelViewSet):
    """
    交易设置视图集
    """
    queryset = TradeSetting.objects.all()
    
@api_view(['GET'])
def get_stock_realtime_data(request, stock_code):
    """
    获取股票实时数据
    
    Args:
        request: HTTP请求
        stock_code: 股票代码
        
    Returns:
        Response: 股票实时数据
    """
    try:
        # 获取股票数据
        stock_data = StockDataService.get_stock_data(stock_code)
        
        if stock_data is None:
            return Response(
                {"error": "获取股票数据失败", "message": f"无法获取股票 {stock_code} 的数据"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # 保存到数据库
        stock_data_model = StockData(
            stock_code=stock_data['stock_code'],
            current_price=stock_data['current_price'],
            average_price=stock_data['average_price'],
            volume=stock_data['volume'],
            timestamp=stock_data['timestamp']
        )
        stock_data_model.save()
        
        # 获取或创建账户信息
        account, created = Account.objects.get_or_create(
            stock_code=stock_code,
            defaults={
                'balance': 100000.00,
                'shares': 3000,
                'available_shares': 3000
            }
        )
        
        # 检查是否需要更新可用持仓（每日更新 T+1）
        # 如果当前日期大于上次更新日期，则将可用持仓同步为当前总持仓
        now = timezone.now()
        if account.updated_at.date() < now.date():
            account.available_shares = account.shares
            account.save()
            print(f"DEBUG: 账户 {stock_code} 可用持仓已根据 T+1 规则更新: {account.available_shares}")
        
        # 确保获取或创建交易设置
        trade_setting, created = TradeSetting.objects.get_or_create(
            stock_code=stock_code,
            defaults={
                'sell_threshold': Decimal('0.5'),
                'buy_threshold': Decimal('0.5'),
                'update_interval': 5,
                'is_active': True
            }
        )
        
        # 确保交易设置是活跃的
        if not trade_setting.is_active:
            TradeSetting.objects.filter(stock_code=stock_code).update(is_active=True)
        
        return Response({
            'stock_code': stock_data['stock_code'],
            'current_price': float(stock_data['current_price']),
            'average_price': float(stock_data['average_price']),
            'volume': stock_data['volume'],
            'price_diff': stock_data['price_diff'],
            'price_diff_percent': stock_data['price_diff_percent'],
            'timestamp': stock_data['timestamp'],
            'account': {
                'balance': float(account.balance),
                'shares': account.shares,
                'available_shares': account.available_shares
            }
        })
    except Exception as e:
        return Response({
            'error': str(e),
            'message': '获取股票数据失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'DELETE'])
def trade_records(request, stock_code):
    """
    处理股票交易记录的GET和DELETE请求
    
    Args:
        request: HTTP请求
        stock_code: 股票代码
        
    Returns:
        Response: 交易记录列表或清空结果
    """
    try:
        if request.method == 'GET':
            # 获取交易记录
            trade_records = TradeRecord.objects.filter(stock_code=stock_code).order_by('-timestamp')[:50]
            
            result = []
            for record in trade_records:
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
            
            return Response(result)
        elif request.method == 'DELETE':
            print(f"DEBUG: 清空股票 {stock_code} 的交易记录和挂起状态")
            # 清空交易记录
            TradeRecord.objects.filter(stock_code=stock_code).delete()
            # 同时清空关联的闭环记录
            TradeLoop.objects.filter(stock_code=stock_code).delete()
            
            # 同时清空交易设置中的待处理字段 (pending_loop_type 等)
            updated_count = TradeSetting.objects.filter(stock_code=stock_code).update(
                pending_loop_type=None,
                pending_price=None,
                pending_volume=None,
                pending_timestamp=None
            )
            print(f"DEBUG: 已更新 {updated_count} 个交易设置记录")
            
            return Response({
                'message': '交易记录、闭环交易及挂起状态已成功清空'
            })
    except Exception as e:
        return Response({
            'error': str(e),
            'message': f'{"获取交易记录失败" if request.method == "GET" else "清空交易记录失败"}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def trade_loops(request, stock_code):
    """
    获取股票闭环交易记录
    
    Args:
        request: HTTP请求
        stock_code: 股票代码
        
    Returns:
        Response: 闭环交易记录列表
    """
    try:
        # 获取闭环交易记录
        loops = TradeLoop.objects.filter(stock_code=stock_code).order_by('-created_at')[:50]
        
        result = []
        for loop in loops:
            result.append({
                'id': loop.id,
                'stock_code': loop.stock_code,
                'loop_type': loop.loop_type,
                'loop_type_display': loop.get_loop_type_display(),
                'open_price': float(loop.open_record.price),
                'open_volume': loop.open_record.volume,
                'open_time': loop.open_record.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'close_price': float(loop.close_record.price) if loop.close_record else None,
                'close_time': loop.close_record.timestamp.strftime('%Y-%m-%d %H:%M:%S') if loop.close_record else None,
                'is_closed': loop.is_closed,
                'profit': float(loop.profit)
            })
        
        return Response(result)
    except Exception as e:
        return Response({
            'error': str(e),
            'message': '获取闭环交易记录失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
def update_trade_setting(request):
    """
    获取或更新交易设置
    
    Args:
        request: HTTP请求
        
    Returns:
        Response: 交易设置数据或更新结果
    """
    try:
        # 获取或创建交易设置
        if request.method == 'GET':
            stock_code = request.query_params.get('stock_code')
            if not stock_code:
                return Response({
                    'error': '股票代码不能为空',
                    'message': '请提供股票代码'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 获取或创建交易设置
            trade_setting = TradeSetting.objects.filter(stock_code=stock_code).first()
            
            if not trade_setting:
                # 如果不存在，创建一个基础设置
                trade_setting = TradeSetting.objects.create(
                    stock_code=stock_code,
                    sell_threshold=Decimal('0.5'),
                    buy_threshold=Decimal('0.5'),
                    update_interval=5,
                    is_active=False
                )
            
            # 无论是否存在设置，都要同步最新的挂起任务状态
            unclosed_loop = TradeLoop.objects.filter(stock_code=stock_code, is_closed=False).order_by('-created_at').first()
            
            # 同步挂起状态
            if unclosed_loop:
                trade_setting.pending_loop_type = 'buy_first' if unclosed_loop.loop_type == 'buy_sell' else 'sell_first'
                trade_setting.pending_price = unclosed_loop.open_record.price
                trade_setting.pending_volume = unclosed_loop.open_record.volume
                trade_setting.pending_timestamp = unclosed_loop.open_record.timestamp
                trade_setting.save()
                print(f"DEBUG: [GET] 同步挂起任务到设置: {stock_code}, 类型: {trade_setting.pending_loop_type}")
            else:
                # 如果没有未闭环任务，清空挂起状态
                if trade_setting.pending_loop_type:
                    trade_setting.pending_loop_type = None
                    trade_setting.pending_price = None
                    trade_setting.pending_volume = None
                    trade_setting.pending_timestamp = None
                    trade_setting.save()
                    print(f"DEBUG: [GET] 清空挂起任务状态: {stock_code}")
        else:
            data = request.data
            stock_code = data.get('stock_code')
            print(f"DEBUG: [POST] 收到交易设置更新请求: {stock_code}, data={data}")
            
            if not stock_code:
                return Response({
                    'error': '股票代码不能为空',
                    'message': '请提供股票代码'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # 获取或创建交易设置
            trade_setting, created = TradeSetting.objects.get_or_create(
                stock_code=stock_code,
                defaults={
                    'sell_threshold': safe_decimal(data.get('sell_threshold'), Decimal('0.5')),
                    'buy_threshold': safe_decimal(data.get('buy_threshold'), Decimal('0.5')),
                    'buy_shares': data.get('buy_shares'),
                    'sell_shares': data.get('sell_shares'),
                    'update_interval': data.get('update_interval', 5),
                    'market_stage': data.get('market_stage'),
                    'oscillation_type': data.get('oscillation_type'),
                    'buy_avg_line_range_minus': safe_decimal(data.get('buy_avg_line_range_minus')),
                    'buy_avg_line_range_plus': safe_decimal(data.get('buy_avg_line_range_plus')),
                    'sell_avg_line_range_minus': safe_decimal(data.get('sell_avg_line_range_minus')),
                    'sell_avg_line_range_plus': safe_decimal(data.get('sell_avg_line_range_plus')),
                    'strategy': data.get('strategy', 'grid'),
                    'grid_buy_count': data.get('grid_buy_count'),
                    'grid_sell_count': data.get('grid_sell_count'),
                    'overnight_sell_ratio': safe_decimal(data.get('overnight_sell_ratio'), Decimal('1.0')),
                    'overnight_buy_ratio': safe_decimal(data.get('overnight_buy_ratio'), Decimal('1.0')),
                    'is_active': False
                }
            )
            
            # 更新交易设置
            if not created:
                update_fields = {}
                
                # 基础字段
                for field in ['sell_threshold', 'buy_threshold', 'buy_avg_line_range_minus', 
                             'buy_avg_line_range_plus', 'sell_avg_line_range_minus', 'sell_avg_line_range_plus']:
                    if field in data:
                        update_fields[field] = safe_decimal(data.get(field))
                
                for field in ['buy_shares', 'sell_shares', 'update_interval', 'market_stage', 
                             'oscillation_type', 'strategy', 'grid_buy_count', 'grid_sell_count']:
                    if field in data:
                        update_fields[field] = data.get(field)
                
                # 隔夜比例更新 - 特别处理
                if 'overnight_sell_ratio' in data and data.get('overnight_sell_ratio') is not None:
                    update_fields['overnight_sell_ratio'] = safe_decimal(data.get('overnight_sell_ratio'))
                    print(f"DEBUG: [POST] 更新卖出比例: {stock_code} -> {update_fields['overnight_sell_ratio']}")
                
                if 'overnight_buy_ratio' in data and data.get('overnight_buy_ratio') is not None:
                    update_fields['overnight_buy_ratio'] = safe_decimal(data.get('overnight_buy_ratio'))
                    print(f"DEBUG: [POST] 更新买入比例: {stock_code} -> {update_fields['overnight_buy_ratio']}")
                
                if data.get('is_active') is True:
                    update_fields['is_active'] = True
                
                if update_fields:
                    TradeSetting.objects.filter(id=trade_setting.id).update(**update_fields)
                    # 重新获取以返回最新数据
                    trade_setting.refresh_from_db()

        # 构建返回数据
        resp_data = {
            'stock_code': trade_setting.stock_code,
            'overnight_sell_ratio': float(trade_setting.overnight_sell_ratio) if trade_setting.overnight_sell_ratio is not None else 1.0,
            'overnight_buy_ratio': float(trade_setting.overnight_buy_ratio) if trade_setting.overnight_buy_ratio is not None else 1.0,
            'pending_loop_type': trade_setting.pending_loop_type,
            'pending_price': float(trade_setting.pending_price) if trade_setting.pending_price else None,
            'pending_volume': trade_setting.pending_volume,
            'pending_timestamp': trade_setting.pending_timestamp.strftime('%Y-%m-%d %H:%M:%S') if trade_setting.pending_timestamp else None,
            'sell_threshold': float(trade_setting.sell_threshold) if trade_setting.sell_threshold is not None else 0.5,
            'buy_threshold': float(trade_setting.buy_threshold) if trade_setting.buy_threshold is not None else 0.5,
            'buy_shares': trade_setting.buy_shares,
            'sell_shares': trade_setting.sell_shares,
            'update_interval': trade_setting.update_interval,
            'market_stage': trade_setting.market_stage,
            'oscillation_type': trade_setting.oscillation_type,
            'buy_avg_line_range_minus': float(trade_setting.buy_avg_line_range_minus) if trade_setting.buy_avg_line_range_minus is not None else None,
            'buy_avg_line_range_plus': float(trade_setting.buy_avg_line_range_plus) if trade_setting.buy_avg_line_range_plus is not None else None,
            'sell_avg_line_range_minus': float(trade_setting.sell_avg_line_range_minus) if trade_setting.sell_avg_line_range_minus is not None else None,
            'sell_avg_line_range_plus': float(trade_setting.sell_avg_line_range_plus) if trade_setting.sell_avg_line_range_plus is not None else None,
            'strategy': trade_setting.strategy,
            'grid_buy_count': trade_setting.grid_buy_count,
            'grid_sell_count': trade_setting.grid_sell_count,
            'is_active': trade_setting.is_active,
        }
        
        print(f"DEBUG: [FINAL_RESPONSE] {stock_code} -> sell_ratio: {resp_data['overnight_sell_ratio']}, buy_ratio: {resp_data['overnight_buy_ratio']}")
        
        return Response({
            'message': '获取成功' if request.method == 'GET' else '交易设置更新成功',
            'data': resp_data
        })
    except Exception as e:
        return Response({
            'error': str(e),
            'message': '更新交易设置失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def trade_callback(request):
    """
    执行端完成后的回调接口
    """
    try:
        data = request.data
        raw_stock_code = data.get('symbol')
        action = data.get('action')
        price = Decimal(str(data.get('price')))
        volume = int(data.get('quantity'))
        reason = data.get('reason', '外部执行端回调')
        
        # 统一处理股票代码：去除 sh/sz 前缀，转为纯数字
        stock_code = raw_stock_code
        if isinstance(raw_stock_code, str):
            if raw_stock_code.lower().startswith(('sh', 'sz', 'bj')):
                stock_code = raw_stock_code[2:]
        
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S.%f')
        print(f"\n[EXECUTION_DEBUG] [{timestamp}] 收到执行端回调: {stock_code} (原始: {raw_stock_code}), {action}, {volume}股")
        
        # 获取账户信息
        try:
            account = Account.objects.get(stock_code=stock_code)
        except Account.DoesNotExist:
            print(f"[EXECUTION_DEBUG] [{timestamp}] 错误: 未找到股票 {stock_code} 的账户信息")
            return Response({'status': 'error', 'message': f'未找到股票 {stock_code} 的账户信息'}, status=status.HTTP_404_NOT_FOUND)
            
        # 获取交易设置
        try:
            setting = TradeSetting.objects.get(stock_code=stock_code)
        except TradeSetting.DoesNotExist:
            print(f"[EXECUTION_DEBUG] [{timestamp}] 错误: 未找到股票 {stock_code} 的交易设置")
            return Response({'status': 'error', 'message': f'未找到股票 {stock_code} 的交易设置'}, status=status.HTTP_404_NOT_FOUND)
        
        # 执行交易逻辑记录
        actual_trade_amount = price * Decimal(str(volume))
        
        trade_record = None
        if action == 'buy':
            account.balance -= actual_trade_amount
            account.shares += volume
            # T+1: available_shares 不变
            account.save()
            
            trade_record = TradeRecord(
                stock_code=stock_code,
                trade_type='buy',
                price=price,
                volume=volume,
                amount=actual_trade_amount,
                reason=reason
            )
            trade_record.save()
            
        elif action == 'sell':
            account.balance += actual_trade_amount
            account.shares -= volume
            account.available_shares -= volume
            account.save()
            
            trade_record = TradeRecord(
                stock_code=stock_code,
                trade_type='sell',
                price=price,
                volume=volume,
                amount=actual_trade_amount,
                reason=reason
            )
            trade_record.save()
            
        if trade_record:
            # 更新闭环交易逻辑
            if setting.pending_loop_type:
                # 存在待闭环，尝试闭环
                # 只有类型匹配时才闭环
                is_closing = False
                if setting.pending_loop_type == 'buy_first' and action == 'sell':
                    is_closing = True
                elif setting.pending_loop_type == 'sell_first' and action == 'buy':
                    is_closing = True
                
                if is_closing:
                    # 找到对应的未闭环记录
                    loop = TradeLoop.objects.filter(
                        stock_code=stock_code, 
                        is_closed=False
                    ).order_by('-created_at').first()
                    
                    if loop:
                        loop.close_record = trade_record
                        loop.is_closed = True
                        loop.closed_at = timezone.now()
                        
                        # 计算盈亏
                        if loop.loop_type == 'buy_sell':
                            loop.profit = (trade_record.price - loop.open_record.price) * Decimal(str(loop.open_record.volume))
                        else: # sell_buy
                            loop.profit = (loop.open_record.price - trade_record.price) * Decimal(str(loop.open_record.volume))
                        
                        loop.save()
                        
                        # 清除设置中的待闭环状态
                        TradeSetting.objects.filter(stock_code=stock_code).update(
                            pending_loop_type=None,
                            pending_price=None,
                            pending_volume=None,
                            pending_timestamp=None
                        )
            else:
                # 不存在待闭环，开启新闭环
                loop_type = 'buy_sell' if action == 'buy' else 'sell_buy'
                TradeLoop.objects.create(
                    stock_code=stock_code,
                    loop_type=loop_type,
                    open_record=trade_record,
                    is_closed=False
                )
                
                # 更新设置中的待闭环状态
                TradeSetting.objects.filter(stock_code=stock_code).update(
                    pending_loop_type='buy_first' if action == 'buy' else 'sell_first',
                    pending_price=price,
                    pending_volume=volume,
                    pending_timestamp=timezone.now()
                )

        return Response({'status': 'success', 'message': '交易记录及闭环状态已更新'})
    except Exception as e:
        print(f"回调处理失败: {e}")
        return Response({'status': 'error', 'message': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        # 重置执行状态 (放到 finally 确保即使出错也能释放锁，除非是数据库层面严重的错误)
        TradeSetting.objects.filter(stock_code=stock_code).update(is_executing=False)
        print(f"[EXECUTION_DEBUG] [{timezone.now().strftime('%H:%M:%S.%f')}] 已尝试重置 {stock_code} 的执行锁状态")

@api_view(['GET', 'POST'])
def account_api(request):
    """
    账户设置API (GET 获取, POST 更新)
    """
    try:
        if request.method == 'GET':
            stock_code = request.query_params.get('stock_code')
            if not stock_code:
                return Response({'error': '股票代码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
            
            account, created = Account.objects.get_or_create(
                stock_code=stock_code,
                defaults={
                    'balance': 100000.00,
                    'shares': 3000,
                    'available_shares': 3000
                }
            )
            return Response({
                'balance': float(account.balance),
                'shares': account.shares,
                'available_shares': account.available_shares
            })
        
        elif request.method == 'POST':
            data = request.data
            stock_code = data.get('stock_code')
            
            if not stock_code:
                return Response({'error': '股票代码不能为空'}, status=status.HTTP_400_BAD_REQUEST)
            
            account, created = Account.objects.get_or_create(
                stock_code=stock_code,
                defaults={
                    'balance': safe_decimal(data.get('balance'), Decimal('100000.00')),
                    'shares': data.get('shares', 3000),
                    'available_shares': data.get('available_shares', 3000)
                }
            )
            
            if not created:
                account.balance = safe_decimal(data.get('balance'), account.balance)
                account.shares = data.get('shares', account.shares)
                account.available_shares = data.get('available_shares', account.available_shares)
                account.save()
            
            return Response({
                'message': '账户设置更新成功',
                'data': {
                    'stock_code': account.stock_code,
                    'balance': float(account.balance),
                    'shares': account.shares,
                    'available_shares': account.available_shares
                }
            })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)