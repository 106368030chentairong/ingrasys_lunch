import requests
import time
import datetime
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.ext import MessageHandler, filters
from telegram import ReplyKeyboardMarkup
from telegram import BotCommand
from telegram import Bot

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import re
import json
import os
import pytz

import asyncio
import aiohttp

DATA_FILE = "user_data.json"
user_work_ids = {}
user_weekday_id_map = {}
user_urls = {} # chat_id → URL 
user_day_index_map = {}  # chat_id → hf_day 

TELEGRAM_TOKEN = '7998365635:AAG1Z4692To8tH48io8WrpquscgdsQHD52E'
# TELEGRAM_TOKEN = '8082867993:AAGZj8nrZGFoqDInFGfZui4RdGMD7OakOBU'

tz = pytz.timezone("Asia/Taipei")

proxies = {
    "http": "http://10.62.163.224:7740",
    "https": "http://10.62.163.224:7740"
}

id_options = [
    ("0", "不定餐"),
    ("1", "葷食"),
    ("2", "拉亞1"),
    ("3", "拉亞2"),
    ("4", "素食"),
    ("5", "麵食"),
    ("6", "輕食"),
]
weekday_names = ["週一", "週二", "週三", "週四", "週五"]

REPLY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🍱 設定每日餐點", "✅ 統一設定"],
        ["📷 本週菜單", "🔍 查看設定"],
    ],
    resize_keyboard = True
)

# main menu keyboard
MAIN_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("🍱 設定各天餐點（逐日設定）", callback_data='set_weekday_id')],
    [InlineKeyboardButton("✅ 統一設定所有平日餐點", callback_data="unified_set_id")],
    [InlineKeyboardButton("📷 本週菜單圖片", callback_data="menu")],
    [InlineKeyboardButton("🔍 查看目前餐點設定", callback_data="show_all_setting")],
])

CANCEL_MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("⬅ 返回主選單", callback_data="back_main")],
    [InlineKeyboardButton("❌ 取消設定", callback_data="cancel_setting")],
])

# save user data
def load_user_data():
    global user_work_ids, user_weekday_id_map, user_urls, user_day_index_map
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            user_work_ids.update({int(k): v for k, v in data.get("user_work_ids", {}).items()})
            user_weekday_id_map.update({
                int(k): {int(kk): vv for kk, vv in v.items()}
                for k, v in data.get("user_weekday_id_map", {}).items()
            })
            user_urls.update({int(k): v for k, v in data.get("user_urls", {}).items()})
            user_day_index_map.update({int(k): v for k, v in data.get("user_day_index_map", {}).items()})

def save_user_data():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "user_work_ids": user_work_ids,
            "user_weekday_id_map": user_weekday_id_map,
            "user_urls": user_urls,
            "user_day_index_map": user_day_index_map,
        }, f, ensure_ascii=False, indent=2)


# send order query and report results
def send_query_and_report(bot=None, requester=None):
    bot = bot or Bot(token=TELEGRAM_TOKEN)
    requester = requester or requests.get

    for chat_id, work_id in user_work_ids.items():
        weekday_id_map = user_weekday_id_map.get(chat_id, {i: "4" for i in range(5)})
        today = datetime.datetime.now().weekday()
        if today not in weekday_id_map:
            continue
        params = {
            "act": 1,
            "order": "L",
            "id": weekday_id_map[today],
            "index": user_day_index_map[chat_id],
            "iok": work_id,
            "uid": work_id,
            "_": int(time.time() * 1000)
        }
        print(params)
        url = "https://www.ingrasys.com/nq/hrorder/ConnDB.ashx"
        response = requester(url, params=params, proxies=proxies)
        asyncio.run(bot.send_message(chat_id=chat_id, text=f"工號={work_id}：送出訂餐 '{id_options[int(weekday_id_map[today])][1]}'\n{response.text}"))


# get hf_day index value asynchronously
async def fetch_hf_day(session, chat_id, uuid, retry_delay=5, max_retries=3):
    url = f"https://www.ingrasys.com/nq/{uuid}/#slide1"
    for attempt in range(max_retries):
        try:
            async with session.get(url, timeout=60) as resp:
                text = await resp.text()
                match = re.search(r'name="hf_day"[^>]*value="(\d+)"', text)
                if match:
                    return chat_id, match.group(1)
        except Exception as e:
            print(f"[錯誤] {chat_id}: 第{attempt+1}次抓取失敗 {e}")
            await asyncio.sleep(retry_delay)
    return chat_id, None

async def fetch_index_value_async(user_urls, user_day_index_map):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_hf_day(session, chat_id, uuid) for chat_id, uuid in user_urls.items()]
        results = await asyncio.gather(*tasks)
        for chat_id, hf_day_value in results:
            if hf_day_value:
                user_day_index_map[chat_id] = hf_day_value
                print(f"[更新] {chat_id}: hf_day={hf_day_value}")
            else:
                print(f"[失敗] {chat_id}: 未抓到 hf_day")
                user_day_index_map[chat_id] = ""
    save_user_data()


# bot commands
async def set_bot_commands(app):
    commands = [
        BotCommand("start", "顯示主選單"),
        BotCommand("setid", "設定工號"),
        BotCommand("seturl", "設定URL"),
        BotCommand("menu", "顯示本週菜單"),
        BotCommand("status", "查看目前餐點設定"),
    ]
    await app.bot.set_my_commands(commands)


# show menu image
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.date.today()
    days_since_sunday = today.weekday() + 1  # 星期一=0，星期日=6 → +1 才回到上週日
    last_sunday = today - datetime.timedelta(days=days_since_sunday)
    date_str = last_sunday.strftime("%Y%m%d")
    url = f"https://www.ingrasys.com/nq/hr/Content/menu{date_str}.jpg"
    print(url)
    await update.message.reply_text(url)


# handle text messages
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[DEBUG] Received text: {update.message.text}")
    text = update.message.text

    if text == "🍱 設定每日餐點":
        keyboard = [[InlineKeyboardButton(day, callback_data=f"weekday_{i}")] for i, day in enumerate(weekday_names)]
        keyboard += [[InlineKeyboardButton("⬅ 返回主選單", callback_data="back_main")]]
        await update.message.reply_text("請選擇要設定的星期：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "✅ 統一設定":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"unifiedid_{id_}")] for id_, name in id_options]
        keyboard.append([InlineKeyboardButton("⬅ 返回主選單", callback_data="back_main")])
        await update.message.reply_text("請選擇要套用到整週的餐點種類：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == "本週菜單":
        today = datetime.date.today()
        days_since_sunday = today.weekday() + 1  # 星期一=0，星期日=6 → +1 才回到上週日
        last_sunday = today - datetime.timedelta(days=days_since_sunday)
        date_str = last_sunday.strftime("%Y%m%d")
        url = f"https://www.ingrasys.com/nq/hr/Content/menu{date_str}.jpg"
        print(url)
        await update.message.reply_text(url)

    elif text == "🔍 查看設定":
        chat_id = update.effective_chat.id
        weekday_id_map = user_weekday_id_map.get(chat_id, {i: "4" for i in range(5)})
        msg = "目前平日餐點設定如下：\n"
        for i in range(5):
            id_ = weekday_id_map.get(i, "未設定")
            name = next((n for idv, n in id_options if idv == id_), "未設定")
            msg += f"{weekday_names[i]}：{id_}（{name}）\n"
        await update.message.reply_text(msg, reply_markup=MAIN_MENU)
    
    """ elif text == "立即訂餐":
        params = {
            "act": 1,
            "order": "L",
            "id": weekday_id_map[today],
            "index": user_day_index_map[chat_id],
            "iok": work_id,
            "uid": work_id,
            "_": int(time.time() * 1000)
        }
        print(params)
        url = "https://www.ingrasys.com/nq/hrorder/ConnDB.ashx"
        response = requester(url, params=params, proxies=proxies) """


# start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_work_ids:
        await update.message.reply_text("新用戶你好！請設定你的工號，例如：/setid 812345")
    else:
        work_id = user_work_ids[chat_id]
        await update.message.reply_text(
            f"目前以此工號設定：{work_id}\n請選擇操作：",
            reply_markup=REPLY_KEYBOARD  # ← 顯示輸入匡上方選單
        )
        await update.message.reply_text("功能選單：", reply_markup=MAIN_MENU)

# setid command
async def setid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not context.args:
        await update.effective_chat.send_message("請輸入格式：/setid <你的工號>")
        return
    work_id = context.args[0]
    user_work_ids[chat_id] = work_id
    if chat_id not in user_weekday_id_map:
        user_weekday_id_map[chat_id] = {i: "6" for i in range(5)}
    save_user_data()
    await update.effective_chat.send_message(
        f"你的工號已設定為：{work_id}\n餐點初始設定每天為 “輕食”\n請使用 /start 開始設定每週平日餐點。"
    )

# seturl command
async def seturl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id not in user_work_ids:
        await update.message.reply_text("新用戶你好！請設定你的工號，例如：/setid 812345")
    else:
        if not context.args:
            await update.effective_chat.send_message("請輸入格式：/seturl <完整URL>")
            return

        url = context.args[0]
        match = re.search(r'/nq/([0-9a-fA-F-]{36})', url)
        if not match:
            await update.effective_chat.send_message("URL 格式錯誤，未找到UUID。")
            return

        uuid = match.group(1)
        user_urls[chat_id] = uuid
        save_user_data()
        await update.effective_chat.send_message(f"你的訂餐UUID已設定為：{uuid}")


# define menu button callback handler
async def menu_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data == 'back_main':
        await query.message.reply_text("返回主選單：", reply_markup=MAIN_MENU)
        return

    if data == 'set_weekday_id':
        keyboard = [[InlineKeyboardButton(day, callback_data=f"weekday_{i}")] for i, day in enumerate(weekday_names)]
        keyboard += [[InlineKeyboardButton("⬅ 返回主選單", callback_data="back_main")]]
        await query.message.reply_text("請選擇要設定的星期：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "show_all_setting":
        weekday_id_map = user_weekday_id_map.get(chat_id, {i: "4" for i in range(5)})
        msg = "目前平日餐點設定如下：\n"
        for i in range(5):
            id_ = weekday_id_map.get(i, "未設定")
            name = next((n for idv, n in id_options if idv == id_), "未設定")
            msg += f"{weekday_names[i]}：{id_}（{name}）\n"
        await query.message.reply_text(msg, reply_markup=MAIN_MENU)

    elif data.startswith('weekday_'):
        weekday = int(data.split('_')[1])
        context.user_data['set_weekday'] = weekday
        keyboard = [[InlineKeyboardButton(name, callback_data=f"setid_{weekday}_{id_}")] for id_, name in id_options]
        keyboard += [[InlineKeyboardButton("⬅ 返回主選單", callback_data="back_main")]]
        await query.message.reply_text(f"請為{weekday_names[weekday]}選擇餐點：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('setid_'):
        _, weekday, id_selected = data.split('_')
        weekday = int(weekday)
        user_weekday_id_map[chat_id][weekday] = id_selected
        name_selected = next(name for id_, name in id_options if id_ == id_selected)
        save_user_data()
        await query.message.reply_text(f"{weekday_names[weekday]} 已設定為：{id_selected}（{name_selected}）",
                                       reply_markup=MAIN_MENU)

    elif data == "unified_set_id":
        keyboard = [[InlineKeyboardButton(name, callback_data=f"unifiedid_{id_}")] for id_, name in id_options] # "id_options" set lunch for whole week
        keyboard.append([InlineKeyboardButton("⬅ 返回主選單", callback_data="back_main")])
        await query.message.reply_text("請選擇要套用到整週（週一至五）的餐點種類：", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith('unifiedid_'):
        id_selected = data.split('_')[1]
        for i in range(5):
            user_weekday_id_map[chat_id][i] = id_selected
        name_selected = next(name for id_, name in id_options if id_ == id_selected) # "id_options" set lunch for whole week
        save_user_data()
        await query.message.reply_text(f"已將週一至週五的餐點全部設定為：{id_selected}（{name_selected}）",
                                       reply_markup=MAIN_MENU)

    elif data == "cancel_setting":
        await query.message.reply_text("已取消設定。", reply_markup=MAIN_MENU)

    elif data in "menu":
        today = datetime.date.today()
        days_since_sunday = today.weekday() + 1  # 星期一=0，星期日=6 → +1 才回到上週日
        last_sunday = today - datetime.timedelta(days=days_since_sunday)
        date_str = last_sunday.strftime("%Y%m%d")
        url = f"https://www.ingrasys.com/nq/hr/Content/menu{date_str}.jpg"
        print(url)
        await query.message.reply_text(url, reply_markup=MAIN_MENU)


# wrapper for async send_query_and_report
async def send_query_and_report_wrapper():
    await send_query_and_report()


def main():
    load_user_data()
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .read_timeout(360)
        .connect_timeout(360)
        #.proxy_url("http://10.62.163.224:7740")
        .build()
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('setid', setid))
    app.add_handler(CommandHandler('seturl', seturl))
    app.add_handler(CommandHandler('menu', menu))
    app.add_handler(CallbackQueryHandler(menu_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("TELEGRAM DEBUG 1")

    scheduler = AsyncIOScheduler(timezone=tz)
    scheduler.add_job(fetch_index_value_async, 'cron', hour=6, minute=0, day_of_week='mon-fri')
    scheduler.add_job(send_query_and_report_wrapper, 'cron', hour=6, minute=30, day_of_week='mon-fri')
    scheduler.start()
    print("TELEGRAM DEBUG 2")

    app.post_init = set_bot_commands
    print("Bot is polling...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

# 及時訂餐
# SETIU 優化流程
# 所有設定工號優先設定
# 定時往前
# 菜單新增素食