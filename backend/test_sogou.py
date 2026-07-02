import requests
from bs4 import BeautifulSoup
import urllib.parse

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def test_sogou(query):
    url = f"https://www.sogou.com/web?query={urllib.parse.quote(query)}"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = soup.find_all('div', class_='vrwrap')
        return f"Sogou: Found {len(items)} items"
    except Exception as e:
        return f"Sogou Error: {e}"

print(test_sogou("天华新能 核心竞争优势"))
