# journal/cache.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, Any

DEFAULT_CACHE_PATH = Path.home() / ".devdiary_cache.json"

def load_cache(path: Path = DEFAULT_CACHE_PATH) -> Dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # corrupted cache; start fresh
            return {}
    return {}

def save_cache(cache: Dict[str, Any], path: Path = DEFAULT_CACHE_PATH) -> None:
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def get_cached(hash_: str, cache: Dict[str, Any]) -> Any | None:
    return cache.get(hash_)

def put_cached(hash_: str, value: Any, cache: Dict[str, Any]) -> None:
    cache[hash_] = value
    
def purge_bad_entries(cache: dict) -> dict:
    to_delete = []
    for k, v in cache.items():
        # If earlier runs stored an error fallback
        if isinstance(v, dict) and "bullet" in v and "summary unavailable" in v["bullet"]:
            to_delete.append(k)
    for k in to_delete:
        cache.pop(k, None)
    return cache

