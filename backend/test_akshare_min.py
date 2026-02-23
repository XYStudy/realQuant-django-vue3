
import akshare as ak
import pandas as pd

def test_index_min():
    print("Testing index minute data fetching...")
    
    # 000001 is Ping An Bank
    # We need to find the correct symbol for Shanghai Index minute data in stock_zh_a_hist_min_em
    # Sometimes it's 'sh000001' but that failed
    
    # Let's try to see if stock_zh_a_hist_min_em accepts '1.000001' (EastMoney style) or just '000001' with adjust=''
    
    # Wait, akshare documentation for index minute data might use a different function?
    # No, stock_zh_a_hist_min_em is generally for stocks.
    # There is index_zh_a_hist_min_em ? Let's check.
    
    try:
        print("\nTrying index_zh_a_hist_min_em (sh000001)")
        # This function might not exist or have different name
        if hasattr(ak, 'index_zh_a_hist_min_em'):
            df = ak.index_zh_a_hist_min_em(symbol="sh000001", period="5")
            print(df.tail())
        else:
            print("ak.index_zh_a_hist_min_em does not exist")
    except Exception as e:
        print(f"Error: {e}")
        
    try:
        print("\nTrying stock_zh_a_hist_min_em with symbol='sh000001'")
        df = ak.stock_zh_a_hist_min_em(symbol="sh000001", period="5")
        print(df.tail())
    except Exception as e:
        print(f"Error: {e}")

    try:
        print("\nTrying stock_zh_a_hist_min_em with symbol='000001' (no adjust)")
        # This returns Ping An Bank usually
        df = ak.stock_zh_a_hist_min_em(symbol="000001", period="5")
        print(f"Last close: {df.iloc[-1]['收盘']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_index_min()
