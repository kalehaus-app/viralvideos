"""Layered configuration: built-in defaults < config.yaml < environment variables.

Environment overrides use the form ``VIRALAGENT__SECTION__KEY=value`` (double
underscores separate nesting levels), e.g. ``VIRALAGENT__CONTENT__CADENCE_HOURS=6``.

Secrets are read from well-known env vars (see :class:`Secrets`) and never written
to disk.
"""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a core dependency
    yaml = None


# --------------------------------------------------------------------------- #
# Built-in defaults (mirrors config.example.yaml).
# --------------------------------------------------------------------------- #
DEFAULTS: Dict[str, Any] = {
    "channel": {
        "name": "Touchline Tales",
        "niche": "viral soccer and World Cup moments",
        "persona": (
            "A fast-talking, deeply knowledgeable football storyteller who turns "
            "stats, history, and viral moments into edge-of-your-seat "
            "micro-documentaries."
        ),
        "tone": "energetic, punchy, authoritative, a little cheeky",
        "language": "en",
        "audience": (
            "global football fans aged 16-34 who live on YouTube Shorts and TikTok"
        ),
        "banned_topics": [],
    },
    "content": {
        "format": "short",
        "style": "story",        # "story" or "commentary" (analysis-forward)
        "target_seconds": 50,
        "cadence_hours": 12,
        "topics_per_cycle": 5,
        "words_per_minute": 165,
    },
    "llm": {
        "model": "claude-opus-4-8",
        "effort": "high",
        "use_web_search": True,
    },
    "providers": {
        "voiceover": "auto",
        "visuals": "auto",
        "footage": "auto",       # auto | folder | pexels | none
        "publish": "auto",
    },
    "publish": {
        "visibility": "private",
        "category_id": "17",
        "made_for_kids": False,
        "default_tags": ["soccer", "football", "world cup"],
        "description_footer": (
            "⚽ Subscribe for daily football stories. "
            "This video uses AI-assisted production."
        ),
    },
    "paths": {
        "output_dir": "output",
        "state_file": "state.json",
        "clips_dir": "assets/clips",   # drop your own/licensed clips here
    },
}


@dataclass
class Secrets:
    """Secrets resolved from the environment. Empty string means "not set"."""

    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    openai_api_key: str = ""
    stock_api_key: str = ""
    pexels_api_key: str = ""
    youtube_client_secrets: str = "client_secret.json"
    youtube_token_file: str = "youtube_token.json"

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            elevenlabs_api_key=os.environ.get("ELEVENLABS_API_KEY", ""),
            elevenlabs_voice_id=os.environ.get("ELEVENLABS_VOICE_ID", ""),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            stock_api_key=os.environ.get("STOCK_API_KEY", ""),
            pexels_api_key=os.environ.get("PEXELS_API_KEY", ""),
            youtube_client_secrets=os.environ.get(
                "YOUTUBE_CLIENT_SECRETS", "client_secret.json"
            ),
            youtube_token_file=os.environ.get(
                "YOUTUBE_TOKEN_FILE", "youtube_token.json"
            ),
        )


@dataclass
class Config:
    """Resolved configuration plus environment-derived secrets."""

    data: Dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULTS))
    secrets: Secrets = field(default_factory=Secrets.from_env)

    # -- convenience accessors ------------------------------------------------
    @property
    def channel(self) -> Dict[str, Any]:
        return self.data["channel"]

    @property
    def content(self) -> Dict[str, Any]:
        return self.data["content"]

    @property
    def llm(self) -> Dict[str, Any]:
        return self.data["llm"]

    @property
    def providers(self) -> Dict[str, Any]:
        return self.data["providers"]

    @property
    def publish(self) -> Dict[str, Any]:
        return self.data["publish"]

    @property
    def output_dir(self) -> Path:
        return Path(self.data["paths"]["output_dir"])

    @property
    def state_file(self) -> Path:
        return Path(self.data["paths"]["state_file"])

    @property
    def clips_dir(self) -> Path:
        return Path(self.data["paths"].get("clips_dir", "assets/clips"))

    def get(self, path: str, default: Any = None) -> Any:
        """Dotted-path lookup, e.g. ``cfg.get("content.format")``."""
        node: Any = self.data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def _deep_merge(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge ``overrides`` into a copy of ``base``."""
    out = copy.deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _coerce(value: str) -> Any:
    """Coerce a string env value into bool/int/float when it clearly is one."""
    lowered = value.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


def _env_overrides(prefix: str = "VIRALAGENT__") -> Dict[str, Any]:
    """Build a nested override dict from ``VIRALAGENT__A__B=value`` env vars."""
    overrides: Dict[str, Any] = {}
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        parts = [p.lower() for p in env_key[len(prefix):].split("__") if p]
        if not parts:
            continue
        node = overrides
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = _coerce(env_val)
    return overrides


def load_dotenv(path: str | os.PathLike = ".env") -> None:
    """Load ``KEY=value`` pairs from a ``.env`` file into ``os.environ``.

    Real environment variables always win — values already set are never
    overwritten. Quotes around values and ``#`` comment lines are handled.
    Missing file is a no-op. No third-party dependency required.
    """
    p = Path(path)
    if not p.exists():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_config(path: str | os.PathLike | None = None) -> Config:
    """Load configuration from defaults, an optional YAML file, and the env.

    Looks for ``config.yaml`` in the CWD when ``path`` is not given. A ``.env``
    file in the CWD is auto-loaded first (without overriding real env vars), so
    secrets like ``ANTHROPIC_API_KEY`` work just by being in that file. Missing
    files are fine — defaults are used.
    """
    load_dotenv()
    data = copy.deepcopy(DEFAULTS)

    candidate = Path(path) if path else Path("config.yaml")
    if candidate.exists():
        if yaml is None:  # pragma: no cover
            raise RuntimeError("PyYAML is required to read config files")
        loaded = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"Config file {candidate} must be a mapping at the top level")
        data = _deep_merge(data, loaded)

    data = _deep_merge(data, _env_overrides())
    return Config(data=data, secrets=Secrets.from_env())
