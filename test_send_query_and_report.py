from unittest.mock import MagicMock
import datetime
from main import send_query_and_report  # 改成你的模組名稱

def test_send_query_and_report_url(monkeypatch):
    # 假資料
    monkeypatch.setattr("main.TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setattr("main.user_work_ids", {835079: "835079"})
    monkeypatch.setattr("main.user_weekday_id_map", {835079: {datetime.datetime.now().weekday(): "1"}})
    monkeypatch.setattr("main.id_options", [["1","早餐"],["2","午餐"],["3","晚餐"]])
    monkeypatch.setattr("main.proxies", None)

    # 模擬 bot 和 requests.get
    mock_bot = MagicMock()
    mock_requester = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "OK"
    mock_requester.return_value = mock_response

    # 執行函式
    send_query_and_report(bot=mock_bot, requester=mock_requester)

    # 驗證 URL 是否被呼叫
    mock_requester.assert_called_once()
    called_url = mock_requester.call_args[0][0]
    assert called_url == "http://10.60.177.236/api/Order.ashx"
