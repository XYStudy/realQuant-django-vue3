import requests
from bs4 import BeautifulSoup
import urllib.parse
import time

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def test_baidu(query):
    url = f"https://www.baidu.com/s?wd={urllib.parse.quote(query)}"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.find_all('div', class_='c-container')
        return f"Baidu: Found {len(items)} items"
    except Exception as e:
        return f"Baidu Error: {e}"

def test_360(query):
    url = f"https://www.so.com/s?q={urllib.parse.quote(query)}"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.find_all('li', class_='res-list')
        return f"360: Found {len(items)} items"
    except Exception as e:
        return f"360 Error: {e}"

query = "天华新能 核心竞争优势 行业地位"
print(test_baidu(query))
time.sleep(1)
print(test_360(query))
