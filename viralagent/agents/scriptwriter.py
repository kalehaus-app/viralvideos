"""ScriptWriter — turns a Topic into a scene-by-scene, retention-optimized script.

Real mode: Claude writes the hook + beats + CTA, sized to the target runtime and
on-brand for the channel persona, returned as structured data.

Offline mode: a deterministic template that still produces a usable, well-timed
script so the rest of the pipeline can run.
"""

from __future__ import annotations

from typing import List

from ..config import Config
from ..llm import LLMClient
from ..models import Scene, Script, Topic
from ..utils import estimate_seconds, get_logger

log = get_logger("viralagent.script")

try:
    from pydantic import BaseModel, Field

    class _SceneSchema(BaseModel):
        narration: str = Field(description="One spoken line/beat of narration")
        visual: str = Field(description="Concrete visual direction for this beat")
        on_screen_text: str = Field(
            default="", description="Short caption/keyword to burn on screen"
        )

    class _ScriptSchema(BaseModel):
        hook: str = Field(description="First 1-2 seconds; must stop the scroll")
        scenes: List[_SceneSchema]
        call_to_action: str = Field(description="Closing CTA (subscribe/comment)")

    _SCHEMA_OK = True
except ImportError:  # pragma: no cover
    _SCHEMA_OK = False


class ScriptWriter:
    def __init__(self, config: Config, llm: LLMClient):
        self.config = config
        self.llm = llm

    def write(self, topic: Topic) -> Script:
        if self.llm.available and _SCHEMA_OK:
            try:
                return self._write_with_claude(topic)
            except Exception as exc:  # pragma: no cover
                log.warning("Claude scriptwriting failed (%s); using template.", exc)
        return self._write_offline(topic)

    # ------------------------------------------------------------------ #
    def _write_with_claude(self, topic: Topic) -> Script:
        channel = self.config.channel
        content = self.config.content
        target = content["target_seconds"]
        wpm = content["words_per_minute"]
        fmt = content["format"]
        word_budget = int(target / 60 * wpm)

        style = content.get("style", "story")
        style_note = (
            "Write as ANALYSIS/COMMENTARY: make a sharp argument or insight about the "
            "moment, back it with specifics, and let the narration carry the video over "
            "footage. Each visual direction should describe the soccer footage that "
            "would play under that line."
            if style == "commentary"
            else "Write as STORYTELLING: build narrative tension beat by beat."
        )
        system = (
            f"You are the scriptwriter and narrator persona for '{channel['name']}', "
            f"a faceless YouTube channel about {channel['niche']}.\n"
            f"Persona: {channel['persona']}\n"
            f"Tone: {channel['tone']}\n"
            f"Audience: {channel['audience']}\n"
            f"{style_note}\n"
            "Write tight, high-retention narration. Open with a pattern-breaking hook, "
            "escalate stakes every beat, and never waste a word. Be factually careful: "
            "do not invent specific scores, dates, or quotes you are unsure about."
        )
        user = (
            f"Write a {fmt} video script (~{target} seconds, ~{word_budget} words total).\n\n"
            f"TITLE: {topic.title}\n"
            f"ANGLE: {topic.angle}\n"
            f"WHY NOW: {topic.why_now}\n\n"
            "Return a hook, a sequence of scenes (each = one narration beat + a "
            "concrete visual direction + an optional 2-4 word on-screen caption), and a "
            "closing call to action. Aim for 5-9 scenes."
        )
        parsed = self.llm.parse(system, user, _ScriptSchema, max_tokens=4000)

        scenes = [
            Scene(
                narration=s.narration.strip(),
                visual=s.visual.strip(),
                on_screen_text=s.on_screen_text.strip(),
                seconds=estimate_seconds(s.narration, wpm),
            )
            for s in parsed.scenes
        ]
        script = Script(
            topic=topic,
            hook=parsed.hook.strip(),
            scenes=scenes,
            call_to_action=parsed.call_to_action.strip(),
        )
        script.estimated_seconds = round(
            estimate_seconds(script.full_narration, wpm), 2
        )
        log.info("Wrote script: %d scenes, ~%.0fs.", len(scenes), script.estimated_seconds)
        return script

    def _write_offline(self, topic: Topic) -> Script:
        wpm = self.config.content["words_per_minute"]
        beats = [
            (
                f"Here's what everyone missed about {topic.title.lower()}.",
                f"Bold title card: {topic.title}",
                "WAIT FOR IT",
            ),
            (
                f"{topic.angle}",
                "Archival-style highlight montage with motion blur",
                "THE SETUP",
            ),
            (
                "The numbers don't lie — and they tell a story most fans never noticed.",
                "Animated stat overlay counting up",
                "THE STATS",
            ),
            (
                "But the real twist? It changed how the game was played.",
                "Slow zoom on a defining moment",
                "THE TWIST",
            ),
            (
                "And that's why this moment still goes viral years later.",
                "Crowd-reaction collage, rising energy",
                "WHY IT MATTERS",
            ),
        ]
        scenes = [
            Scene(
                narration=n,
                visual=v,
                on_screen_text=t,
                seconds=estimate_seconds(n, wpm),
            )
            for (n, v, t) in beats
        ]
        script = Script(
            topic=topic,
            hook=f"{topic.title}? You have NO idea.",
            scenes=scenes,
            call_to_action="Follow for the football stories nobody else tells.",
        )
        script.estimated_seconds = round(
            estimate_seconds(script.full_narration, wpm), 2
        )
        log.info("Wrote offline template script (~%.0fs).", script.estimated_seconds)
        return script
