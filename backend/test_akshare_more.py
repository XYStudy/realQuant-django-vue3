
import akshare as ak
import pandas as pd

def test_index_interfaces():
    print("Testing alternative AKShare index interfaces...")
    
    # 1. stock_zh_index_daily_em (only daily)
    try:
        print("\n1. stock_zh_index_daily_em (sh000001)")
        df = ak.stock_zh_index_daily_em(symbol="sh000001")
        print(f"Daily rows: {len(df)}")
        print(df.tail(2))
    except Exception as e:
        print(f"Error: {e}")

    # 2. index_zh_a_hist (general index history)
    try:
        print("\n2. index_zh_a_hist (000001)")
        df = ak.index_zh_a_hist(symbol="000001", period="daily")
        print(f"Rows: {len(df)}")
        print(df.tail(2))
    except Exception as e:
        print(f"Error: {e}")

    # 3. stock_zh_a_hist_min_em with special codes?
    # Some docs suggest index codes might be different for min data
    # 000001 is Ping An Bank
    # sh000001 is Shanghai Index (often used)
    # 1.000001 is EastMoney style for SH Index
    
    # Let's try to search for index code
    try:
        print("\n3. Searching for index codes")
        # index_stock_info_sina?
        # stock_zh_index_spot_em?
        df = ak.stock_zh_index_spot_em(symbol="上证系列指数")
        print(df[df['名称'].str.contains("上证指数")])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_index_interfaces()
