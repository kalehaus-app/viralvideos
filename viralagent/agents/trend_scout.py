"""TrendScout — discovers and ranks viral soccer / World Cup topics.

Real mode: Claude + the web-search tool surfaces what's blowing up *right now*,
then returns a ranked, structured list of video-worthy angles.

Offline mode: a curated set of evergreen football angles so a cycle always has
something strong to produce.
"""

from __future__ import annotations

import json
from typing import List

from ..config import Config
from ..llm import LLMClient
from ..models import Topic
from ..utils import get_logger

log = get_logger("viralagent.scout")

# Pydantic schema for structured output — only needed when the SDK is present.
try:
    from pydantic import BaseModel, Field

    class _TopicSchema(BaseModel):
        title: str = Field(description="Punchy, search-friendly video title idea")
        angle: str = Field(description="The specific hook/spin for this video")
        why_now: str = Field(description="Why this is timely or viral right now")
        virality_score: float = Field(
            description="0-100 estimate of viral potential for a faceless Short"
        )
        keywords: List[str] = Field(default_factory=list)
        sources: List[str] = Field(default_factory=list)

    class _TopicList(BaseModel):
        topics: List[_TopicSchema]

    _SCHEMA_OK = True
except ImportError:  # pragma: no cover
    _SCHEMA_OK = False


_EVERGREEN: List[dict] = [
    {
        "title": "The World Cup Goal That Broke the Internet",
        "angle": "Break down a single iconic World Cup goal frame-by-frame and why it went viral.",
        "why_now": "Evergreen nostalgia that reliably performs around tournament season.",
        "virality_score": 78,
        "keywords": ["world cup", "iconic goal", "football history"],
    },
    {
        "title": "5 World Cup Dark Horses Nobody Is Talking About",
        "angle": "Rapid-fire profiles of underdog nations who could shock the favorites.",
        "why_now": "Prediction/list content spikes in the build-up to every tournament.",
        "virality_score": 74,
        "keywords": ["world cup dark horses", "underdogs", "predictions"],
    },
    {
        "title": "Why This Free Kick Should Be Illegal",
        "angle": "Dissect a physics-defying free kick and the technique behind it.",
        "why_now": "Skill-breakdown shorts have huge save/share rates.",
        "virality_score": 71,
        "keywords": ["free kick", "football skills", "technique"],
    },
    {
        "title": "The Transfer Nobody Saw Coming",
        "angle": "Tell the story of a shock transfer and the chaos it caused.",
        "why_now": "Transfer drama is a permanent engagement engine in football.",
        "virality_score": 69,
        "keywords": ["transfer news", "football", "shock move"],
    },
    {
        "title": "The Greatest Comeback in Football History",
        "angle": "Re-tell a legendary comeback minute-by-minute with rising tension.",
        "why_now": "Underdog/comeback narratives are endlessly re-watchable.",
        "virality_score": 76,
        "keywords": ["comeback", "football history", "champions league"],
    },
]


class TrendScout:
    def __init__(self, config: Config, llm: LLMClient):
        self.config = config
        self.llm = llm

    def discover(self, count: int = 5) -> List[Topic]:
        if self.llm.available and _SCHEMA_OK:
            try:
                return self._discover_with_claude(count)
            except Exception as exc:  # pragma: no cover - network/SDK variance
                log.warning("Claude trend discovery failed (%s); using fallback.", exc)
        return self._discover_offline(count)

    # ------------------------------------------------------------------ #
    def _discover_with_claude(self, count: int) -> List[Topic]:
        channel = self.config.channel
        banned = ", ".join(channel.get("banned_topics", [])) or "none"

        system = (
            "You are the editorial strategist for a faceless YouTube channel about "
            f"{channel['niche']}. You find the highest-potential viral video ideas. "
            "You understand YouTube Shorts/TikTok virality: a strong hook, emotional "
            "stakes, and shareability matter more than raw news value."
        )
        user = (
            f"Find the {count} best video ideas to publish in the next 48 hours for "
            f"audience: {channel['audience']}.\n\n"
            "Search the web for what's currently going viral in football: standout "
            "matches, wonder goals, transfer drama, World Cup storylines, and trending "
            "debates. Then return the strongest, most shareable angles.\n\n"
            f"Avoid these topics: {banned}.\n"
            "Rank by viral potential for a faceless narrated Short. Include real "
            "source URLs you found."
        )

        # First gather research with web search, then coerce to a strict schema.
        research = self.llm.web_research(system, user)
        structurer_system = (
            "Convert the research notes into a strict ranked list of video topics. "
            "Keep titles punchy and under 70 characters."
        )
        topic_list = self.llm.parse(
            structurer_system,
            f"Research notes:\n\n{research}\n\nReturn the top {count} as structured data.",
            _TopicList,
        )
        topics = [
            Topic(
                title=t.title,
                angle=t.angle,
                why_now=t.why_now,
                virality_score=float(t.virality_score),
                keywords=list(t.keywords),
                sources=list(t.sources),
            )
            for t in topic_list.topics
        ]
        topics.sort(key=lambda t: t.virality_score, reverse=True)
        log.info("Discovered %d topics via Claude web research.", len(topics))
        return topics[:count]

    def _discover_offline(self, count: int) -> List[Topic]:
        topics = [
            Topic(
                title=item["title"],
                angle=item["angle"],
                why_now=item["why_now"],
                virality_score=float(item["virality_score"]),
                keywords=list(item.get("keywords", [])),
                sources=["offline-evergreen"],
            )
            for item in _EVERGREEN
        ]
        topics.sort(key=lambda t: t.virality_score, reverse=True)
        log.info("Using %d offline evergreen topics.", min(count, len(topics)))
        return topics[:count]
