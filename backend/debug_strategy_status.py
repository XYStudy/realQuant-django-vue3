import os
import django
import sys
from decimal import Decimal

# Setup Django environment
# Assuming this script is in f:\traeProject\backend\
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from quant.models import TradeSetting
from quant.services.multi_factor_strategy import MultiFactorStrategy
from quant.services.stock_service import StockDataService

stock_code = '603069'

def check_status():
    print(f"Checking status for {stock_code}...")
    
    # 1. Check TradeSetting
    try:
        setting = TradeSetting.objects.get(stock_code=stock_code)
        print(f"TradeSetting: strategy={setting.strategy}, is_active={setting.is_active}")
        print(f"Params: grid_buy={setting.grid_buy_count}, grid_sell={setting.grid_sell_count}")
    except TradeSetting.DoesNotExist:
        print("TradeSetting not found!")
        return

    # 2. Check MultiFactorStrategy
    if setting.strategy == 'multi_factor':
        print("Strategy is multi_factor. Testing execution...")
        # Mock stock data (minimal)
        stock_data = {
            'stock_code': stock_code,
            'current_price': 22.76,
            'high': 23.21,
            'low': 22.36,
            'open': 22.76,
            'average_price': 22.82,
            'volume': 86791,
            'amount': 198075901.0,
            'timestamp': '2026-02-19 12:36:01' # Ensure format matches what pandas expects or logic handles
        }
        
        try:
            strategy = MultiFactorStrategy.get_instance(stock_code)
            # Force initialization check
            print(f"Strategy Initialized: {strategy.is_initialized}")
            
            result = strategy.check_signal(stock_data, setting)
            print(f"Strategy Result: {result}")
        except Exception as e:
            print(f"Strategy Execution Failed: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"Strategy is NOT multi_factor. It is {setting.strategy}")

if __name__ == '__main__':
    check_status()
