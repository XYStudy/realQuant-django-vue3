import requests
import json
import sys
import io
import time

# 设置输出编码为 UTF-8，防止 Windows 终端报错
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def get_kline_new(secid, n_days=60):
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "ut": "fa5fd1943c090f22558a2d1694d50935",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
        "klt": "101",
        "fqt": "1",
        "end": "20500101", # 结束日期设为未来
        "lmt": n_days,
        "_": str(int(time.time() * 1000))
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/"
    }
    resp = requests.get(url, params=params, headers=headers)
    return resp.json()

print("--- 启动数据获取 ---")
sid = "1.603069"
data = get_kline_new(sid, 60)
if data.get("data") and data["data"].get("klines"):
    print(f"✅ {sid} 成功获取 {len(data['data']['klines'])} 条 K 线数据：")
    for line in data["data"]["klines"]:
        print(line)
else:
    print(f"❌ {sid} 获取失败:", data)