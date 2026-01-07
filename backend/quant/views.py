from rest_framework import viewsets, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.utils import timezone
from decimal import Decimal

from .models import StockData, TradeRecord, TradeSetting, Account
from .services.stock_service import StockDataService

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
        
        # 确保获取或创建交易设置
        trade_setting, created = TradeSetting.objects.get_or_create(
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
        
        # 确保交易设置是活跃的
        if not trade_setting.is_active:
            trade_setting.is_active = True
            trade_setting.save()
        
        trade_settings = [trade_setting]
        
        for setting in trade_settings:
            # 检查交易条件
            should_trade, trade_type, reason = StockDataService.check_trade_condition(
                stock_data, 
                setting.sell_threshold, 
                setting.buy_threshold
            )
            
            if should_trade:
                # 执行交易
                trade_volume = 0
                actual_trade_amount = Decimal('0.00')
                
                if trade_type == 'buy':
                    # 计算买入股数
                    if setting.buy_shares:
                        # 使用买入股数
                        trade_volume = setting.buy_shares
                    else:
                        # 使用买入金额
                        buy_amount = setting.buy_amount or Decimal('10000')
                        # 计算交易数量，向下取整到100股的倍数
                        trade_volume = int(buy_amount / stock_data['current_price'] / Decimal('100')) * 100
                    
                    # 确保是100股的倍数且至少100股
                    trade_volume = max(100, (trade_volume // 100) * 100)
                    
                    # 计算实际交易金额
                    actual_trade_amount = stock_data['current_price'] * Decimal(str(trade_volume))
                    
                    # 检查账户余额是否足够
                    if account.balance >= actual_trade_amount:
                        # 更新账户信息
                        account.balance -= actual_trade_amount
                        account.shares += trade_volume
                        # T+1机制：买入的股票当天不可卖出
                        # available_shares保持不变，新买入的股票明天才能卖出
                        account.save()
                        
                        # 保存交易记录
                        trade_record = TradeRecord(
                            stock_code=stock_code,
                            trade_type='buy',  # 明确指定为买入类型
                            price=stock_data['current_price'],
                            volume=trade_volume,
                            amount=actual_trade_amount,
                            reason=reason
                        )
                        trade_record.save()
                
                elif trade_type == 'sell':
                    # 计算卖出股数
                    if setting.sell_shares:
                        # 使用卖出股数
                        trade_volume = setting.sell_shares
                    else:
                        # 使用卖出金额
                        sell_amount = setting.sell_amount or Decimal('10000')
                        # 计算交易数量，向下取整到100股的倍数
                        trade_volume = int(sell_amount / stock_data['current_price'] / Decimal('100')) * 100
                    
                    # 确保是100股的倍数且至少100股
                    trade_volume = max(100, (trade_volume // 100) * 100)
                    
                    # 检查可用持股数量是否足够（T+1）
                    if account.available_shares >= trade_volume:
                        # 计算实际交易金额
                        actual_trade_amount = stock_data['current_price'] * Decimal(str(trade_volume))
                        
                        # 更新账户信息
                        account.balance += actual_trade_amount
                        account.shares -= trade_volume
                        account.available_shares -= trade_volume
                        account.save()
                        
                        # 保存交易记录
                        trade_record = TradeRecord(
                            stock_code=stock_code,
                            trade_type='sell',  # 明确指定为卖出类型
                            price=stock_data['current_price'],
                            volume=trade_volume,
                            amount=actual_trade_amount,
                            reason=reason
                        )
                        trade_record.save()
        
        return Response({
            'stock_code': stock_data['stock_code'],
            'current_price': float(stock_data['current_price']),
            'average_price': float(stock_data['average_price']),
            'volume': stock_data['volume'],
            'price_diff': stock_data['price_diff'],
            'price_diff_percent': stock_data['price_diff_percent'],
            'timestamp': stock_data['timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
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
            # 清空交易记录
            TradeRecord.objects.filter(stock_code=stock_code).delete()
            
            return Response({
                'message': '交易记录已成功清空'
            })
    except Exception as e:
        return Response({
            'error': str(e),
            'message': f'{"获取交易记录失败" if request.method == "GET" else "清空交易记录失败"}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def update_trade_setting(request):
    """
    更新交易设置
    
    Args:
        request: HTTP请求，包含交易设置参数
        
    Returns:
        Response: 更新结果
    """
    try:
        data = request.data
        stock_code = data.get('stock_code')
        
        if not stock_code:
            return Response({
                'error': '股票代码不能为空',
                'message': '请提供股票代码'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 处理买入金额和买入股数的互斥关系
        buy_amount = data.get('buy_amount')
        buy_shares = data.get('buy_shares')
        sell_amount = data.get('sell_amount')
        sell_shares = data.get('sell_shares')
        
        # 获取或创建交易设置
        trade_setting, created = TradeSetting.objects.get_or_create(
            stock_code=stock_code,
            defaults={
                'sell_threshold': Decimal(str(data.get('sell_threshold', 0.5))),
                'buy_threshold': Decimal(str(data.get('buy_threshold', 0.5))),
                'buy_amount': Decimal(str(buy_amount)) if buy_amount is not None else None,
                'sell_amount': Decimal(str(sell_amount)) if sell_amount is not None else None,
                'buy_shares': buy_shares,
                'sell_shares': sell_shares,
                'update_interval': data.get('update_interval', 5),
                'is_active': True
            }
        )
        
        # 更新交易设置
        if not created:
            trade_setting.sell_threshold = Decimal(str(data.get('sell_threshold', trade_setting.sell_threshold)))
            trade_setting.buy_threshold = Decimal(str(data.get('buy_threshold', trade_setting.buy_threshold)))
            trade_setting.buy_amount = Decimal(str(buy_amount)) if buy_amount is not None else None
            trade_setting.sell_amount = Decimal(str(sell_amount)) if sell_amount is not None else None
            trade_setting.buy_shares = buy_shares
            trade_setting.sell_shares = sell_shares
            trade_setting.update_interval = data.get('update_interval', trade_setting.update_interval)
            trade_setting.is_active = True
            trade_setting.save()
        
        return Response({
            'message': '交易设置更新成功',
            'data': {
                'stock_code': trade_setting.stock_code,
                'sell_threshold': float(trade_setting.sell_threshold),
                'buy_threshold': float(trade_setting.buy_threshold),
                'buy_amount': float(trade_setting.buy_amount) if trade_setting.buy_amount else None,
                'sell_amount': float(trade_setting.sell_amount) if trade_setting.sell_amount else None,
                'buy_shares': trade_setting.buy_shares,
                'sell_shares': trade_setting.sell_shares,
                'update_interval': trade_setting.update_interval,
                'is_active': trade_setting.is_active
            }
        })
    except Exception as e:
        return Response({
            'error': str(e),
            'message': '更新交易设置失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def update_account(request):
    """
    更新账户设置
    
    Args:
        request: HTTP请求，包含账户设置参数
        
    Returns:
        Response: 更新结果
    """
    try:
        data = request.data
        stock_code = data.get('stock_code')
        
        if not stock_code:
            return Response({
                'error': '股票代码不能为空',
                'message': '请提供股票代码'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 获取或创建账户信息
        account, created = Account.objects.get_or_create(
            stock_code=stock_code,
            defaults={
                'balance': Decimal(str(data.get('balance', 100000.00))),
                'shares': data.get('shares', 3000),
                'available_shares': data.get('available_shares', 3000)
            }
        )
        
        # 更新账户信息
        account.balance = Decimal(str(data.get('balance', account.balance)))
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
        return Response({
            'error': str(e),
            'message': '更新账户设置失败'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)