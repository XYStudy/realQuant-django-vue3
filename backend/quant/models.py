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
    账户模型，用于管理账户资金和持股情况
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
    stock_code = models.CharField(max_length=10, verbose_name='股票代码')
    sell_threshold = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='高于均价卖出阈值(%)')
    buy_threshold = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='低于均价买入阈值(%)')
    buy_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='买入金额(元)')
    sell_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='卖出金额(元)')
    buy_shares = models.IntegerField(null=True, blank=True, verbose_name='买入股数(股)')
    sell_shares = models.IntegerField(null=True, blank=True, verbose_name='卖出股数(股)')
    update_interval = models.IntegerField(default=5, verbose_name='更新频率(秒)')
    is_active = models.BooleanField(default=True, verbose_name='是否激活')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='创建时间')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='更新时间')
    
    class Meta:
        verbose_name = '交易设置'
        verbose_name_plural = '交易设置'
    
    def __str__(self):
        if self.buy_amount:
            buy_info = f'买入金额: {self.buy_amount}元'
        elif self.buy_shares:
            buy_info = f'买入股数: {self.buy_shares}股'
        else:
            buy_info = '未设置买入'
        
        if self.sell_amount:
            sell_info = f'卖出金额: {self.sell_amount}元'
        elif self.sell_shares:
            sell_info = f'卖出股数: {self.sell_shares}股'
        else:
            sell_info = '未设置卖出'
        
        return f'{self.stock_code} - 卖出阈值: {self.sell_threshold}% - 买入阈值: {self.buy_threshold}% - {buy_info} - {sell_info}'