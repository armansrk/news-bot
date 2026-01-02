import os
import time
import requests
import feedparser
from googletrans import Translator
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import json
from datetime import datetime, timedelta

# تنظیمات
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SEEN_FILE = "seen.txt"
prices_file = "prices.json"

# ارزهای دیجیتال برای نظارت
COINS = ['bitcoin', 'ethereum', 'binancecoin', 'cardano', 'solana', 'ripple', 'polkadot', 'dogecoin', 'litecoin', 'uniswap']

# RSS Feeds برای اخبار ارز دیجیتال
RSS_FEEDS = [
    "https://arzdigital.com/feed/",
    "https://www.coindesk.com/feed/",
    "https://cointelegraph.com/rss",
    "https://cryptoslate.com/feed/",
    "https://decrypt.co/feed",
]

# URL API کوین گکو برای دریافت قیمت
API_URL = "https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies=usd"

HEADERS = {"User-Agent": "Mozilla/5.0 (NewsBot)"}

# ترجمه به فارسی
def translate_to_persian(text: str) -> str:
    translator = Translator()
    translated = translator.translate(text, src='en', dest='fa')
    return translated.text

# خواندن/نوشتن seen.txt
def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(seen: set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            f.write(url + "\n")

# فیلتر کلیدواژه
def matches_keywords(title: str) -> bool:
    t = (title or "").lower()
    return any(k.lower() in t for k in COINS)

# استخراج خلاصه از URL
def extract_summary_from_url(url: str, max_chars: int = 420) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
        text = " ".join([p for p in paragraphs if p and len(p) > 30])
        text = re.sub(r"\s+", " ", text).strip()

        if not text:
            return "خلاصه در دسترس نیست."

        summary = text[:max_chars]
        if len(text) > max_chars:
            summary += "…"
        return summary

    except Exception:
        return "خلاصه در دسترس نیست."

# استخراج تصویر از صفحه
def extract_image_from_url(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")
        img_tag = soup.find("img")  # پیدا کردن اولین تگ img
        if img_tag:
            img_url = img_tag.get("src")
            img_url = urljoin(url, img_url)  # در صورت نیاز، آدرس کامل تصویر را می‌سازیم
            return img_url
        return ""
    except Exception:
        return ""

# گرفتن اخبار از RSS
def get_news_from_rss():
    items = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                title = getattr(entry, "title", "").strip()
                link = getattr(entry, "link", "").strip()

                if title and link and matches_keywords(title):
                    items.append({"title": title, "link": link})

        except Exception:
            continue
    return items

# ارسال پیام به تلگرام (شامل تصویر)
def send_telegram_message_with_image(text: str, img_url: str):
    # ارسال پیام متنی
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        # ابتدا پیام متنی را ارسال می‌کنیم
        response_text = requests.post(api_url, data=payload)
        if response_text.status_code == 200:
            print("پیام متنی با موفقیت ارسال شد.")
        else:
            print(f"خطا در ارسال پیام متنی: {response_text.status_code}")

        # سپس اگر تصویر وجود دارد، تصویر را ارسال می‌کنیم
        if img_url:
            print(f"در حال ارسال تصویر از URL: {img_url}")
            img_response = requests.get(img_url)
            if img_response.status_code == 200:  # اگر تصویر با موفقیت دانلود شد
                files = {"photo": img_response.content}
                # ارسال تصویر به تلگرام
                response_img = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto", data=payload, files=files)
                if response_img.status_code == 200:
                    print("تصویر با موفقیت ارسال شد.")
                else:
                    print(f"خطا در ارسال تصویر: {response_img.status_code}")
            else:
                print(f"خطا در دانلود تصویر: {img_url}")
    except requests.exceptions.RequestException as e:
        print(f"خطا در ارسال پیام به تلگرام: {e}")

# دریافت قیمت فعلی ارزها از API
def get_current_prices():
    ids = ",".join(COINS)
    response = requests.get(API_URL.format(ids))
    return response.json()

# بارگذاری قیمت‌ها از فایل
def load_prices():
    if os.path.exists(prices_file):
        try:
            with open(prices_file, 'r') as file:
                return json.load(file)
        except json.JSONDecodeError:
            print(f"خطا در بارگذاری فایل {prices_file}. داده نامعتبر است.")
            return {}  # بازگشت داده خالی در صورت خطا
    return {}

# ذخیره قیمت‌ها به فایل
def save_prices(prices):
    with open(prices_file, 'w') as file:
        json.dump(prices, file)

# محاسبه تغییرات قیمت
def calculate_price_change(old_price, new_price):
    return ((new_price - old_price) / old_price) * 100

# بررسی تغییرات قیمت ارزها
def check_price_changes():
    current_prices = get_current_prices()
    saved_prices = load_prices()
    
    for coin in COINS:
        if coin not in current_prices:
            continue
        current_price = current_prices[coin]['usd']
        
        if coin not in saved_prices:
            saved_prices[coin] = {
                'last_price': current_price,
                'last_check_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            continue
        
        last_price = saved_prices[coin]['last_price']
        last_check_time = datetime.strptime(saved_prices[coin]['last_check_time'], "%Y-%m-%d %H:%M:%S")
        
        # محاسبه تغییر قیمت در 4 ساعت گذشته
        time_diff = datetime.now() - last_check_time
        price_change_percentage = calculate_price_change(last_price, current_price)

        # اگر تغییر قیمت بیش از 5 درصد در 4 ساعت باشد
        if time_diff < timedelta(hours=4) and abs(price_change_percentage) >= 5:
            send_telegram_message_with_image(f"🔹 تغییر قیمت {coin} بیشتر از 5 درصد در 4 ساعت اخیر!\n\n"
                                  f"قیمت قبلی: ${last_price}\n"
                                  f"قیمت جدید: ${current_price}\n"
                                  f"تغییر: {price_change_percentage:.2f}%", "")

        # اگر تغییر قیمت بیشتر از 10 درصد در یک روز باشد
        if time_diff >= timedelta(days=1) and abs(price_change_percentage) >= 10:
            send_telegram_message_with_image(f"🔹 تغییر قیمت {coin} بیشتر از 10 درصد در 24 ساعت اخیر!\n\n"
                                  f"قیمت قبلی: ${last_price}\n"
                                  f"قیمت جدید: ${current_price}\n"
                                  f"تغییر: {price_change_percentage:.2f}%", "")

        # بروزرسانی اطلاعات قیمت و زمان
        saved_prices[coin]['last_price'] = current_price
        saved_prices[coin]['last_check_time'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    save_prices(saved_prices)

def job():
    if not BOT_TOKEN or not CHANNEL_ID:
        print("خطا: توکن ربات یا شناسه کانال مشخص نشده است.")
        return  # اجرای کد متوقف می‌شود اگر توکن یا شناسه کانال وجود نداشته باشد

    # گرفتن اخبار از RSS
    news = get_news_from_rss()
    for item in news:
        title = item['title']
        link = item['link']
        summary = extract_summary_from_url(link)
        img_url = extract_image_from_url(link)
        send_telegram_message_with_image(f"<b>{title}</b>\n{summary}\n\n<a href='{link}'>بیشتر بخوانید</a>", img_url)

    # بررسی تغییرات قیمت ارزها
    check_price_changes()

if __name__ == "__main__":
    job()
