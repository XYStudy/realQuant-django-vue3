import requests


def fetch_latest_financial_row(code: str):
    url = "https://datacenter-web.eastmoney.com/api/data/v1/get"
    params = {
        "reportName": "RPT_LICO_FN_CPD",
        "columns": "ALL",
        "sortColumns": "REPORTDATE",
        "sortTypes": "-1",
        "pageSize": "1",
        "pageNumber": "1",
        "filter": f'(SECURITY_CODE="{code}")',
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    data = (payload.get("result") or {}).get("data") or []
    return data[0] if data else None


if __name__ == "__main__":
    for c in ["300486", "300487"]:
        row = fetch_latest_financial_row(c) or {}
        print(
            c,
            "REPORTDATE",
            row.get("REPORTDATE"),
            "ROE",
            row.get("WEIGHTAVG_ROE"),
            "REV_YOY",
            row.get("YSTZ"),
            "NP_YOY",
            row.get("SJLTZ"),
        )
