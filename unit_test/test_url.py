import requests
import time

proxies = {
    "http": "http://10.62.163.224:7740",
    "https": "http://10.62.163.224:7740"
}

url = "https://www.ingrasys.com/nq/hrorder/ConnDB.ashx"

params = {
    "act": 1,
    "order": "L",
    "id": 4,
    "index": 1854717,
    "iok": "835079",
    "uid": 835079,
    "_": int(time.time() * 1000)  # 目前時間戳(毫秒)
}


print(params)
response = requests.get(url, params=params, proxies=proxies)
print(response.text)