import re
import requests

uuid = "cac32654-5e4e-43f0-8326-744aa128b0ce"
url = f"https://www.ingrasys.com/nq/{uuid}/"

proxies = {
    "http": "http://10.62.163.224:7740",
    "https": "http://10.62.163.224:7740"
}

r = requests.get(url, proxies=proxies, timeout=10)
print(f"HTTP 狀態碼: {r.status_code}")
print("HTML 片段前 500 字:\n", r.text[:500])

match = re.search(r'name="hf_day"[^>]*value="(\d+)"', r.text)
if match:
    print("找到 hf_day:", match.group(1))

