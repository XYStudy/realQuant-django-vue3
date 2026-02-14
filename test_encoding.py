import requests
import akshare as ak

def get_stock_name(stock_code):
    """获取股票名称 (支持非交易日)"""
    clean_code = ''.join(filter(str.isdigit, stock_code))
    try:
        # 使用新浪接口获取名称，通常比较稳定且支持周末
        url = f"http://hq.sinajs.cn/list=sh{clean_code}" if clean_code.startswith('6') else f"http://hq.sinajs.cn/list=sz{clean_code}"
        headers = {"Referer": "http://finance.sina.com.cn"}
        resp = requests.get(url, headers=headers, timeout=5)
        resp.encoding = 'gbk'  # 新浪接口通常使用 GBK 编码
        if resp.status_code == 200 and '="' in resp.text:
            content = resp.text.split('="')[1]
            if content:
                name = content.split(',')[0]
                print(f"Code: {stock_code}, Name: {name}, Encoding: {resp.encoding}")
                return name
    except Exception as e:
        print(f"Error fetching stock name from Sina for {stock_code}: {e}")
    return stock_code

if __name__ == "__main__":
    get_stock_name("600710")
    get_stock_name("300169")
