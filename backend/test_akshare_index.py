
import akshare as ak
import pandas as pd

def test_index_fetch():
    print("Testing AKShare index data fetching...")
    
    # Try different symbols for Shanghai Composite Index
    symbols = ['000001', 'sh000001', '1.000001']
    
    for symbol in symbols:
        print(f"\nTesting symbol: {symbol}")
        try:
            # Using stock_zh_a_hist_min_em which is what the current code uses
            df = ak.stock_zh_a_hist_min_em(symbol=symbol, period="5")
            if not df.empty:
                print(f"Success! Retrieved {len(df)} rows.")
                print("First 2 rows:")
                print(df.head(2))
                print("Last 2 rows:")
                print(df.tail(2))
                
                # Check if values look like index (approx 3000+) or stock (approx 10-100)
                last_close = df.iloc[-1]['收盘']
                print(f"Last close price: {last_close}")
                if last_close > 2000:
                    print("=> Looks like Index data")
                else:
                    print("=> Looks like Stock data (e.g. Ping An Bank)")
            else:
                print("Empty dataframe returned")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_index_fetch()
