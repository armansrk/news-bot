import os
import re
import time
import requests
import feedparser
from bs4 import BeautifulSoup

# ================== تنظیمات ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SEEN_FILE = "seen.txt"

COINS = [
    "بیت کوین", "اتریوم", "دوج", "ریپل", "کاردانو", "سولانا",
    "شیبا", "پولکادات", "بیت کوین کش",
    "Bitcoin", "BTC", "Ethereum", "ETH", "XRP", "SOL", "DOGE", "ADA",
    "ETF", "SEC"
]

# RSS منابع (می‌تونی بعداً بیشترش کنی)
RSS_FEEDS = [
    "https://arzdigital.com/feed/",
]

HEADERS = {"User-Agent": "Mozilla/5.0 (NewsBot)"}


# ================== خواندن/نوشتن seen.txt ==================
def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen(seen: set):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for url in sorted(seen):
            f.write(url + "\n")


# ================== فیلتر کلیدواژه ==================
def matches_keywords(title: str) -> bool:
    t = (title or "").lower()
    return any(k.lower() in t for k in COINS)


# ================== خلاصه‌سازی ساده ==================
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


# ================== گرفتن خبر از RSS ==================
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


# ================== ارسال پیام به تلگرام (HTTP API) ==================
def send_telegram_message(html_text: str):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    r = requests.post(api_url, json=payload, timeout=20)
    r.raise_for_status()


# ================== اجرای ربات ==================
def job():
    if not BOT_TOKEN or not CHANNEL_ID:
        raise RuntimeError("BOT_TOKEN و CHANNEL_ID را در GitHub Secrets ست کن.")

    seen = load_seen()
    news = get_news_from_rss()

    sent = 0
    for item in news:
        url = item["link"]
        title = item["title"]

        # حذف تکراری‌ها
        if url in seen:
            continue

        summary = extract_summary_from_url(url)

        message = (
            f"🔹 <b>{title}</b>\n\n"
            f"{summary}\n\n"
            f"🔗 <a href='{url}'>ادامه خبر</a>"
        )

        send_telegram_message(message)
        seen.add(url)
        sent += 1
        time.sleep(1)  # ضد محدودیت تلگرام

    save_seen(seen)
    print(f"✅ {sent} خبر ارسال شد (بدون تکرار)")


# ✅ این بخش دقیقاً همونیه که باید باشه
if name == "main":
    job()
