from ddgs import DDGS
import sys

print("Testing DDGS")
try:
    res = DDGS().text("江南新材 核心竞争优势 行业地位 市占率", max_results=3)
    print(res)
except Exception as e:
    print("Error:", e)