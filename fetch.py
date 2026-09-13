import os
import json
import requests
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv


"""
fetch.py — Ingestion module for the news digest pipeline.

What it does:
- Queries NewsAPI's /v2/everything endpoint using server-side OR keyword queries.
- Filters articles strictly by dynamic UTC time windows (hours_back) and up to 20 valid sources.
- Handles network/API failure cases cleanly (timeouts, HTTP errors, and non-JSON HTML gateway errors).
- Warns if results exceed NewsAPI's 100-article single-page cap (totalResults > fetched count).
- Writes fetched articles + query metadata to a timestamped JSON file anchored in news-digest/data/.
- Exposes run_fetch() as a UI-facing wrapper for app.py that uses the pipeline
  defaults and returns (filepath, article_count).

Expected JSON output structure (data/articles_YYYY-MM-DDTHH-MM-SS.json):
{
  "metadata": {
    "fetched_at": "2026-09-13T04:15:00.123456+00:00",
    "article_count": 2,
    "query_params": {
      "keywords": [countries you are intrested in],
      "sources": ["al-jazeera-english", "bbc-news", "cnn", "reuters"],
      "hours_back": 48
    }
  },
  "articles": [
    {
      "source": {"id": "bbc-news", "name": "BBC News"},
      "author": "BBC Staff",
      "title": "Sample Article Title",
      "description": "Short article description...",
      "url": "https://www.bbc.co.uk/news/...",
      "publishedAt": "2026-09-13T01:15:00Z",
      "content": "Article snippet..."
    }
  ]
}
"""


load_dotenv(override=True)
NEWS_API_KEY = os.getenv("NEWS_API_KEY")


# --- Pipeline defaults (single source of truth for CLI + app.py) ---
DEFAULT_KEYWORDS = ["gaza", "lebanon", "iran", "yemen", "syria", "iraq", "saudi arabia"]
DEFAULT_SOURCES = [
    "al-jazeera-english", "bbc-news", "cnn", "reuters", "associated-press",
    "the-washington-post", "the-wall-street-journal", "bloomberg",
    "independent", "abc-news", "cbs-news", "msnbc", "newsweek",
]
DEFAULT_HOURS_BACK = 48


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(BASE_DIR, "data")


def fetch_news(news_key, keywords=None, sources=None, hours_back=24):
    base_url = "https://newsapi.org/v2/everything"

    params = {
        "apiKey": news_key,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 100,
    }

    if keywords:
        params["q"] = " OR ".join(f'"{kw}"' if " " in kw else kw for kw in keywords)

    time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours_back)
    params["from"] = time_threshold.strftime("%Y-%m-%dT%H:%M:%SZ")

    selected_sources = sources if sources is not None else DEFAULT_SOURCES
    if selected_sources:
        params["sources"] = ",".join(selected_sources[:20])

    query_metadata = {
        "keywords": keywords,
        "sources": selected_sources[:20] if selected_sources else None,
        "hours_back": hours_back,
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
            "query_params": query_metadata or {},
        },
        "articles": articles,
    }

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Successfully exported {len(articles)} articles to: {filepath}")
        return filepath
    except IOError as e:
        print(f"Failed to export articles to JSON: {e}")
        return None


def run_fetch(keywords=None, sources=None, hours_back=DEFAULT_HOURS_BACK):
    """
    UI-facing wrapper: fetch with pipeline defaults and persist to disk.
    Returns (raw_filepath, article_count).
    Raises RuntimeError on fetch or save failure so the Gradio button shows
    a clean error instead of a traceback.
    """
    articles, meta = fetch_news(
        news_key=NEWS_API_KEY,
        keywords=keywords if keywords is not None else DEFAULT_KEYWORDS,
        sources=sources if sources is not None else DEFAULT_SOURCES,
        hours_back=hours_back,
    )

    if articles is None:
        raise RuntimeError(
            "NewsAPI fetch failed (see stdout above for the specific cause: "
            "timeout, HTTP error, or non-JSON response)."
        )

    filepath = save_articles_to_json(articles, query_metadata=meta)
    if filepath is None:
        raise RuntimeError("Fetched articles but failed to write the raw JSON file.")

    return filepath, len(articles)


if __name__ == "__main__":
    articles, meta = fetch_news(
        news_key=NEWS_API_KEY,
        keywords=DEFAULT_KEYWORDS,
        sources=DEFAULT_SOURCES,
        hours_back=DEFAULT_HOURS_BACK,
    )

    if articles is not None:
        save_articles_to_json(articles, query_metadata=meta)