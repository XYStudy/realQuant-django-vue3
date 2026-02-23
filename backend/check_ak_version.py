
import akshare as ak
print(f"AKShare version: {ak.__version__}")

# Try to find relevant functions
functions = [f for f in dir(ak) if 'index' in f and 'min' in f]
print("\nPossible index minute functions:")
for f in functions:
    print(f)

# Try index_zh_a_hist_min_em if found
if 'index_zh_a_hist_min_em' in functions:
    try:
        print("\nTesting index_zh_a_hist_min_em with 'sh000001'")
        df = ak.index_zh_a_hist_min_em(symbol="sh000001", period="5")
        print(df.tail())
    except Exception as e:
        print(f"Error sh000001: {e}")
        
    try:
        print("\nTesting index_zh_a_hist_min_em with '000001'")
        df = ak.index_zh_a_hist_min_em(symbol="000001", period="5") # usually 000001 implies SH Index in index context
        print(df.tail())
    except Exception as e:
        print(f"Error 000001: {e}")

# If not found, check stock_zh_a_minute (sina)
if 'stock_zh_a_minute' in dir(ak):
    try:
        print("\nTesting stock_zh_a_minute (sina) with 'sh000001'")
        df = ak.stock_zh_a_minute(symbol="sh000001", period="5")
        print(df.tail())
    except Exception as e:
        print(f"Error sina: {e}")
