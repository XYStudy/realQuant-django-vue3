from django.db import models
from django.utils import timezone

class StockData(models.Model):
    """
    股票实时数据模型
    """
    stock_code = models.CharField(max_length=10, verbose_name='股票代码')
    current_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='当前价格')
    average_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='均价')
    volume = models.IntegerField(verbose_name='成交量')
    timestamp = models.DateTimeField(verbose_name='时间戳')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '股票数据'
        verbose_name_plural = '股票数据'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f'{self.stock_code} - {self.current_price} - {self.timestamp}'

class TradeRecord(models.Model):
    """
    交易记录模型
    """
    TRADE_TYPE_CHOICES = (
        ('buy', '买入'),
        ('sell', '卖出'),
    )
    
    stock_code = models.CharField(max_length=10, verbose_name='股票代码')
    trade_type = models.CharField(max_length=4, choices=TRADE_TYPE_CHOICES, verbose_name='交易类型')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='交易价格')
    volume = models.IntegerField(verbose_name='交易数量')
    amount = models.DecimalField(max_digits=12, decimal_places=2, verbose_name='交易金额')
    reason = models.CharField(max_length=200, verbose_name='交易原因')
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='交易时间')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    
    class Meta:
        verbose_name = '交易记录'
        verbose_name_plural = '交易记录'
        ordering = ['-timestamp']
    
    def __str__(self):
        return f'{self.stock_code} - {self.trade_type} - {self.price} - {self.timestamp}'

class Account(models.Model):
    """
    账户模型，用于 management 账户资金和持股情况
    """
    stock_code = models.CharField(max_length=10, verbose_name='股票代码')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=100000.00, verbose_name='账户余额')
    shares = models.IntegerField(default=3000, verbose_name='持股数量')
    available_shares = models.IntegerField(default=3000, verbose_name='可用持股数量（T+1）')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '账户信息'
        verbose_name_plural = '账户信息'
        unique_together = ('stock_code',)  # 每个股票代码对应一个账户
    
    def __str__(self):
        return f'{self.stock_code} - 余额: {self.balance}元 - 持股: {self.shares}股 - 可用: {self.available_shares}股'

class TradeSetting(models.Model):
    """
    交易设置模型
    """
    STAGE_CHOICES = (
        ('oscillation', '震荡阶段'),
        ('downward', '下跌阶段'),
        ('upward', '上涨阶段'),
    )
    
    STRATEGY_CHOICES = (
        ('grid', '格子法做T'),
        ('percentage', '百分比做T'),
        ('multi_factor', '多因子做T'),
    )

    OSCILLATION_TYPE_CHOICES = (
        ('low', '低位震荡'),
        ('normal', '普通震荡'),
    )

    stock_code = models.CharField(max_length=10, unique=True, verbose_name='股票代码')
    market_stage = models.CharField(max_length=20, choices=STAGE_CHOICES, null=True, blank=True, verbose_name='行情阶段')
    oscillation_type = models.CharField(max_length=20, choices=OSCILLATION_TYPE_CHOICES, null=True, blank=True, verbose_name='震荡类型')
    strategy = models.CharField(max_length=20, choices=STRATEGY_CHOICES, default='multi_factor', verbose_name='交易策略')
    
    # 百分比策略字段
    sell_threshold = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0.5, verbose_name='高于均价卖出阈值(%)')
    buy_threshold = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, default=0.5, verbose_name='低于均价买入阈值(%)')
    
    # 均价线买入区间字段
    buy_avg_line_range_minus = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='均价线买入左区间(-)')
    buy_avg_line_range_plus = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='均价线买入右区间(+)')
    
    # 均价线卖出区间字段
    sell_avg_line_range_minus = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='均价线卖出左区间(-)')
    sell_avg_line_range_plus = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='均价线卖出右区间(+)')
    
    # 格子策略字段
    grid_buy_count = models.IntegerField(null=True, blank=True, verbose_name='低于均价格子数买入')
    grid_sell_count = models.IntegerField(null=True, blank=True, verbose_name='高于均价格子数卖出')

    buy_shares = models.IntegerField(null=True, blank=True, verbose_name='买入股数(股)')
    sell_shares = models.IntegerField(null=True, blank=True, verbose_name='卖出股数(股)')
    update_interval = models.IntegerField(default=5, verbose_name='更新频率(秒)')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    is_executing = models.BooleanField(default=False, verbose_name='是否正在执行交易')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')

    # 闭环交易相关字段
    PENDING_LOOP_CHOICES = (
        ('buy_first', '待卖出（买入领先）'),
        ('sell_first', '待买入（卖出领先）'),
    )
    pending_loop_type = models.CharField(max_length=20, choices=PENDING_LOOP_CHOICES, null=True, blank=True, verbose_name='待闭环类型')
    pending_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='待闭环价格')
    pending_volume = models.IntegerField(null=True, blank=True, verbose_name='待闭环数量')
    pending_timestamp = models.DateTimeField(null=True, blank=True, verbose_name='待闭环开始时间')
    
    overnight_sell_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, verbose_name='隔夜交易卖出比例(%)')
    overnight_buy_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=1.0, verbose_name='隔夜交易买入比例(%)')
    
    class Meta:
        verbose_name = '交易设置'
        verbose_name_plural = '交易设置'
    
    def __str__(self):
        return f'{self.stock_code} - 策略: {self.get_strategy_display()}'

class TradeLoop(models.Model):
    """
    闭环交易记录模型
    """
    LOOP_TYPE_CHOICES = (
        ('buy_sell', '买入->卖出'),
        ('sell_buy', '卖出->买入'),
    )
    
    stock_code = models.CharField(max_length=10, verbose_name='股票代码')
    loop_type = models.CharField(max_length=20, choices=LOOP_TYPE_CHOICES, verbose_name='闭环类型')
    
    # 第一笔交易
    open_record = models.ForeignKey(TradeRecord, on_delete=models.CASCADE, related_name='open_loops', verbose_name='开仓记录')
    # 第二笔交易
    close_record = models.ForeignKey(TradeRecord, on_delete=models.CASCADE, related_name='close_loops', null=True, blank=True, verbose_name='平仓记录')
    
    is_closed = models.BooleanField(default=False, verbose_name='是否已闭环')
    profit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name='闭环盈亏')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='闭环时间')

    class Meta:
        verbose_name = '闭环交易'
        verbose_name_plural = '闭环交易'
        ordering = ['-created_at']

    def __str__(self):
        status = "已闭环" if self.is_closed else "进行中"
        return f'{self.stock_code} - {self.get_loop_type_display()} - {status}'