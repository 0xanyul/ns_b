# import hashlib
# import os
# import time
# from dataclasses import dataclass
# from datetime import datetime, timedelta
# from typing import Iterable
# from xml.etree import ElementTree

# import requests
# import schedule


# TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
# CHAT_ID = os.environ.get("CHAT_ID")
# DART_API_KEY = os.environ.get("DART_API_KEY")
# ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY")

# RUN_AT = os.environ.get("NEWSBOT_RUN_AT", "08:00")
# INTERVAL_MINUTES = int(os.environ.get("NEWSBOT_INTERVAL_MINUTES", "15"))
# MIN_IMPORTANCE = int(os.environ.get("NEWSBOT_MIN_IMPORTANCE", "5"))
# MAX_ITEMS = int(os.environ.get("NEWSBOT_MAX_ITEMS", "10"))

# SEC_USER_AGENT = os.environ.get(
#     "SEC_USER_AGENT",
#     "market-news-bot/1.0 contact@example.com",
# )

# SESSION = requests.Session()
# SESSION.headers.update({"User-Agent": SEC_USER_AGENT})
# SEEN_ITEMS: set[str] = set()


# HIGH_IMPACT_KEYWORDS = {
#     "acquisition": 5,
#     "bankruptcy": 6,
#     "buyback": 4,
#     "cpi": 4,
#     "default": 5,
#     "earnings": 3,
#     "fda": 4,
#     "fomc": 5,
#     "guidance": 5,
#     "inflation": 4,
#     "lawsuit": 4,
#     "merger": 5,
#     "offering": 4,
#     "rate cut": 5,
#     "rate hike": 5,
#     "recall": 4,
#     "restructuring": 4,
#     "sec": 3,
#     "유상증자": 5,
#     "무상증자": 4,
#     "감자": 6,
#     "합병": 5,
#     "인수": 4,
#     "매각": 4,
#     "영업정지": 6,
#     "공급계약": 4,
#     "최대주주": 4,
#     "관리종목": 6,
#     "횡령": 6,
#     "배임": 6,
#     "실적": 3,
#     "금리": 4,
#     "물가": 4,
#     "환율": 3,
# }

# SEC_HIGH_IMPACT_FORMS = {
#     "8-K": 5,
#     "10-Q": 3,
#     "10-K": 3,
#     "S-1": 4,
#     "13D": 5,
#     "13G": 4,
#     "4": 4,
# }


# @dataclass(frozen=True)
# class NewsItem:
#     title: str
#     source: str
#     url: str = ""
#     published_at: str = ""
#     category: str = ""
#     base_score: int = 0


# def request_json(url: str, params: dict | None = None) -> dict:
#     response = SESSION.get(url, params=params, timeout=15)
#     response.raise_for_status()
#     return response.json()


# def request_xml(url: str, params: dict | None = None) -> ElementTree.Element:
#     response = SESSION.get(url, params=params, timeout=15)
#     response.raise_for_status()
#     return ElementTree.fromstring(response.content)


# def clean_text(text: str | None) -> str:
#     return " ".join((text or "").split())


# def item_id(item: NewsItem) -> str:
#     raw = item.url or f"{item.source}:{item.title}"
#     return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# def importance_score(item: NewsItem) -> int:
#     text = f"{item.title} {item.category}".lower()
#     score = item.base_score

#     for keyword, weight in HIGH_IMPACT_KEYWORDS.items():
#         if keyword.lower() in text:
#             score += weight

#     if item.source in {"OpenDART", "SEC EDGAR", "Federal Reserve", "BLS", "BEA"}:
#         score += 2

#     return score


# def dedupe(items: Iterable[NewsItem]) -> list[NewsItem]:
#     unique: dict[str, NewsItem] = {}
#     for item in items:
#         if not item.title:
#             continue
#         unique[item_id(item)] = item
#     return list(unique.values())


# def fetch_opendart() -> list[NewsItem]:
#     if not DART_API_KEY:
#         return []

#     today = datetime.now()
#     begin = (today - timedelta(days=3)).strftime("%Y%m%d")
#     end = today.strftime("%Y%m%d")
#     params = {
#         "crtfc_key": DART_API_KEY,
#         "bgn_de": begin,
#         "end_de": end,
#         "page_count": 100,
#         "sort": "date",
#         "sort_mth": "desc",
#     }
#     data = request_json("https://opendart.fss.or.kr/api/list.json", params=params)
#     if data.get("status") not in {"000", "013"}:
#         raise RuntimeError(f"OpenDART error: {data.get('message')}")

#     items = []
#     for row in data.get("list", [])[:50]:
#         receipt_no = row.get("rcept_no", "")
#         url = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else ""
#         title = f"{row.get('corp_name', '')} - {row.get('report_nm', '')}"
#         items.append(
#             NewsItem(
#                 title=clean_text(title),
#                 source="OpenDART",
#                 url=url,
#                 published_at=row.get("rcept_dt", ""),
#                 category=row.get("report_nm", ""),
#                 base_score=3,
#             )
#         )
#     return items


# def fetch_sec_edgar() -> list[NewsItem]:
#     root = request_xml(
#         "https://www.sec.gov/cgi-bin/browse-edgar",
#         params={"action": "getcurrent", "output": "atom", "count": "100"},
#     )
#     ns = {"atom": "http://www.w3.org/2005/Atom"}
#     items = []

#     for entry in root.findall("atom:entry", ns):
#         title = clean_text(entry.findtext("atom:title", default="", namespaces=ns))
#         link = entry.find("atom:link", ns)
#         href = link.attrib.get("href", "") if link is not None else ""
#         updated = clean_text(entry.findtext("atom:updated", default="", namespaces=ns))
#         form = ""
#         base_score = 1

#         for sec_form, weight in SEC_HIGH_IMPACT_FORMS.items():
#             if title == sec_form or title.startswith(f"{sec_form} - "):
#                 form = sec_form
#                 base_score = weight
#                 break

#         items.append(
#             NewsItem(
#                 title=title,
#                 source="SEC EDGAR",
#                 url=href,
#                 published_at=updated,
#                 category=form,
#                 base_score=base_score,
#             )
#         )
#     return items


# def fetch_rss_feed(source: str, url: str, base_score: int = 1) -> list[NewsItem]:
#     root = request_xml(url)
#     channel = root.find("channel")
#     nodes = channel.findall("item") if channel is not None else root.findall(".//item")
#     items = []

#     for node in nodes[:50]:
#         items.append(
#             NewsItem(
#                 title=clean_text(node.findtext("title")),
#                 source=source,
#                 url=clean_text(node.findtext("link")),
#                 published_at=clean_text(node.findtext("pubDate")),
#                 category=clean_text(node.findtext("category")),
#                 base_score=base_score,
#             )
#         )
#     return items


# def fetch_macro_rss() -> list[NewsItem]:
#     feeds = [
#         ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", 4),
#         ("PR Newswire", "https://www.prnewswire.com/rss/news-releases-list.rss", 2),
#     ]
#     items = []
#     for source, url, base_score in feeds:
#         items.extend(fetch_rss_feed(source, url, base_score))
#     return items


# def fetch_gdelt() -> list[NewsItem]:
#     query = '("Federal Reserve" OR FOMC OR CPI OR inflation OR "rate cut" OR "rate hike" OR merger OR acquisition OR bankruptcy)'
#     params = {
#         "query": query,
#         "mode": "ArtList",
#         "format": "json",
#         "maxrecords": 25,
#         "sort": "HybridRel",
#     }
#     data = request_json("https://api.gdeltproject.org/api/v2/doc/doc", params=params)
#     return [
#         NewsItem(
#             title=clean_text(article.get("title")),
#             source=f"GDELT/{article.get('sourceCountry', 'NEWS')}",
#             url=article.get("url", ""),
#             published_at=article.get("seendate", ""),
#             base_score=1,
#         )
#         for article in data.get("articles", [])
#     ]


# def fetch_alpha_vantage_news() -> list[NewsItem]:
#     if not ALPHAVANTAGE_API_KEY:
#         return []

#     params = {
#         "function": "NEWS_SENTIMENT",
#         "topics": "financial_markets,economy_monetary,earnings,mergers_and_acquisitions",
#         "sort": "LATEST",
#         "limit": 25,
#         "apikey": ALPHAVANTAGE_API_KEY,
#     }
#     data = request_json("https://www.alphavantage.co/query", params=params)
#     return [
#         NewsItem(
#             title=clean_text(article.get("title")),
#             source="Alpha Vantage",
#             url=article.get("url", ""),
#             published_at=article.get("time_published", ""),
#             category=",".join(topic.get("topic", "") for topic in article.get("topics", [])),
#             base_score=2,
#         )
#         for article in data.get("feed", [])
#     ]


# def fetch_all_news() -> list[NewsItem]:
#     sources = [
#         fetch_opendart,
#         fetch_sec_edgar,
#         fetch_macro_rss,
#         fetch_gdelt,
#         fetch_alpha_vantage_news,
#     ]
#     items = []

#     for source in sources:
#         try:
#             items.extend(source())
#         except Exception as exc:
#             print(f"{source.__name__} 실패: {exc}")

#     ranked = sorted(
#         dedupe(items),
#         key=lambda item: (importance_score(item), item.published_at),
#         reverse=True,
#     )
#     return ranked


# def format_message(items: list[NewsItem], only_new: bool = True) -> str:
#     selected = []
#     for item in items:
#         if importance_score(item) < MIN_IMPORTANCE:
#             continue
#         if only_new and item_id(item) in SEEN_ITEMS:
#             continue
#         selected.append(item)
#         if len(selected) >= MAX_ITEMS:
#             break

#     if not selected:
#         return ""

#     now = datetime.now().strftime("%Y-%m-%d %H:%M")
#     lines = [f"🚨 시장영향 뉴스 알림 ({now})"]
#     for index, item in enumerate(selected, 1):
#         score = importance_score(item)
#         line = f"{index}. [{score}점/{item.source}] {item.title}"
#         if item.url:
#             line += f"\n{item.url}"
#         lines.append(line)
#         SEEN_ITEMS.add(item_id(item))

#     return "\n\n".join(lines)


# def send_telegram(text: str) -> None:
#     if not TELEGRAM_TOKEN or not CHAT_ID:
#         print("TELEGRAM_TOKEN 또는 CHAT_ID가 설정되지 않았습니다.")
#         return

#     url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
#     response = requests.post(
#         url,
#         data={
#             "chat_id": CHAT_ID,
#             "text": text[:4000],
#             "disable_web_page_preview": True,
#         },
#         timeout=15,
#     )
#     response.raise_for_status()


# def job() -> None:
#     print("시장영향 뉴스 수집 중...")
#     items = fetch_all_news()
#     message = format_message(items)
#     if not message:
#         print("새로운 고영향 뉴스 없음")
#         return
#     send_telegram(message)
#     print("전송 완료!")


# def schedule_jobs() -> None:
#     schedule.every(INTERVAL_MINUTES).minutes.do(job)
#     schedule.every().day.at(RUN_AT).do(job)


# if __name__ == "__main__":
#     schedule_jobs()
#     job()

#     while True:
#         schedule.run_pending()
#         time.sleep(30)
