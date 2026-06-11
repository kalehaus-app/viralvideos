"""Command-line interface for ViralAgent.

    python -m viralagent run-once [--dry-run] [--format short|long] [--count N] [--no-upload]
    python -m viralagent daemon   [--dry-run] [--no-upload] [--max-cycles N]
    python -m viralagent scout    [--count N]
    python -m viralagent script   "<topic title>" [--dry-run]
    python -m viralagent package  <slug>
    python -m viralagent publish  <slug> [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .config import Config, load_config
from .models import Metadata, Scene, Script, Topic
from .pipeline import Pipeline
from .scheduler import Scheduler
from .utils import get_logger

log = get_logger("viralagent.cli")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="viralagent",
        description="Autonomous faceless YouTube channel for viral soccer content.",
    )
    p.add_argument("--config", help="Path to config.yaml", default=None)
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run-once", help="Run a single end-to-end cycle")
    _common_flags(run)
    run.add_argument("--count", type=int, default=None, help="Topics to consider")

    daemon = sub.add_parser("daemon", help="Run autonomously on a schedule")
    _common_flags(daemon)
    daemon.add_argument("--max-cycles", type=int, default=None)

    scout = sub.add_parser("scout", help="Discover & print trending topics")
    scout.add_argument("--count", type=int, default=5)
    scout.add_argument("--dry-run", action="store_true")

    script = sub.add_parser("script", help="Write a script for a specific topic")
    script.add_argument("topic", help="Topic title")
    script.add_argument("--dry-run", action="store_true")

    package = sub.add_parser("package", help="(Re)generate metadata + thumbnail")
    package.add_argument("slug", help="Bundle slug under output/")
    package.add_argument("--dry-run", action="store_true")

    publish = sub.add_parser("publish", help="Upload an existing bundle")
    publish.add_argument("slug", help="Bundle slug under output/")
    publish.add_argument("--dry-run", action="store_true")
    return p


def _common_flags(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--dry-run", action="store_true", help="No network/uploads")
    sp.add_argument("--no-upload", action="store_true", help="Render but don't publish")
    sp.add_argument(
        "--format", choices=["short", "long"], default=None, help="Override content format"
    )


def _apply_overrides(config: Config, args: argparse.Namespace) -> None:
    if getattr(args, "format", None):
        config.content["format"] = args.format


# --------------------------------------------------------------------------- #
# Command handlers
# --------------------------------------------------------------------------- #
def cmd_run_once(config: Config, args) -> int:
    _apply_overrides(config, args)
    pipe = Pipeline(config, dry_run=args.dry_run, no_upload=args.no_upload)
    bundle = pipe.run_once(topics_count=args.count)
    if bundle is None:
        return 1
    print(f"\n✅ Done → {bundle.directory}")
    if bundle.video_path:
        print(f"   video: {bundle.video_path}")
    if bundle.youtube_id:
        print(f"   youtube: https://youtu.be/{bundle.youtube_id}")
    return 0


def cmd_daemon(config: Config, args) -> int:
    _apply_overrides(config, args)
    sched = Scheduler(config, dry_run=args.dry_run, no_upload=args.no_upload)
    try:
        sched.run_forever(max_cycles=args.max_cycles)
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


def cmd_scout(config: Config, args) -> int:
    from .llm import LLMClient
    from .agents.trend_scout import TrendScout

    llm = LLMClient(config, dry_run=args.dry_run)
    topics = TrendScout(config, llm).discover(args.count)
    print(f"\nTop {len(topics)} topics:\n")
    for i, t in enumerate(topics, 1):
        print(f"{i}. [{t.virality_score:4.0f}] {t.title}")
        print(f"     angle: {t.angle}")
        if t.why_now:
            print(f"     why now: {t.why_now}")
        print()
    return 0


def cmd_script(config: Config, args) -> int:
    from .llm import LLMClient
    from .agents.scriptwriter import ScriptWriter

    topic = Topic(title=args.topic, angle=args.topic)
    llm = LLMClient(config, dry_run=args.dry_run)
    script = ScriptWriter(config, llm).write(topic)
    print(f"\nHOOK: {script.hook}\n")
    for i, s in enumerate(script.scenes, 1):
        print(f"[{i}] {s.narration}")
    print(f"\nCTA: {script.call_to_action}")
    print(f"~{script.estimated_seconds:.0f}s")
    return 0


def cmd_package(config: Config, args) -> int:
    from .llm import LLMClient
    from .agents.packager import Packager

    out_dir = config.output_dir / args.slug
    script = _load_script(out_dir)
    if script is None:
        log.error("No script.json found in %s", out_dir)
        return 1
    llm = LLMClient(config, dry_run=args.dry_run)
    meta = Packager(config, llm, dry_run=args.dry_run).package(script, out_dir)
    (out_dir / "metadata.json").write_text(
        json.dumps(asdict(meta), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"✅ Metadata written → {out_dir / 'metadata.json'}")
    print(f"   title: {meta.title}")
    return 0


def cmd_publish(config: Config, args) -> int:
    from .agents.publisher import Publisher

    out_dir = config.output_dir / args.slug
    meta = _load_metadata(out_dir)
    if meta is None:
        log.error("No metadata.json found in %s", out_dir)
        return 1
    video = out_dir / "video.mp4"
    youtube_id = Publisher(config, dry_run=args.dry_run).publish(
        str(video) if video.exists() else None, meta, out_dir
    )
    if youtube_id:
        print(f"✅ Published → https://youtu.be/{youtube_id}")
    else:
        print(f"📝 Dry-run manifest written in {out_dir}")
    return 0


# --------------------------------------------------------------------------- #
def _load_script(out_dir: Path) -> Optional[Script]:
    path = out_dir / "script.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    topic = Topic(**data["topic"])
    scenes = [Scene(**s) for s in data.get("scenes", [])]
    return Script(
        topic=topic,
        hook=data["hook"],
        scenes=scenes,
        call_to_action=data.get("call_to_action", ""),
        estimated_seconds=data.get("estimated_seconds", 0.0),
    )


def _load_metadata(out_dir: Path) -> Optional[Metadata]:
    path = out_dir / "metadata.json"
    if not path.exists():
        return None
    return Metadata(**json.loads(path.read_text(encoding="utf-8")))


_HANDLERS = {
    "run-once": cmd_run_once,
    "daemon": cmd_daemon,
    "scout": cmd_scout,
    "script": cmd_script,
    "package": cmd_package,
    "publish": cmd_publish,
}


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)
    handler = _HANDLERS[args.command]
    return handler(config, args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
