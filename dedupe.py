"""
dedupe.py — Deduplication module for the news digest pipeline.

What it does:
- Loads the most recent raw articles JSON file from news-digest/data/.
- Sorts articles newest-first by publishedAt timestamp to ensure deterministic ordering.
- Removes exact duplicate URLs.
- Identifies liveblogs and collapses duplicate coverage per topic per outlet.
- Uses difflib fuzzy matching (threshold: 0.70) to catch syndicated wire stories.
- Writes cleaned dataset to news-digest/data/deduped_latest.json.

Two entry points:
- run_dedupe(raw_file)      -> explicit-threaded, used by app.py. Takes the exact
                               raw file produced by fetch.run_fetch() so there is no
                               ambiguity about which snapshot is being deduped.
- run_deduplication()       -> CLI auto-discovery. Picks the newest articles_*.json
                               on disk. Used by the `python dedupe.py` workflow.
"""

import os
import json
import re
from difflib import SequenceMatcher

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def load_latest_raw_articles(data_dir=DATA_DIR):
    """
    Finds and loads the most recent raw articles JSON file using
    deterministic string sorting on timestamped filenames.
    """
    if not os.path.exists(data_dir):
        return None, None

    raw_files = [
        os.path.join(data_dir, f) for f in os.listdir(data_dir)
        if f.startswith("articles_") and f.endswith(".json")
    ]
    if not raw_files:
        return None, None

    latest_file = max(raw_files, key=os.path.basename)

    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("articles", []), latest_file
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading {latest_file}: {e}")
        return None, None


def string_similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_liveblog(article):
    """Checks if an article is a liveblog based on title and URL patterns."""
    title = (article.get("title") or "").lower()
    url = (article.get("url") or "").lower()

    live_keywords = ["live updates", "liveblog", "war live", "live news", "live coverage"]
    return any(kw in title or kw in url for kw in live_keywords)


def extract_liveblog_topic(title):
    """Strips punctuation and stop-words to generate a clean topic key."""

    clean_title = re.sub(r'[^\w\s]', '', title.lower())

    stop_words = {"live", "updates", "war", "blog", "news", "coverage", "latest"}
    words = [w for w in clean_title.split() if w not in stop_words]

    return "-".join(words[:4])


def deduplicate_articles(articles, title_similarity_threshold=0.70):
    """
    Deduplicates articles based on URL uniqueness, scoped liveblog topic matching,
    and title similarity for syndicated copy.
    """
    if not articles:
        return []

    sorted_articles = sorted(
        articles,
        key=lambda x: x.get("publishedAt") or "",
        reverse=True,
    )

    seen_urls = set()
    unique_articles = []
    seen_liveblogs = set()

    for article in sorted_articles:
        url = article.get("url")
        title = article.get("title")
        source_id = (
            article.get("source", {}).get("id")
            or article.get("source", {}).get("name")
            or "unknown"
        )

        if not title or not url:
            continue

        if url in seen_urls:
            continue

        if is_liveblog(article):
            topic_key = extract_liveblog_topic(title)
            liveblog_signature = (source_id, topic_key)

            if liveblog_signature in seen_liveblogs:
                continue

            seen_liveblogs.add(liveblog_signature)
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


def _write_deduped(clean_articles, raw_filename, original_count, output_path=None):
    """
    Shared writer used by both run_dedupe() and run_deduplication().
    Returns the output path.
    """
    if output_path is None:
        output_path = os.path.join(DATA_DIR, "deduped_latest.json")

    removed_count = original_count - len(clean_articles)

    payload = {
        "metadata": {
            "source_raw_file": raw_filename,
            "original_count": original_count,
            "clean_count": len(clean_articles),
            "removed_count": removed_count,
        },
        "articles": clean_articles,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return output_path


def run_dedupe(raw_file, title_similarity_threshold=0.70):
    """
    Explicit-threaded dedupe: takes the specific raw file produced by fetch.run_fetch()
    so there's no ambiguity about which snapshot is being deduped.

    Returns (deduped_filepath, clean_count, removed_count).
    Raises RuntimeError on load or write failure so app.py can surface a clean error.
    """
    if not raw_file or not os.path.exists(raw_file):
        raise RuntimeError(f"Raw file not found: {raw_file}")

    try:
        with open(raw_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Failed to load {raw_file}: {e}")

    articles = data.get("articles", [])
    raw_filename = os.path.basename(raw_file)

    clean_articles = deduplicate_articles(articles, title_similarity_threshold)
    removed_count = len(articles) - len(clean_articles)

    print(f"Loaded {len(articles)} articles from {raw_filename}")
    print(
        f"Deduplication complete: {removed_count} duplicates removed "
        f"({len(clean_articles)} retained)."
    )

    try:
        output_path = _write_deduped(clean_articles, raw_filename, len(articles))
    except IOError as e:
        raise RuntimeError(f"Failed to write deduped dataset: {e}")

    print(f"Saved clean dataset to {output_path}")
    return output_path, len(clean_articles), removed_count


def run_deduplication(title_similarity_threshold=0.70):
    """
    CLI entry point: auto-discovers the newest articles_*.json on disk and dedupes it.
    Kept for the `python dedupe.py` workflow. Returns the clean articles list
    (or None on failure) so the __main__ block can print the near-threshold report.
    """
    articles, source_file = load_latest_raw_articles()
    if not articles:
        print(f"No raw articles found in {DATA_DIR}")
        return None

    raw_filename = os.path.basename(source_file)
    print(f"Loaded {len(articles)} articles from {raw_filename}")

    clean_articles = deduplicate_articles(articles, title_similarity_threshold)
    removed_count = len(articles) - len(clean_articles)

    print(
        f"Deduplication complete: {removed_count} duplicates removed "
        f"({len(clean_articles)} retained)."
    )

    try:
        output_path = _write_deduped(clean_articles, raw_filename, len(articles))
        print(f"Saved clean dataset to {output_path}")
        return clean_articles
    except IOError as e:
        print(f"Failed to save deduplicated data: {e}")
        return None


if __name__ == "__main__":
    clean_articles = run_deduplication()

    if clean_articles:
        print("\n--- Checking near-threshold candidate pairs (0.55 - 0.69) ---")
        near_matches = 0
        for i in range(len(clean_articles)):
            for j in range(i + 1, len(clean_articles)):
                sim = string_similarity(
                    clean_articles[i]["title"], clean_articles[j]["title"]
                )
                if 0.55 <= sim < 0.70:
                    near_matches += 1
                    print(f"[{sim:.2f}] Candidate near threshold:")
                    print(f"  A: {clean_articles[i]['title']}")
                    print(f"  B: {clean_articles[j]['title']}\n")

        if near_matches == 0:
            print("No articles found in the 0.55 - 0.69 similarity range.")