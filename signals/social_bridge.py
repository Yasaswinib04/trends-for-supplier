"""
Social Bridge — YouTube Haul Video Parser
-------------------------------------------
Searches YouTube Data API v3 for recent "Kurti haul" videos, parses
descriptions using Regex to extract affiliate link densities,
and returns a social buzz metrics payload.

Gracefully falls back to cached reference data if YOUTUBE_API_KEY
is not configured or rate-limited.

Usage:
    from signals.social_bridge import get_social_signals
    buzz = get_social_signals("chanderi kurti")
"""

import json
import os
import re
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).parent.parent
CACHE_FILE = ROOT_DIR / "data" / "social_bridge_cache.json"

LINK_REGEX = re.compile(
    r"https?://[^\s\)\]]+",
    re.IGNORECASE,
)
AFFILIATE_PATTERNS = re.compile(
    r"(affiliate|amzn\.to|fkrt\.it|bit\.ly|shop\.myntra|nykaafashion|"
    r"meesho|linktr\.ee|taplink|lync\.me|commission|referral)",
    re.IGNORECASE,
)


def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(data):
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)


def get_social_signals(trend_name: str, search_terms: list = None,
                       use_cache: bool = True) -> dict:
    """
    Search YouTube for Kurti haul videos related to the trend,
    extract affiliate link density from descriptions.

    Returns:
        dict with haul_count, affiliate_density, top_mentions, social_buzz_level.
    """
    api_key = os.getenv("YOUTUBE_API_KEY", "")

    terms = search_terms or [trend_name]
    query = " OR ".join(f'"{t}"' for t in terms[:3])
    query = f"({query}) haul kurti"

    cache_key = _cache_key(terms)

    if use_cache and cache_key in _load_social_cache():
        return _load_social_cache()[cache_key]

    if not api_key:
        return _cached_fallback(terms, cache_key, "No YOUTUBE_API_KEY configured")

    try:
        result = _fetch_youtube(api_key, query)
        _save_to_cache(cache_key, result)
        return result
    except Exception as e:
        return _cached_fallback(terms, cache_key,
                                f"YouTube API error: {str(e)[:80]}")


def _fetch_youtube(api_key: str, query: str) -> dict:
    import urllib.request
    import urllib.parse

    params = urllib.parse.urlencode({
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 10,
        "order": "date",
        "relevanceLanguage": "en",
        "regionCode": "IN",
        "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"
    req = urllib.request.Request(url)

    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())

    items = data.get("items", [])
    video_ids = [item["id"]["videoId"] for item in items
                 if item.get("id", {}).get("videoId")]

    descriptions = []
    affiliate_links = 0
    total_links = 0

    channel_ids = set()

    for video_id in video_ids:
        desc_params = urllib.parse.urlencode({
            "part": "snippet",
            "id": video_id,
            "key": api_key,
        })
        desc_url = f"https://www.googleapis.com/youtube/v3/videos?{desc_params}"

        try:
            desc_req = urllib.request.Request(desc_url)
            with urllib.request.urlopen(desc_req, timeout=10) as desc_resp:
                desc_data = json.loads(desc_resp.read())

            for vitem in desc_data.get("items", []):
                desc = vitem.get("snippet", {}).get("description", "")
                channel_id = vitem.get("snippet", {}).get("channelId", "")
                channel_ids.add(channel_id)
                descriptions.append(desc)

                links = LINK_REGEX.findall(desc)
                total_links += len(links)
                affiliate_links += sum(1 for l in links
                                       if AFFILIATE_PATTERNS.search(l))
        except Exception:
            continue

    haul_count = len(video_ids)
    affiliate_density = round(affiliate_links / max(haul_count, 1), 2)
    link_density = round(total_links / max(haul_count, 1), 2)

    if haul_count >= 6 and affiliate_density >= 2.0:
        buzz_level = "high"
    elif haul_count >= 3 and affiliate_density >= 1.0:
        buzz_level = "moderate"
    elif haul_count >= 1:
        buzz_level = "low"
    else:
        buzz_level = "none"

    return {
        "source": "social_bridge",
        "live": True,
        "fetched_at": datetime.now().isoformat(),
        "query": query,
        "hauls_in_last_30d": haul_count,
        "affiliate_link_density": affiliate_density,
        "total_link_density": link_density,
        "unique_creators": len(channel_ids),
        "social_buzz_level": buzz_level,
        "fallback": False,
        "sample_descriptions": [d[:200] for d in descriptions[:3]],
    }


def _cached_fallback(terms: list, cache_key: str, reason: str) -> dict:
    cache = _load_social_cache()
    if cache_key in cache:
        cached = cache[cache_key]
        cached["fallback"] = True
        cached["fallback_reason"] = reason
        return cached

    return {
        "source": "social_bridge",
        "live": False,
        "hauls_in_last_30d": 0,
        "affiliate_link_density": 0,
        "total_link_density": 0,
        "unique_creators": 0,
        "social_buzz_level": "unknown",
        "fallback": True,
        "fallback_reason": reason,
    }


def _cache_key(terms: list) -> str:
    return "|".join(sorted(terms))


def _load_social_cache():
    return load_cache()


def _save_to_cache(cache_key: str, data: dict):
    cache = load_cache()
    cache[cache_key] = {
        "hauls_in_last_30d": data.get("hauls_in_last_30d", 0),
        "affiliate_link_density": data.get("affiliate_link_density", 0),
        "total_link_density": data.get("total_link_density", 0),
        "unique_creators": data.get("unique_creators", 0),
        "social_buzz_level": data.get("social_buzz_level", "unknown"),
        "fetched_at": data.get("fetched_at", datetime.now().isoformat()),
    }
    save_cache(cache)
