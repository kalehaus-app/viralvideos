"""Thin wrapper around the Claude API used by the reasoning-heavy agents.

Centralizes model selection, adaptive thinking, effort, structured outputs, and
the optional web-search server tool, and exposes an ``available`` flag so callers
can fall back to offline templates when no API key is configured.

Defaults to ``claude-opus-4-8`` with adaptive thinking — the recommended setup for
agentic / generation work on the current Opus-tier model.
"""

from __future__ import annotations

from typing import List, Optional, Type, TypeVar

from .config import Config
from .utils import get_logger

log = get_logger("viralagent.llm")

try:  # The anthropic SDK is optional at import time so dry-run needs no key.
    import anthropic

    _SDK_AVAILABLE = True
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore
    _SDK_AVAILABLE = False

T = TypeVar("T")


class LLMClient:
    """Wraps ``anthropic.Anthropic`` with project-wide defaults."""

    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.model: str = config.get("llm.model", "claude-opus-4-8")
        self.effort: str = config.get("llm.effort", "high")
        self.dry_run = dry_run
        self._client = None

        key = config.secrets.anthropic_api_key
        if dry_run:
            log.info("LLM in dry-run mode — using offline templates.")
        elif not _SDK_AVAILABLE:
            log.warning("anthropic SDK not installed — offline templates only.")
        elif not key:
            log.warning("ANTHROPIC_API_KEY not set — offline templates only.")
        else:
            self._client = anthropic.Anthropic(api_key=key)

    @property
    def available(self) -> bool:
        """True when real Claude calls can be made."""
        return self._client is not None and not self.dry_run

    # ------------------------------------------------------------------ #
    # Generation helpers
    # ------------------------------------------------------------------ #
    def complete(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 4000,
        thinking: bool = True,
    ) -> str:
        """Return Claude's text response to a single-turn prompt."""
        if not self.available:
            raise RuntimeError("LLMClient.complete called while unavailable")

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": self.effort},
        }
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}

        message = self._client.messages.create(**kwargs)
        return "".join(b.text for b in message.content if b.type == "text").strip()

    def parse(
        self,
        system: str,
        user: str,
        schema: Type[T],
        *,
        max_tokens: int = 4000,
    ) -> T:
        """Return a validated instance of ``schema`` (a Pydantic model).

        Uses structured outputs (``messages.parse``) so the response is guaranteed
        to match the schema.
        """
        if not self.available:
            raise RuntimeError("LLMClient.parse called while unavailable")

        response = self._client.messages.parse(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            thinking={"type": "adaptive"},
            output_config={"effort": self.effort},
            output_format=schema,
        )
        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            raise RuntimeError(
                f"Structured output failed (stop_reason={response.stop_reason})"
            )
        return parsed

    def web_research(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 6000,
        max_searches: int = 6,
    ) -> str:
        """Run a prompt with the web-search server tool enabled.

        Falls back to a plain completion if web search is disabled in config.
        """
        if not self.available:
            raise RuntimeError("LLMClient.web_research called while unavailable")

        if not self.config.get("llm.use_web_search", True):
            return self.complete(system, user, max_tokens=max_tokens)

        tools: List[dict] = [
            {
                "type": "web_search_20260209",
                "name": "web_search",
                "max_uses": max_searches,
            }
        ]
        messages = [{"role": "user", "content": user}]
        # Server-side tools may pause; resume until the model is done.
        for _ in range(max_searches + 2):
            message = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=tools,
                thinking={"type": "adaptive"},
                output_config={"effort": self.effort},
            )
            if message.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": message.content})
                continue
            return "".join(
                b.text for b in message.content if b.type == "text"
            ).strip()
        # Exhausted continuations — return whatever text we last have.
        return "".join(b.text for b in message.content if b.type == "text").strip()
