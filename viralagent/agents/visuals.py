"""Visuals — produces one background asset per scene.

Default backend ('textcards') renders original motion-graphic-style color cards
with ffmpeg (optionally with the on-screen caption drawn on them) — no external
footage and no licensing concerns. A 'stock' backend hook is provided for wiring
in a licensed footage provider.

Dimensions follow ``content.format``: short = 1080x1920, long = 1920x1080.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import List, Optional

from ..config import Config
from ..models import Script
from ..utils import get_logger, have_ffmpeg, run

log = get_logger("viralagent.visuals")

# A football-flavored palette (deep pitch greens, floodlight, kit accents).
_PALETTE = [
    "0x0B6E4F", "0x08313A", "0x14213D", "0x1B998B",
    "0xC1121F", "0x2A2D34", "0x06402B", "0x023E8A",
]


class Visuals:
    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def dimensions(self) -> tuple[int, int]:
        if self.config.content.get("format") == "long":
            return 1920, 1080
        return 1080, 1920

    def generate(self, script: Script, out_dir: Path) -> List[str]:
        scenes_dir = out_dir / "scenes"
        scenes_dir.mkdir(parents=True, exist_ok=True)

        if not have_ffmpeg():
            log.warning("ffmpeg not found — writing visual direction stubs instead.")
            return self._stub_assets(script, scenes_dir)

        backend = self.config.providers.get("visuals", "auto")
        if backend == "stock":
            assets = self._stock(script, scenes_dir)
            if assets:
                return assets
            log.warning("Stock backend unavailable; falling back to text cards.")

        return self._textcards(script, scenes_dir)

    # ------------------------------------------------------------------ #
    def _textcards(self, script: Script, scenes_dir: Path) -> List[str]:
        w, h = self.dimensions()
        font = _find_font()
        assets: List[str] = []
        all_scenes = [("HOOK", script.hook)] + [
            (s.on_screen_text or f"SCENE {i+1}", s.narration)
            for i, s in enumerate(script.scenes)
        ]
        for idx, (caption, _) in enumerate(all_scenes):
            color = _PALETTE[idx % len(_PALETTE)]
            out = scenes_dir / f"scene_{idx:02d}.png"
            filters = "format=rgba"
            if font and caption:
                safe = _escape_drawtext(caption)
                filters += (
                    f",drawtext=fontfile='{font}':text='{safe}':"
                    f"fontcolor=white:fontsize={int(h*0.06)}:"
                    "box=1:boxcolor=black@0.35:boxborderw=24:"
                    "x=(w-text_w)/2:y=(h-text_h)/2"
                )
            try:
                run(
                    [
                        "ffmpeg", "-y", "-f", "lavfi",
                        "-i", f"color=c={color}:s={w}x{h}",
                        "-vf", filters, "-frames:v", "1", str(out),
                    ]
                )
                assets.append(str(out))
            except Exception as exc:  # pragma: no cover
                log.warning("Card render failed for scene %d: %s", idx, exc)
        log.info("Rendered %d scene cards (%dx%d).", len(assets), w, h)
        return assets

    def _stock(self, script: Script, scenes_dir: Path) -> List[str]:
        """Hook for a licensed stock-footage provider.

        Intentionally a no-op unless you implement it: returning [] makes the
        caller fall back to original text cards rather than risk using footage
        you don't have rights to.
        """
        if not self.config.secrets.stock_api_key or self.dry_run:
            return []
        log.info("Stock backend configured but not implemented; see visuals.py.")
        return []

    def _stub_assets(self, script: Script, scenes_dir: Path) -> List[str]:
        assets: List[str] = []
        scenes = [("hook", script.hook, script.hook)] + [
            (f"scene_{i:02d}", s.on_screen_text, s.visual)
            for i, s in enumerate(script.scenes)
        ]
        for name, caption, visual in scenes:
            path = scenes_dir / f"{name}.txt"
            path.write_text(
                f"CAPTION: {caption}\nVISUAL DIRECTION: {visual}\n", encoding="utf-8"
            )
            assets.append(str(path))
        return assets


def _find_font() -> Optional[str]:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    for pattern in ("/usr/share/fonts/**/*.ttf", "/Library/Fonts/*.ttf"):
        hits = glob.glob(pattern, recursive=True)
        if hits:
            return hits[0]
    return None


def _escape_drawtext(text: str) -> str:
    # Escape characters that are special to ffmpeg's drawtext filter.
    return (
        text.replace("\\", "")
        .replace(":", "\\:")
        .replace("'", "")
        .replace("%", "")
    )
