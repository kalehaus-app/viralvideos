"""Persistent state: which topics/titles we've already produced, to avoid repeats.

A simple JSON file is enough for a single-channel agent. Swap for a DB if you scale
to many channels.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List


class StateStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._data: Dict[str, Any] = {"produced": [], "published": []}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        self._data.setdefault("produced", [])
        self._data.setdefault("published", [])

    def _save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    # -- dedup helpers --------------------------------------------------------
    def seen_slugs(self) -> List[str]:
        return [entry["slug"] for entry in self._data["produced"]]

    def is_recent(self, slug: str) -> bool:
        return slug in self.seen_slugs()

    def record_produced(self, slug: str, title: str) -> None:
        self._data["produced"].append(
            {"slug": slug, "title": title, "ts": time.time()}
        )
        self._save()

    def record_published(self, slug: str, youtube_id: str) -> None:
        self._data["published"].append(
            {"slug": slug, "youtube_id": youtube_id, "ts": time.time()}
        )
        self._save()

    def last_published_ts(self) -> float:
        if not self._data["published"]:
            return 0.0
        return max(entry.get("ts", 0.0) for entry in self._data["published"])
