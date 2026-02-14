import akshare as ak
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Test")

def get_stock_name(stock_code):
    clean_code = ''.join(filter(str.isdigit, stock_code))
    try:
        df = ak.stock_zh_a_spot_em()
        if not df.empty:
            target = df[df['代码'] == clean_code]
            if not target.empty:
                return target.iloc[0]['名称']
    except Exception as e:
        logger.error(f"Error: {e}")
    return stock_code

print(f"Name for 600152: {get_stock_name('600152')}")
