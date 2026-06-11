"""Packager — writes SEO metadata (title/description/tags) and a thumbnail.

Real mode: Claude writes a click-optimized but non-clickbait title, a keyword-rich
description with timestamps/hashtags, and a tight tag set, returned as structured
data. Offline mode derives solid metadata from the topic and script.

The thumbnail is an original generated card (ffmpeg) — safe to publish.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from ..config import Config
from ..llm import LLMClient
from ..models import Metadata, Script
from ..utils import get_logger, have_ffmpeg, run

log = get_logger("viralagent.package")

try:
    from pydantic import BaseModel, Field

    class _MetaSchema(BaseModel):
        title: str = Field(description="<=80 char YouTube title, strong but honest")
        description: str = Field(description="2-4 short paragraphs, keyword rich")
        tags: List[str] = Field(description="8-15 lowercase tags")
        thumbnail_text: str = Field(description="2-4 word punchy thumbnail caption")

    _SCHEMA_OK = True
except ImportError:  # pragma: no cover
    _SCHEMA_OK = False


class Packager:
    def __init__(self, config: Config, llm: LLMClient, *, dry_run: bool = False):
        self.config = config
        self.llm = llm
        self.dry_run = dry_run

    def package(self, script: Script, out_dir: Path) -> Metadata:
        if self.llm.available and _SCHEMA_OK:
            try:
                meta = self._package_with_claude(script)
            except Exception as exc:  # pragma: no cover
                log.warning("Claude packaging failed (%s); using fallback.", exc)
                meta = self._package_offline(script)
        else:
            meta = self._package_offline(script)

        meta.description = self._with_footer(meta.description)
        meta.thumbnail_path = self._thumbnail(script, meta, out_dir)
        log.info("Packaged: '%s' (%d tags).", meta.title, len(meta.tags))
        return meta

    # ------------------------------------------------------------------ #
    def _package_with_claude(self, script: Script) -> Metadata:
        pub = self.config.publish
        system = (
            "You are a YouTube growth specialist for a football channel. Write "
            "metadata that maximizes click-through and watch time WITHOUT misleading "
            "clickbait. Titles must be accurate to the script."
        )
        user = (
            f"TOPIC: {script.topic.title}\n"
            f"ANGLE: {script.topic.angle}\n"
            f"HOOK: {script.hook}\n"
            f"NARRATION:\n{script.full_narration}\n\n"
            "Write a title, a description, a tag list, and a 2-4 word thumbnail caption."
        )
        parsed = self.llm.parse(system, user, _MetaSchema, max_tokens=2000)
        tags = _dedupe(list(parsed.tags) + pub.get("default_tags", []))
        return Metadata(
            title=parsed.title.strip()[:100],
            description=parsed.description.strip(),
            tags=tags[:15],
            category_id=str(pub.get("category_id", "17")),
            visibility=pub.get("visibility", "private"),
            made_for_kids=bool(pub.get("made_for_kids", False)),
        )

    def _package_offline(self, script: Script) -> Metadata:
        pub = self.config.publish
        topic = script.topic
        title = topic.title if len(topic.title) <= 90 else topic.title[:87] + "..."
        description = (
            f"{topic.angle}\n\n"
            f"{script.hook}\n\n"
            "In this short: " + " ".join(s.on_screen_text for s in script.scenes if s.on_screen_text)
        )
        tags = _dedupe(list(topic.keywords) + pub.get("default_tags", []))
        return Metadata(
            title=title,
            description=description.strip(),
            tags=tags[:15],
            category_id=str(pub.get("category_id", "17")),
            visibility=pub.get("visibility", "private"),
            made_for_kids=bool(pub.get("made_for_kids", False)),
        )

    def _with_footer(self, description: str) -> str:
        footer = self.config.publish.get("description_footer", "").strip()
        if footer and footer not in description:
            return f"{description}\n\n{footer}"
        return description

    def _thumbnail(self, script: Script, meta: Metadata, out_dir: Path) -> Optional[str]:
        out = out_dir / "thumbnail.png"
        if not have_ffmpeg():
            (out_dir / "thumbnail.txt").write_text(
                f"THUMBNAIL CAPTION: {meta.title}\n", encoding="utf-8"
            )
            return None
        # 1280x720 thumbnail with a bold caption (uses the same font finder).
        from .visuals import _escape_drawtext, _find_font

        font = _find_font()
        text = _escape_drawtext(_thumb_text(script, meta))
        vf = "format=rgba"
        if font:
            vf += (
                f",drawtext=fontfile='{font}':text='{text}':fontcolor=white:"
                "fontsize=72:box=1:boxcolor=0xC1121F@0.85:boxborderw=26:"
                "x=(w-text_w)/2:y=h-text_h-80"
            )
        try:
            run(
                [
                    "ffmpeg", "-y", "-f", "lavfi",
                    "-i", "color=c=0x0B6E4F:s=1280x720",
                    "-vf", vf, "-frames:v", "1", str(out),
                ]
            )
            return str(out)
        except Exception as exc:  # pragma: no cover
            log.warning("Thumbnail render failed: %s", exc)
            return None


def _thumb_text(script: Script, meta: Metadata) -> str:
    # Prefer a short hook fragment; cap to keep it punchy.
    candidate = script.hook.split("?")[0].split(".")[0].strip()
    if 3 <= len(candidate) <= 28:
        return candidate.upper()
    words = meta.title.split()
    return " ".join(words[:4]).upper()


def _dedupe(items: List[str]) -> List[str]:
    seen, out = set(), []
    for item in items:
        key = item.lower().strip()
        if key and key not in seen:
            seen.add(key)
            out.append(item.lower().strip())
    return out
