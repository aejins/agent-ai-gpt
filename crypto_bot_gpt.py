import os
import json
import requests
import feedparser
from datetime import datetime
import openai

# --- Konfiguracja ---
TOKEN = os.getenv("BOT_TOKEN")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

CHAT_IDS_FILE = "chat_ids.txt"
RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://cryptonews.com/news/feed/",
    "https://bitcoinmagazine.com/.rss/full/",
]

MAX_MSG_LEN = 3900

# --- Chat ID ---
def get_chat_ids():
    try:
        with open(CHAT_IDS_FILE, "r") as f:
            return [line.strip() for line in f]
    except FileNotFoundError:
        return []

def save_chat_ids_from_telegram():
    url = f"{TELEGRAM_API}/getUpdates"
    resp = requests.get(url).json()
    chat_ids = set(get_chat_ids())
    for update in resp.get("result", []):
        if "message" in update:
            cid = str(update["message"]["chat"]["id"])
            chat_ids.add(cid)
    if chat_ids:
        with open(CHAT_IDS_FILE, "w") as f:
            for cid in chat_ids:
                f.write(cid + "\n")

# --- Wysyłka wiadomości ---
def send_message(text):
    chat_ids = get_chat_ids()
    if not chat_ids:
        save_chat_ids_from_telegram()
        chat_ids = get_chat_ids()
    if not chat_ids:
        print("❌ Brak chat_id, napisz coś do bota na Telegramie")
        return
    for chat_id in chat_ids:
        url = f"{TELEGRAM_API}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": text})

# --- Pobranie newsów ---
def fetch_news():
    items = []
    for feed in RSS_FEEDS:
        parsed = feedparser.parse(feed)
        for e in parsed.entries[:5]:
            items.append({
                "title": e.title,
                "link": e.link
            })
    return items

# --- GPT analiza ważności ---
def analyze_news_with_gpt(news_items):
    openai.api_key = OPENAI_KEY
    prompt = "Oceń następujące wiadomości krypto pod względem ważności HIGH, MEDIUM, LOW i podaj krótki podsumowujący opis. Format: LEVEL | title | short summary\n\n"
    for n in news_items:
        prompt += f"{n['title']}\n"
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2
    )
    text = response['choices'][0]['message']['content']
    # Zamiana odpowiedzi GPT na listę wiadomości
    analyzed = []
    for line in text.split("\n"):
        if "|" in line:
            level, title, summary = [x.strip() for x in line.split("|", 2)]
            analyzed.append({"level": level, "title": title, "summary": summary})
    return analyzed

# --- Budowanie raportu ---
def build_report():
    news = fetch_news()
    if not news:
        return "⚠️ Brak newsów dziś"
    analyzed_news = analyze_news_with_gpt(news)
    # Sortowanie: HIGH -> MEDIUM -> LOW
    analyzed_news.sort(key=lambda x: ["HIGH","MEDIUM","LOW"].index(x["level"]))
    msg = f"📅 {datetime.now().date()}\n🧠 *CRYPTO NEWS DIGEST GPT*\n\n"
    for n in analyzed_news:
        emoji = "🚨" if n["level"]=="HIGH" else "📌" if n["level"]=="MEDIUM" else "ℹ️"
        msg += f"{emoji} {n['level']}\n{n['title']}\n{n['summary']}\n{n['link']}\n\n"
    return msg[:MAX_MSG_LEN]

# --- Main ---
def main():
    save_chat_ids_from_telegram()
    report = build_report()
    send_message(report)

if __name__ == "__main__":
    main()
