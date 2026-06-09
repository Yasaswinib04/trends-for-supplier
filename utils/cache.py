import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"

def load_cache(cache_name):
    cache_path = DATA_DIR / cache_name
    if cache_path.exists():
        with open(cache_path) as f:
            return json.load(f)
    return {}

def save_cache(cache_name, data):
    cache_path = DATA_DIR / cache_name
    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2, default=str)

def get_cached_fallback(trend_id):
    fallback_path = DATA_DIR / "sample_outputs" / f"{trend_id}.json"
    if fallback_path.exists():
        with open(fallback_path) as f:
            return json.load(f)
    return None
