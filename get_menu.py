import datetime

today = datetime.date.today()
# weekday(): 0=週一, ..., 6=週日
days_until_sunday = 7 - today.weekday()
print(days_until_sunday)
sunday = today - datetime.timedelta(days=days_until_sunday)
date_str = sunday.strftime("%Y%m%d")

url = f"http://ingrasys.com/nq/hr/Content/menu{date_str}.jpg"
print(url)