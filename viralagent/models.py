"""Typed data structures that flow between pipeline stages.

These are plain dataclasses (JSON-serializable) so every intermediate artifact
can be written to / read from a bundle directory and inspected by a human.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


def slugify(text: str, max_len: int = 60) -> str:
    """Filesystem- and URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text[:max_len].strip("-") or "untitled"


@dataclass
class Topic:
    """A candidate content idea discovered by the TrendScout."""

    title: str
    angle: str                      # the specific hook/spin for this video
    why_now: str = ""               # why it's timely / viral right now
    virality_score: float = 0.0     # 0-100, the scout's estimate
    keywords: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.title)


@dataclass
class Scene:
    """One beat of the video: a line of narration + a visual direction."""

    narration: str                  # what the voiceover says
    visual: str                     # description used to source/generate visuals
    on_screen_text: str = ""        # short caption/keyword burned on screen
    seconds: float = 0.0            # estimated duration (filled by scriptwriter)


@dataclass
class Script:
    """A complete, scene-by-scene video script."""

    topic: Topic
    hook: str                       # the first 1-2 seconds — must stop the scroll
    scenes: List[Scene] = field(default_factory=list)
    call_to_action: str = ""
    estimated_seconds: float = 0.0

    @property
    def full_narration(self) -> str:
        parts = [self.hook] + [s.narration for s in self.scenes]
        if self.call_to_action:
            parts.append(self.call_to_action)
        return "\n".join(p.strip() for p in parts if p.strip())


@dataclass
class Metadata:
    """YouTube publishing metadata."""

    title: str
    description: str
    tags: List[str] = field(default_factory=list)
    category_id: str = "17"
    visibility: str = "private"
    made_for_kids: bool = False
    thumbnail_path: Optional[str] = None


@dataclass
class VideoBundle:
    """The full artifact set for one video, anchored to a directory on disk."""

    directory: Path
    topic: Optional[Topic] = None
    script: Optional[Script] = None
    metadata: Optional[Metadata] = None
    voiceover_path: Optional[str] = None
    scene_assets: List[str] = field(default_factory=list)
    captions_path: Optional[str] = None
    video_path: Optional[str] = None
    youtube_id: Optional[str] = None
    notes: List[str] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return self.directory.name

    def log(self, message: str) -> None:
        self.notes.append(message)

    # -- persistence ----------------------------------------------------------
    def write_json(self, name: str, obj: Any) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / name
        path.write_text(_to_json(obj), encoding="utf-8")
        return path

    def save_manifest(self) -> Path:
        """Persist a top-level manifest describing the whole bundle."""
        manifest = {
            "slug": self.slug,
            "topic": asdict(self.topic) if self.topic else None,
            "voiceover_path": self.voiceover_path,
            "scene_assets": self.scene_assets,
            "captions_path": self.captions_path,
            "video_path": self.video_path,
            "youtube_id": self.youtube_id,
            "metadata": asdict(self.metadata) if self.metadata else None,
            "notes": self.notes,
        }
        return self.write_json("manifest.json", manifest)


def _to_json(obj: Any) -> str:
    def encode(o: Any) -> Any:
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if isinstance(o, Path):
            return str(o)
        raise TypeError(f"Not JSON serializable: {type(o)}")

    if hasattr(obj, "__dataclass_fields__"):
        obj = asdict(obj)
    return json.dumps(obj, indent=2, ensure_ascii=False, default=encode)
