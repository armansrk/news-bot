import os
import time
import requests
import feedparser
from googletrans import Translator
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# تنظیمات
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
SEEN_FILE = "seen.txt"

RSS_FEEDS = [
    "https://arzdigital.com/feed/",
    "https://www.coindesk.com/feed/",
    "https://cointelegraph.com/rss",
    "https://cryptoslate.com/feed/",
    "https://decrypt.co/feed",
]

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

                if title and link:
                    items.append({"title": title, "link": link})

        except Exception:
            continue
    return items

# ارسال پیام به تلگرام (شامل تصویر)
def send_telegram_message_with_image(text: str, img_url: str):
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": CHANNEL_ID,
        "caption": text,
        "parse_mode": "HTML"
    }
    files = {"photo": requests.get(img_url).content} if img_url else {}
    r = requests.post(api_url, data=payload, files=files, timeout=20)
    if r.status_code == 200:
        print(f"✅ پیام ارسال شد: {text}")
    else:
        print(f"❌ خطا در ارسال پیام: {r.status_code} - {r.text}")

# اجرای ربات
def job():
    if not BOT_TOKEN or not CHANNEL_ID:
        raise RuntimeError("BOT_TOKEN و CHANNEL_ID را در GitHub Secrets ست کن.")

    seen = load_seen()
    news = get_news_from_rss()

    sent = 0
    for item in news:
        url = item["link"]
        title = item["title"]

        if url in seen:
            continue

        summary = extract_summary_from_url(url)
        translated_summary = translate_to_persian(summary)

        # استخراج تصویر از خبر
        img_url = extract_image_from_url(url)

        # ارسال پیام به تلگرام همراه با تصویر
        message = (
            f"🔹 <b>{title}</b>\n\n"
            f"{translated_summary}\n\n"
            f"🔗 <a href='{url}'>ادامه خبر</a>"
        )

        send_telegram_message_with_image(message, img_url)
        seen.add(url)
        sent += 1
        time.sleep(1)

    save_seen(seen)
    print(f"✅ {sent} خبر ارسال شد (بدون تکرار)")

# اجرا
if __name__ == "__main__":
    job()
