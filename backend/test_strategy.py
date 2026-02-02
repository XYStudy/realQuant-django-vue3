
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from quant.services.stock_service import StockDataService
from quant.models import TradeSetting

s = TradeSetting.objects.get(stock_code='603069')
data = StockDataService.get_stock_data('603069')
should, trade_type, reason = StockDataService.check_trade_condition(data, s)
print(f'should={should}')
print(f'type={trade_type}')
print(f'reason={reason}')
print(f'grid_step={data.get("grid_step")}')
print(f'grid_diff={data.get("grid_diff")}')
