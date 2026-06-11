"""Pipeline — wires the agents into one end-to-end content cycle.

A cycle is: scout -> pick an unused topic -> script -> voiceover -> visuals ->
edit -> package -> publish, writing every artifact into ``output/<slug>/``.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .agents.editor import Editor
from .agents.packager import Packager
from .agents.publisher import Publisher
from .agents.scriptwriter import ScriptWriter
from .agents.trend_scout import TrendScout
from .agents.visuals import Visuals
from .agents.voiceover import Voiceover
from .config import Config
from .llm import LLMClient
from .models import Script, Topic, VideoBundle
from .state import StateStore
from .utils import get_logger

log = get_logger("viralagent.pipeline")


class Pipeline:
    def __init__(self, config: Config, *, dry_run: bool = False, no_upload: bool = False):
        self.config = config
        self.dry_run = dry_run
        self.no_upload = no_upload

        self.llm = LLMClient(config, dry_run=dry_run)
        self.state = StateStore(config.state_file)

        self.scout = TrendScout(config, self.llm)
        self.writer = ScriptWriter(config, self.llm)
        self.voice = Voiceover(config, dry_run=dry_run)
        self.visuals_agent = Visuals(config, dry_run=dry_run)
        self.editor = Editor(config, dry_run=dry_run)
        self.packager = Packager(config, self.llm, dry_run=dry_run)
        self.publisher = Publisher(config, dry_run=dry_run)

    # ------------------------------------------------------------------ #
    def run_once(self, *, topics_count: Optional[int] = None) -> Optional[VideoBundle]:
        count = topics_count or self.config.content.get("topics_per_cycle", 5)
        topics = self.scout.discover(count)
        topic = self._pick_unused(topics)
        if topic is None:
            log.warning("No fresh topics available this cycle.")
            return None
        log.info("Selected topic: %s (score %.0f)", topic.title, topic.virality_score)
        return self.produce(topic)

    def produce(self, topic: Topic) -> VideoBundle:
        """Run all production stages for a chosen topic and return the bundle."""
        out_dir = self.config.output_dir / topic.slug
        bundle = VideoBundle(directory=out_dir, topic=topic)
        out_dir.mkdir(parents=True, exist_ok=True)
        bundle.write_json("plan.json", topic)

        # 1. Script
        script = self.writer.write(topic)
        bundle.script = script
        self._persist_script(bundle, script)

        # 2. Voiceover
        voice = self.voice.synthesize(script, out_dir)
        bundle.voiceover_path = voice.path
        bundle.log(f"voiceover: {voice.backend}")

        # 3. Visuals
        bundle.scene_assets = self.visuals_agent.generate(script, out_dir)

        # 4. Edit (captions + render)
        edit = self.editor.assemble(
            script, bundle.scene_assets, voice.path, voice.duration, out_dir
        )
        bundle.video_path = edit.video_path
        bundle.captions_path = edit.captions_path

        # 5. Package (metadata + thumbnail)
        bundle.metadata = self.packager.package(script, out_dir)
        bundle.write_json("metadata.json", bundle.metadata)

        # 6. Publish
        if not self.no_upload:
            youtube_id = self.publisher.publish(bundle.video_path, bundle.metadata, out_dir)
            bundle.youtube_id = youtube_id
            if youtube_id:
                self.state.record_published(bundle.slug, youtube_id)
        else:
            log.info("Upload skipped (--no-upload).")

        # 7. Record + manifest
        self.state.record_produced(bundle.slug, topic.title)
        bundle.save_manifest()
        log.info("Cycle complete → %s", out_dir)
        return bundle

    # ------------------------------------------------------------------ #
    def _pick_unused(self, topics) -> Optional[Topic]:
        for topic in topics:
            if not self.state.is_recent(topic.slug):
                return topic
        # All seen — allow the top topic anyway rather than stalling forever.
        return topics[0] if topics else None

    def _persist_script(self, bundle: VideoBundle, script: Script) -> None:
        bundle.write_json("script.json", script)
        lines = [f"HOOK: {script.hook}", ""]
        for i, scene in enumerate(script.scenes, 1):
            lines.append(f"[{i}] {scene.narration}")
            lines.append(f"     visual: {scene.visual}")
            if scene.on_screen_text:
                lines.append(f"     caption: {scene.on_screen_text}")
            lines.append("")
        lines.append(f"CTA: {script.call_to_action}")
        lines.append(f"\n~{script.estimated_seconds:.0f}s")
        (bundle.directory / "script.txt").write_text("\n".join(lines), encoding="utf-8")
