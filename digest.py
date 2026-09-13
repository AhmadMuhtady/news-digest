"""
digest.py — Generates a structured prompt payload and Markdown digest.

What it does:
- Loads news-digest/data/deduped_latest.json.
- Prepares a formatted prompt payload for an LLM (e.g. OpenAI/Anthropic/Groq/Ollama).
- Outputs a fallback human-readable Markdown digest directly to disk.
- Writes output to news-digest/data/digest_report.md.
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
    to guide an LLM in clustering multifaceted news stories.
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

    system_prompt = """You are a Senior Investigative Foreign Affairs Editor specializing in the Middle East.

Your task is to analyze the provided list of raw news articles and produce a cohesive Executive Intelligence Briefing in Markdown format.

Instructions:
1. THEMATIC CLUSTERING: Do NOT summarize article-by-article. Instead, group related multi-angle coverage into major thematic sections (e.g., "Red Sea Escalation & Economic Impact", "Humanitarian & Displacement Updates").
2. NARRATIVE SYNTHESIS: Combine different facts from multiple sources into a single fluid narrative per topic. Mention conflicting updates or different angles explicitly.
3. CITATIONS: Use inline markdown links back to original article URLs when citing specific claims or statistics (e.g., [Al Jazeera reported...](URL)).
4. EXECUTIVE SUMMARY: Include a top-level 3-bullet point executive takeaway at the start.
"""

    return system_prompt, f"--- BEGIN ARTICLES ({len(articles)} total) ---\n\n" + articles_text


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

    print("\n✅ Pipeline execution complete!")
    print(f"   Fetch  -> Data saved in data/")
    print(f"   Dedupe -> Cleaned ({len(articles)} retained)")
    print(f"   Digest -> Markdown generated at data/digest_report.md")


if __name__ == "__main__":
    run_digest()