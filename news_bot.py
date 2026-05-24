import requests
from bs4 import BeautifulSoup
import anthropic
import schedule
import time
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")


def get_news():
    url = "https://news.naver.com/section/101"
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    
    titles = soup.select(".sa_text_title")[:5]
    return [t.get_text(strip=True) for t in titles]

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": CHAT_ID, "text": text})

def job():
    print("뉴스 가져오는 중...")
    news = get_news()
    message = "📰 오늘의 경제뉴스\n\n"
    message += "\n\n".join(f"{i+1}. {n}" for i, n in enumerate(news))
    send_telegram(message)
    print("전송 완료!")

schedule.every().day.at("08:00").do(job)

job()  # 지금 바로 테스트

while True:
    schedule.run_pending()
    time.sleep(60)