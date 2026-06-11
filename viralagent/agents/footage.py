"""Footage — sources REAL video clips for the Short (legally).

Two backends, both keeping you on the right side of copyright:

  folder  -> uses clips YOU place in ``paths.clips_dir`` (your own recordings,
             licensed footage, or anything you've sourced and cleared). The agent
             is just the editor; you decide what goes in the folder.
  pexels  -> downloads rights-cleared soccer b-roll from the free Pexels video API
             (needs PEXELS_API_KEY). Real footage, licensed for reuse.

What this module deliberately does NOT do: scrape/download copyrighted clips from
YouTube/TikTok/etc. for re-upload. That's automated infringement and a fast route
to channel termination — out of scope on purpose.

``gather()`` returns a list of local video file paths (or [] to fall back to the
generated motion-graphic cards in visuals.py).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import List

from ..config import Config
from ..models import Script
from ..utils import get_logger

log = get_logger("viralagent.footage")

_VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".mkv")


class Footage:
    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def gather(self, script: Script, out_dir: Path) -> List[str]:
        backend = self.config.providers.get("footage", "auto")
        if backend == "none":
            return []

        chain = self._resolve_chain(backend)
        for name in chain:
            try:
                clips = self._run_backend(name, script, out_dir)
                if clips:
                    log.info("Footage via '%s': %d clip(s).", name, len(clips))
                    return clips
            except Exception as exc:  # pragma: no cover - provider variance
                log.warning("Footage backend '%s' failed: %s", name, exc)
        log.info("No real footage available; will use generated visuals.")
        return []

    # ------------------------------------------------------------------ #
    def _resolve_chain(self, backend: str) -> List[str]:
        if backend != "auto":
            return [backend]
        chain: List[str] = []
        if self._folder_has_clips():
            chain.append("folder")
        if self.config.secrets.pexels_api_key:
            chain.append("pexels")
        return chain

    def _run_backend(self, name: str, script: Script, out_dir: Path) -> List[str]:
        if name == "folder":
            return self._folder(script, out_dir)
        if name == "pexels":
            return self._pexels(script, out_dir)
        raise ValueError(f"Unknown footage backend: {name}")

    # -- folder backend -------------------------------------------------------
    def _folder_has_clips(self) -> bool:
        return bool(self._list_folder_clips())

    def _list_folder_clips(self) -> List[Path]:
        root = self.config.clips_dir
        if not root.exists():
            return []
        return sorted(
            p for p in root.rglob("*") if p.suffix.lower() in _VIDEO_EXTS
        )

    def _folder(self, script: Script, out_dir: Path) -> List[str]:
        clips = self._list_folder_clips()
        if not clips:
            return []
        # Prefer clips under a subfolder whose name matches the topic slug, then
        # fall back to the whole library.
        slug = script.topic.slug if script.topic else ""
        preferred = [c for c in clips if slug and slug in str(c.parent).lower()]
        chosen = preferred or clips
        return [str(c) for c in chosen]

    # -- pexels backend -------------------------------------------------------
    def _pexels(self, script: Script, out_dir: Path) -> List[str]:
        if self.dry_run:
            return []
        import requests  # lazy

        key = self.config.secrets.pexels_api_key
        if not key:
            return []
        topic = script.topic
        query = " ".join((topic.keywords or [topic.title])[:3]) if topic else "soccer"
        portrait = self.config.content.get("format", "short") != "long"
        params = {
            "query": query or "soccer football",
            "orientation": "portrait" if portrait else "landscape",
            "per_page": 6,
            "size": "medium",
        }
        resp = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": key},
            params=params,
            timeout=60,
        )
        resp.raise_for_status()
        videos = resp.json().get("videos", [])

        footage_dir = out_dir / "footage"
        footage_dir.mkdir(parents=True, exist_ok=True)
        saved: List[str] = []
        for i, video in enumerate(videos[:5]):
            link = self._best_video_file(video, portrait)
            if not link:
                continue
            try:
                data = requests.get(link, timeout=120)
                data.raise_for_status()
                dest = footage_dir / f"pexels_{i:02d}.mp4"
                dest.write_bytes(data.content)
                saved.append(str(dest))
            except Exception as exc:  # pragma: no cover
                log.warning("Pexels clip %d download failed: %s", i, exc)
        return saved

    @staticmethod
    def _best_video_file(video: dict, portrait: bool) -> str:
        """Pick a reasonably-sized file (~HD) from a Pexels video entry."""
        files = video.get("video_files", [])
        if not files:
            return ""

        def score(f: dict) -> tuple:
            h = f.get("height") or 0
            w = f.get("width") or 0
            is_portrait = h >= w
            # Prefer orientation match, then height closest to 1280.
            orient_ok = 1 if is_portrait == portrait else 0
            return (orient_ok, -abs((h or 0) - 1280))

        best = sorted(files, key=score, reverse=True)[0]
        return best.get("link", "")
