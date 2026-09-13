import os
import json
import requests
from datetime import datetime, timedelta, timezone
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

    query_metadata = {
        "keywords": keywords,
        "sources": selected_sources[:20] if selected_sources else None,
        "hours_back": hours_back
    }

    try:
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()
        

        news_data = response.json()

        if news_data.get("status") == "ok":
            articles = news_data.get("articles", [])
            total_results = news_data.get("totalResults", 0)
            
            print(f"Fetched {len(articles)} of {total_results} total matching articles.")
            if total_results > len(articles):
                print(f"⚠️ Warning: Truncated by page size limit! Missed {total_results - len(articles)} older articles.")
                
            return articles, query_metadata
        else:
            print(f"Error fetching news: {news_data.get('message')}")
            return None, None

    except json.JSONDecodeError:
        print("Failed to decode response: API returned non-JSON data (e.g. 502 Bad Gateway HTML).")
    except requests.exceptions.Timeout:
        print("The request took too long and timed out!")
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as err:
        print(f"A general network error occurred: {err}")
    
    return None, None



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data")

def save_articles_to_json(articles, query_metadata=None, output_dir=DEFAULT_DATA_DIR):
    if articles is None:
        print("No article payload to export (articles is None).")
        return None


    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S")
    filepath = os.path.join(output_dir, f"articles_{timestamp}.json")
    
    payload = {
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "article_count": len(articles),
            "query_params": query_metadata or {}
        },
        "articles": articles
    }
    
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Successfully exported {len(articles)} articles to: {filepath}")
        return filepath
    except IOError as e:
        print(f"Failed to export articles to JSON: {e}")
        return None

if __name__ == "__main__":
    valid_sources = [
        "al-jazeera-english", 
        "bbc-news", 
        "cnn", 
        "reuters", 
        "associated-press"
    ]

    articles, meta = fetch_news(
        news_key=NEWS_API_KEY, 
        keywords=["gaza", "lebanon", "iran", "yemen", "syria", "iraq", "saudi arabia"],
        sources=valid_sources,
        hours_back=48
    )


    if articles is not None:
        save_articles_to_json(articles, query_metadata=meta)