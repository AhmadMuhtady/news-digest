"""
utils.py — Shared helper functions for the news digest pipeline.
"""

def get_source_name(article: dict, default: str = "Unknown Source") -> str:
    """
    Safely extracts source name even if 'source' is explicitly None, missing,
    or not formatted as a dictionary.
    """
    if not isinstance(article, dict):
        return default
    source_obj = article.get("source")
    if isinstance(source_obj, dict):
        return source_obj.get("name") or default
    return default