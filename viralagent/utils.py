"""Small shared helpers: logging, ffmpeg detection, timing utilities."""

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import List, Optional

_LOG_CONFIGURED = False


def get_logger(name: str = "viralagent") -> logging.Logger:
    global _LOG_CONFIGURED
    if not _LOG_CONFIGURED:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
            datefmt="%H:%M:%S",
        )
        _LOG_CONFIGURED = True
    return logging.getLogger(name)


def have_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a subprocess, capturing output. Raises on non-zero when ``check``."""
    return subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def estimate_seconds(text: str, words_per_minute: int = 165) -> float:
    """Estimate spoken duration of a block of narration text."""
    words = len(text.split())
    if words == 0:
        return 0.0
    return round(words / max(words_per_minute, 1) * 60.0, 2)


def format_timestamp(seconds: float) -> str:
    """SRT-style timestamp: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0
    millis = int(round((seconds - int(seconds)) * 1000))
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{h:02d}:{m:02d}:{s:02d},{millis:03d}"


def first_available(*candidates: Optional[str]) -> str:
    for c in candidates:
        if c:
            return c
    return ""
