import urllib.request
import urllib.parse
import json
import re
import time
import ssl
import traceback

def search_bing(query):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        q = urllib.parse.quote(query)
        url = f"https://www.bing.com/search?q={q}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            html = response.read().decode('utf-8')
            # Extract text from <p> tags or <div class="b_caption">
            snippets = re.findall(r'<p[^>]*>(.*?)</p>', html)
            text = " ".join(snippets)
            text = re.sub(r'<[^>]+>', '', text)
            if len(text) > 10: return text
    except Exception as e:
        print("Bing error:", e)
    return ""

def search_sogou(query):
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        q = urllib.parse.quote(query)
        url = f"https://www.sogou.com/web?query={q}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, context=ctx, timeout=5) as response:
            html = response.read().decode('utf-8')
            snippets = re.findall(r'<div class="vrwrap"[^>]*>(.*?)</div>', html, re.DOTALL)
            text = " ".join(snippets)
            text = re.sub(r'<[^>]+>', '', text)
            if len(text) > 10: return text
    except Exception as e:
        pass
    return ""

print("Bing:", len(search_bing("江南新材 核心竞争优势")))
print("Sogou:", len(search_sogou("江南新材 核心竞争优势")))
