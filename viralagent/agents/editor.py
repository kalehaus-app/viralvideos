"""Editor — assembles scene assets + voiceover + captions into a final MP4.

Builds an SRT caption track timed to the narration, then uses ffmpeg's concat
demuxer to show each scene card for its share of the runtime, burns in the
captions, and muxes the voiceover. Scene durations are scaled so the rendered
video length matches the actual voiceover length.

Requires ffmpeg on PATH for real rendering. Without it, the editor records the
edit plan to disk so the bundle is still complete and reproducible.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional

from ..config import Config
from ..models import Script
from ..utils import format_timestamp, get_logger, have_ffmpeg


class EditResult:
    def __init__(self, video_path: Optional[str], captions_path: Optional[str]):
        self.video_path = video_path
        self.captions_path = captions_path


log = get_logger("viralagent.editor")


class Editor:
    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def assemble(
        self,
        script: Script,
        scene_assets: List[str],
        voiceover_path: Optional[str],
        voiceover_seconds: float,
        out_dir: Path,
        footage_clips: Optional[List[str]] = None,
    ) -> EditResult:
        out_dir.mkdir(parents=True, exist_ok=True)

        # Segments: [hook] + each scene, paired with their caption text + base secs.
        segments = self._build_segments(script)
        total_base = sum(d for _, d in segments) or 1.0
        target_total = voiceover_seconds if voiceover_seconds > 0 else total_base
        scale = target_total / total_base
        durations = [max(d * scale, 0.8) for _, d in segments]
        captions = [c for c, _ in segments]

        captions_path = self._write_srt(captions, durations, out_dir)

        # Preferred path: cut real video clips (your folder / Pexels) to the
        # narration, with captions burned in and the AI voiceover on top.
        if footage_clips and have_ffmpeg():
            video_path = self._render_from_clips(
                footage_clips, captions, durations, voiceover_path,
                captions_path.name, out_dir,
            )
            if video_path:
                return EditResult(str(video_path), str(captions_path))
            log.warning("Clip render failed; falling back to generated cards.")

        # Fallback: generated motion-graphic cards (visuals stage).
        image_assets = [a for a in scene_assets if a.lower().endswith((".png", ".jpg"))]
        if not image_assets or not have_ffmpeg():
            reason = "no image assets" if not image_assets else "ffmpeg unavailable"
            log.warning("Skipping render (%s); wrote edit plan + captions.", reason)
            self._write_plan(segments, durations, out_dir)
            return EditResult(video_path=None, captions_path=str(captions_path))

        video_path = self._render(
            image_assets, durations, voiceover_path, captions_path.name, out_dir
        )
        return EditResult(
            video_path=str(video_path) if video_path else None,
            captions_path=str(captions_path),
        )

    # ------------------------------------------------------------------ #
    def _build_segments(self, script: Script) -> List[tuple[str, float]]:
        wpm = self.config.content["words_per_minute"]
        from ..utils import estimate_seconds

        segs: List[tuple[str, float]] = [
            (script.hook, max(estimate_seconds(script.hook, wpm), 1.2))
        ]
        for scene in script.scenes:
            secs = scene.seconds or estimate_seconds(scene.narration, wpm)
            segs.append((scene.narration, max(secs, 1.0)))
        if script.call_to_action:
            segs.append(
                (script.call_to_action, max(estimate_seconds(script.call_to_action, wpm), 1.0))
            )
        return segs

    def _write_srt(
        self, captions: List[str], durations: List[float], out_dir: Path
    ) -> Path:
        lines: List[str] = []
        t = 0.0
        for i, (text, dur) in enumerate(zip(captions, durations), start=1):
            start, end = t, t + dur
            lines.append(str(i))
            lines.append(f"{format_timestamp(start)} --> {format_timestamp(end)}")
            lines.append(_wrap(text))
            lines.append("")
            t = end
        path = out_dir / "captions.srt"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    def _dimensions(self) -> tuple[int, int]:
        if self.config.content.get("format") == "long":
            return 1920, 1080
        return 1080, 1920

    def _render_from_clips(
        self,
        clips: List[str],
        captions: List[str],
        durations: List[float],
        voiceover_path: Optional[str],
        captions_name: str,
        out_dir: Path,
    ) -> Optional[Path]:
        """Cut real video clips to the narration timing, one clip per caption beat.

        Each beat is filled by the next clip in the rotation (looped if the clip
        is shorter than the beat), normalized to the channel's frame size. Beats
        are concatenated, captions burned in, and the AI voiceover laid on top —
        the clips' own audio is dropped.
        """
        w, h = self._dimensions()
        seg_dir = out_dir / "footage"
        seg_dir.mkdir(parents=True, exist_ok=True)

        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},setsar=1,fps=30,format=yuv420p"
        )
        seg_files: List[str] = []
        for i, dur in enumerate(durations):
            clip = clips[i % len(clips)]
            seg_rel = f"footage/seg_{i:02d}.mp4"
            cmd = [
                "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(Path(clip).resolve()),
                "-t", f"{max(dur, 0.5):.3f}", "-an", "-vf", vf,
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                seg_rel,
            ]
            try:
                subprocess.run(
                    cmd, cwd=str(out_dir), check=True,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                seg_files.append(seg_rel)
            except subprocess.CalledProcessError as exc:  # pragma: no cover
                log.warning("Clip segment %d failed: %s", i, _tail(exc.stderr))

        if not seg_files:
            return None

        # Concatenate normalized segments (all share codec/params → stream copy).
        concat = "\n".join(f"file '{s}'" for s in seg_files)
        (out_dir / "montage.txt").write_text(concat, encoding="utf-8")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "montage.txt",
                 "-c", "copy", "montage.mp4"],
                cwd=str(out_dir), check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            log.error("Montage concat failed: %s", _tail(exc.stderr))
            return None

        # Burn captions + mux the voiceover.
        cmd = ["ffmpeg", "-y", "-i", "montage.mp4"]
        if voiceover_path:
            cmd += ["-i", str(Path(voiceover_path).name)]
        cmd += ["-vf", f"subtitles={captions_name},format=yuv420p",
                "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if voiceover_path:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["video.mp4"]
        try:
            subprocess.run(
                cmd, cwd=str(out_dir), check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            log.error("Final clip render failed: %s", _tail(exc.stderr))
            return None
        log.info("Rendered video.mp4 from %d real clip beats.", len(seg_files))
        return out_dir / "video.mp4"

    def _render(
        self,
        images: List[str],
        durations: List[float],
        voiceover_path: Optional[str],
        captions_name: str,
        out_dir: Path,
    ) -> Optional[Path]:
        # Align caption count to image count (captions may include a CTA segment).
        n = len(images)
        durs = durations[:n]
        if len(durs) < n:
            durs += [durations[-1] if durations else 2.0] * (n - len(durs))

        # ffmpeg concat demuxer list (paths relative to out_dir for portability).
        concat_lines: List[str] = []
        for img, dur in zip(images, durs):
            rel = str(Path(img).relative_to(out_dir)) if _is_relative(img, out_dir) else img
            concat_lines.append(f"file '{rel}'")
            concat_lines.append(f"duration {dur:.3f}")
        # The concat demuxer needs the last file repeated with no duration.
        last_rel = str(Path(images[-1]).relative_to(out_dir)) if _is_relative(images[-1], out_dir) else images[-1]
        concat_lines.append(f"file '{last_rel}'")
        (out_dir / "concat.txt").write_text("\n".join(concat_lines), encoding="utf-8")

        vf = f"subtitles={captions_name},format=yuv420p"
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat.txt",
        ]
        if voiceover_path:
            cmd += ["-i", str(Path(voiceover_path).name)]
        cmd += ["-vf", vf, "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p"]
        if voiceover_path:
            cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["video.mp4"]

        try:
            subprocess.run(
                cmd, cwd=str(out_dir), check=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            log.error("ffmpeg render failed: %s", exc.stderr[-500:] if exc.stderr else exc)
            return None
        log.info("Rendered video.mp4 (%d segments).", n)
        return out_dir / "video.mp4"

    def _write_plan(
        self, segments: List[tuple[str, float]], durations: List[float], out_dir: Path
    ) -> None:
        lines = ["EDIT PLAN (render skipped)", ""]
        for i, ((text, _), dur) in enumerate(zip(segments, durations)):
            lines.append(f"[{i:02d}] {dur:5.1f}s  {text}")
        (out_dir / "edit_plan.txt").write_text("\n".join(lines), encoding="utf-8")


def _wrap(text: str, width: int = 42) -> str:
    words = text.split()
    out, line = [], ""
    for w in words:
        if len(line) + len(w) + 1 > width:
            out.append(line)
            line = w
        else:
            line = f"{line} {w}".strip()
    if line:
        out.append(line)
    return "\n".join(out[:2])  # keep captions to 2 lines for legibility


def _is_relative(path: str, base: Path) -> bool:
    try:
        Path(path).relative_to(base)
        return True
    except ValueError:
        return False


def _tail(text: Optional[str], n: int = 400) -> str:
    return (text or "")[-n:]
