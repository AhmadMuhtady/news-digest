"""
digest.py — Generates a structured prompt payload and Markdown digest.
"""

import os
import json
from utils import get_source_name

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
INPUT_FILE = os.path.join(DATA_DIR, "deduped_latest.json")
OUTPUT_FILE = os.path.join(DATA_DIR, "digest_report.md")


def load_deduped_data(filepath=INPUT_FILE):
    """Loads cleaned articles and metadata from disk."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}. Run dedupe.py first.")
        return None, None
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("articles", []), data.get("metadata", {})
    except (IOError, json.JSONDecodeError) as e:
        print(f"Failed to read {filepath}: {e}")
        return None, None


def generate_llm_prompt(articles):
    """
    Formats raw articles into a clean text block designed specifically
    to guide an LLM in clustering multifaceted news stories with strict citations.
    """
    article_blocks = []
    for idx, art in enumerate(articles, 1):
        source = get_source_name(art)
        title = art.get("title", "Untitled")
        desc = (art.get("description") or "No description available.").strip()
        pub_date = art.get("publishedAt", "")[:10]
        url = art.get("url", "#")
        
        block = (
            f"[{idx}] SOURCE: {source} ({pub_date})\n"
            f"    TITLE: {title}\n"
            f"    SUMMARY: {desc}\n"
            f"    URL: {url}"
        )
        article_blocks.append(block)

    articles_text = "\n\n".join(article_blocks)

    system_prompt = (
        "You are a Senior Investigative Foreign Affairs Editor specializing in the Middle East. "
        "Your task is to analyze raw news feeds and synthesize them into an Executive Intelligence Briefing."
    )

    user_payload = f"""Analyze the provided list of {len(articles)} raw news articles and produce a cohesive Executive Intelligence Briefing in Markdown.

--- BEGIN RAW ARTICLES ({len(articles)} total) ---

{articles_text}

--- END RAW ARTICLES ---

CRITICAL FORMATTING & CITATION INSTRUCTIONS:
1. MANDATORY INLINE CITATIONS: Every factual claim or summary bullet MUST include an inline Markdown hyperlink to its original article URL.
   Format: [Source Name](URL)
   Example: "Houthi forces seized key coastal positions in Yemen ([Al Jazeera](https://example.com/art1))."
   Do NOT invent URLs; use the exact URL provided in the raw articles list above.

2. EXECUTIVE TAKEAWAYS: Start with EXACTLY 3 bullet points under an "## Executive Takeaways" header. Do NOT use Markdown tables for takeaways.

3. THEMATIC CLUSTERING: Do NOT summarize article-by-article. Group multi-angle coverage into major thematic sections (e.g., "### 1. Red Sea Escalation & Economic Shockwaves", "### 2. Regional Diplomatic Maneuvering").

4. NARRATIVE SYNTHESIS: Combine different facts from multiple sources into a single fluid narrative per topic. Mention conflicting updates or different angles explicitly with citations.
"""

    return system_prompt, user_payload


def build_fallback_markdown(articles, metadata):
    """Generates a structured static Markdown report if no LLM API is called."""
    lines = [
        "# Middle East News Digest (Raw Pipeline Output)",
        f"**Articles Analyzed:** {len(articles)} | **Source File:** `{metadata.get('source_raw_file', 'N/A')}`\n",
        "> *Note: This is a structured pass-through report. Feed this dataset to an LLM using the system prompt for narrative synthesis.*\n",
        "---"
    ]

    by_source = {}
    for item in articles:
        source_name = get_source_name(item, default="Other Sources")
        by_source.setdefault(source_name, []).append(item)

    for source, item_list in sorted(by_source.items()):
        lines.append(f"\n## {source} ({len(item_list)})")
        for idx, item in enumerate(item_list, 1):
            title = item.get("title", "Untitled")
            url = item.get("url", "#")
            desc = (item.get("description") or "No description provided.").strip()
            date = item.get("publishedAt", "")[:10]
            
            lines.append(f"{idx}. **[{title}]({url})** `{date}`")
            lines.append(f"   > {desc}\n")

    return "\n".join(lines)


def run_digest():
    articles, metadata = load_deduped_data()
    if not articles:
        return

    print(f"Loaded {len(articles)} deduplicated articles.")

    sys_prompt, user_payload = generate_llm_prompt(articles)
    fallback_report = build_fallback_markdown(articles, metadata)
    
    try:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(fallback_report)
        print(f"Saved baseline digest report to: {OUTPUT_FILE}")
    except IOError as e:
        print(f"Failed to write digest report: {e}")


if __name__ == "__main__":
    run_digest()