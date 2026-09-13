import os
import json
from difflib import SequenceMatcher


"""
dedupe.py — Deduplication module for the news digest pipeline.

What it does:
- Loads the most recent raw articles JSON file from news-digest/data/.
- Removes exact duplicate URLs.
- Identifies liveblogs (e.g., "live updates") and keeps only the latest snapshot per outlet.
- Uses difflib fuzzy matching (threshold: 0.70) to catch syndicated wire stories across outlets.
- Writes cleaned dataset to news-digest/data/deduped_latest.json.

Expected JSON output structure (data/deduped_latest.json):
{
  "metadata": {
    "source_raw_file": "articles_YYYY-MM-DDTHH-MM-SS.json",
    "original_count": 53,
    "clean_count": 52,
    "removed_count": 1
  },
  "articles": [...]
}
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_latest_raw_articles(data_dir=DATA_DIR):
    """Finds and loads the most recent raw articles JSON file."""
    if not os.path.exists(data_dir):
        return None, None
        
    raw_files = [
        os.path.join(data_dir, f) for f in os.listdir(data_dir) 
        if f.startswith("articles_") and f.endswith(".json")
    ]
    if not raw_files:
        return None, None
        
    latest_file = max(raw_files, key=os.path.getctime)
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    return data.get("articles", []), latest_file


def string_similarity(a, b):
    """Calculates a similarity ratio between two strings (0.0 to 1.0)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_liveblog(article):
    """Checks if an article is a liveblog based on title and URL patterns."""
    title = (article.get("title") or "").lower()
    url = (article.get("url") or "").lower()
    
    live_keywords = ["live updates", "liveblog", "war live", "live news", "live coverage"]
    return any(kw in title or kw in url for kw in live_keywords)


def deduplicate_articles(articles, title_similarity_threshold=0.70):

    if not articles:
        return []

    seen_urls = set()
    unique_articles = []
    liveblog_sources = set()

    for article in articles:
        url = article.get("url")
        title = article.get("title")
        source_id = article.get("source", {}).get("id") or article.get("source", {}).get("name")

        if not title or not url:
            continue


        if url in seen_urls:
            continue


        if is_liveblog(article):
            if source_id in liveblog_sources:

                continue
            liveblog_sources.add(source_id)
            seen_urls.add(url)
            unique_articles.append(article)
            continue


        is_duplicate_title = False
        for accepted in unique_articles:

            if is_liveblog(accepted):
                continue
                
            similarity = string_similarity(title, accepted.get("title", ""))
            if similarity >= title_similarity_threshold:
                is_duplicate_title = True
                break

        if not is_duplicate_title:
            seen_urls.add(url)
            unique_articles.append(article)

    return unique_articles


def run_deduplication():
    articles, source_file = load_latest_raw_articles()
    if not articles:
        print(f"No raw articles found in {DATA_DIR}")
        return None

    raw_filename = os.path.basename(source_file)
    print(f"Loaded {len(articles)} articles from {raw_filename}")

    clean_articles = deduplicate_articles(articles)
    removed_count = len(articles) - len(clean_articles)
    
    print(f"Deduplication complete: {removed_count} duplicates removed ({len(clean_articles)} retained).")


    output_path = os.path.join(DATA_DIR, "deduped_latest.json")
    payload = {
        "metadata": {
            "source_raw_file": raw_filename,
            "original_count": len(articles),
            "clean_count": len(clean_articles),
            "removed_count": removed_count
        },
        "articles": clean_articles
    }

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"Saved clean dataset to {output_path}")
        return clean_articles
    except IOError as e:
        print(f"Failed to save deduplicated data: {e}")
        return None


if __name__ == "__main__":
    run_deduplication()