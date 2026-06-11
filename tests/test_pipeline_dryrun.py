import json

from viralagent.config import load_config
from viralagent.pipeline import Pipeline


def test_full_cycle_dry_run(tmp_path, monkeypatch):
    # Isolate all filesystem output under tmp_path.
    cfg = load_config("does-not-exist.yaml")
    cfg.data["paths"]["output_dir"] = str(tmp_path / "output")
    cfg.data["paths"]["state_file"] = str(tmp_path / "state.json")

    pipe = Pipeline(cfg, dry_run=True, no_upload=False)
    bundle = pipe.run_once(topics_count=3)

    assert bundle is not None
    d = bundle.directory
    # Core artifacts always exist even with no ffmpeg / no API keys.
    assert (d / "plan.json").exists()
    assert (d / "script.json").exists()
    assert (d / "script.txt").exists()
    assert (d / "metadata.json").exists()
    assert (d / "captions.srt").exists()
    assert (d / "manifest.json").exists()
    # Dry-run never uploads; it leaves a publish manifest.
    assert (d / "publish_manifest.json").exists()

    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
    assert meta["title"]
    assert meta["visibility"] == "private"  # safety default

    # State tracked the produced slug for dedup.
    assert bundle.slug in pipe.state.seen_slugs()


def test_dedup_skips_recent(tmp_path):
    cfg = load_config("does-not-exist.yaml")
    cfg.data["paths"]["output_dir"] = str(tmp_path / "output")
    cfg.data["paths"]["state_file"] = str(tmp_path / "state.json")

    pipe = Pipeline(cfg, dry_run=True, no_upload=True)
    first = pipe.run_once(topics_count=5)
    second = pipe.run_once(topics_count=5)
    assert first is not None and second is not None
    # The second cycle should pick a different topic than the first.
    assert first.slug != second.slug
