"""Disk cache for LLM entity extraction. Ensures reproducibility across runs.

Key = SHA256(text). Value = JSON list of entities.
Cache lives at eval/results/.entity_cache/{hash}.json
"""

import hashlib
import json
import os
from pathlib import Path

_cache_dir = Path(os.path.join(os.path.dirname(__file__), "results", ".entity_cache"))


def _key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def get(text: str) -> list[str] | None:
    """Return cached entities for text, or None if not cached."""
    path = _cache_dir / f"{_key(text)}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def put(text: str, entities: list[str]) -> None:
    """Cache entities for text."""
    _cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_dir / f"{_key(text)}.json"
    path.write_text(json.dumps(sorted(entities)))
