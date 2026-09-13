import requests
from datetime import datetime, timedelta, timezone

import os
from dotenv import load_dotenv


load_dotenv(override=True)
NEWS_API_KEY = os.getenv("NEWS_API_KEY")


def fetch_news(news_key, keywords=None, sources=None, hours_back=24):
    base_url = "https://newsapi.org/v2/everything"
    

    params = {
        "apiKey": news_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100
    }

    if keywords:

        params["q"] = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in keywords)
    

    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    params["from"] = time_threshold.strftime("%Y-%m-%dT%H:%M:%SZ")
    

    default_sources = [
        "al-jazeera-english", "bbc-news", "cnn", "reuters", "associated-press",
        "the-washington-post", "the-wall-street-journal", "bloomberg",
        "independent", "abc-news", "cbs-news", "msnbc", "newsweek"
    ]
    
    selected_sources = sources if sources is not None else default_sources
    if selected_sources:
        params["sources"] = ",".join(selected_sources[:20])

    try:
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()
        news_data = response.json()

        if news_data.get("status") == "ok":
            articles = news_data.get("articles", [])
            print(f"Successfully fetched {len(articles)} articles.")
            return articles
        else:
            print(f"Error fetching news: {news_data.get('message')}")
            return None

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as err:
        print(f"A network error occurred: {err}")
    except requests.exceptions.Timeout:
        print("The request took too long and timed out!")
    
    return None

if __name__ == "__main__":
    
    
    valid_sources = [
        "al-jazeera-english", 
        "bbc-news", 
        "cnn", 
        "reuters", 
        "associated-press"
    ]

    articles = fetch_news(
        news_key=NEWS_API_KEY, 
        keywords=["gaza", "lebaon", "iran", "yemen", "syria", "iraq", "saudi arabia"],
        sources=valid_sources,
        hours_back=48
    )