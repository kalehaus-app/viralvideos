import shutil
import subprocess

import pytest

from viralagent.config import load_config
from viralagent.agents.footage import Footage
from viralagent.models import Scene, Script, Topic
from viralagent.pipeline import Pipeline


def _script() -> Script:
    topic = Topic(title="World Cup Dark Horses", angle="underdogs to watch")
    return Script(
        topic=topic,
        hook="These teams will shock everyone.",
        scenes=[Scene(narration="Beat one.", visual="v", seconds=2.0),
                Scene(narration="Beat two.", visual="v", seconds=2.0)],
        call_to_action="Follow for more.",
        estimated_seconds=6.0,
    )


def test_folder_backend_lists_clips(tmp_path):
    clips = tmp_path / "clips"
    clips.mkdir()
    (clips / "a.mp4").write_bytes(b"x")
    (clips / "b.mov").write_bytes(b"x")
    (clips / "notes.txt").write_text("ignore me")

    cfg = load_config("does-not-exist.yaml")
    cfg.data["paths"]["clips_dir"] = str(clips)
    cfg.data["providers"]["footage"] = "folder"

    found = Footage(cfg, dry_run=True).gather(_script(), tmp_path)
    assert len(found) == 2  # only the video files
    assert all(f.endswith((".mp4", ".mov")) for f in found)


def test_footage_none_returns_empty(tmp_path):
    cfg = load_config("does-not-exist.yaml")
    cfg.data["providers"]["footage"] = "none"
    assert Footage(cfg, dry_run=True).gather(_script(), tmp_path) == []


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
def test_pipeline_renders_from_real_clips(tmp_path):
    # Generate a tiny real video clip to act as "footage".
    clips = tmp_path / "clips"
    clips.mkdir()
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-pix_fmt", "yuv420p", str(clips / "clip.mp4")],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    cfg = load_config("does-not-exist.yaml")
    cfg.data["paths"]["output_dir"] = str(tmp_path / "output")
    cfg.data["paths"]["state_file"] = str(tmp_path / "state.json")
    cfg.data["paths"]["clips_dir"] = str(clips)
    cfg.data["providers"]["footage"] = "folder"

    pipe = Pipeline(cfg, dry_run=True, no_upload=True)
    bundle = pipe.run_once(topics_count=3)

    assert bundle is not None
    assert bundle.video_path is not None
    assert (bundle.directory / "video.mp4").exists()
    # The edit used real footage, not generated cards.
    assert any("footage:" in n for n in bundle.notes)
