
import akshare as ak
import pandas as pd

def find_index_api():
    print("Searching for correct index minute API...")
    
    # Try stock_zh_index_daily_em just to confirm connection
    # df = ak.stock_zh_index_daily_em(symbol="sh000001")
    # print(f"Daily OK: {len(df)}")
    
    # Try different codes for stock_zh_a_hist_min_em
    codes = ["1.000001", "sh000001", "000001"]
    
    # There is also index_zh_a_hist_min_em in newer versions or similar?
    # No, usually stock_zh_a_hist_min_em covers indices if the code is right.
    # For EastMoney (em), index codes are usually like "1.000001" for SH Index.
    
    # Let's try to list functions in akshare that contain "index" and "min"
    import inspect
    
    # print("Functions with 'index' and 'min':")
    # for name, obj in inspect.getmembers(ak):
    #     if "index" in name and "min" in name:
    #         print(name)
            
    # Based on online docs/experience:
    # stock_zh_a_hist_min_em(symbol="000001") -> Ping An Bank
    # To get SH Index (000001), EastMoney often uses "1.000001" internally but the API might require just "sh000001" or "000001" with a flag?
    
    # Let's try ak.stock_zh_index_daily_em to get daily data, but we need 5-min.
    
    # Try "sh000001" with period="5" again? We saw it failed.
    # Try "1.000001" again? Failed.
    
    # What about stock_zh_a_minute ? (Sina source)
    try:
        print("\nTrying stock_zh_a_minute (Sina) for sh000001")
        df = ak.stock_zh_a_minute(symbol="sh000001", period="5", adjust="qfq")
        print(df.tail())
    except Exception as e:
        print(f"Error Sina: {e}")

    # What about index_zh_a_hist_min_em ?
    # Let's check if it exists in the installed version
    try:
        print("\nChecking for index_zh_a_hist_min_em")
        if hasattr(ak, 'index_zh_a_hist_min_em'):
             print("Found index_zh_a_hist_min_em!")
             df = ak.index_zh_a_hist_min_em(symbol="000001", period="5")
             print(df.tail())
        else:
             print("Not found.")
    except Exception as e:
        print(f"Error index_zh_a_hist_min_em: {e}")

if __name__ == "__main__":
    find_index_api()
