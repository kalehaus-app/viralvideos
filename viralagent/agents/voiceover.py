"""Voiceover — synthesizes narration audio with a pluggable TTS backend.

Backend resolution (``providers.voiceover``):
    auto        -> first available of elevenlabs, openai, system, silent
    elevenlabs  -> ElevenLabs HTTP API (needs ELEVENLABS_API_KEY)
    openai      -> OpenAI TTS HTTP API (needs OPENAI_API_KEY)
    system      -> offline OS TTS (macOS `say` / Linux `espeak-ng`)
    silent      -> a silent track sized to the script (always works w/ ffmpeg)

Every backend returns a path to a single audio file plus its measured duration so
the editor can sync visuals and captions. Failures fall back down the chain.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..config import Config
from ..models import Script
from ..utils import get_logger, have_ffmpeg, run

log = get_logger("viralagent.voice")


@dataclass
class VoiceResult:
    path: Optional[str]
    duration: float
    backend: str


class Voiceover:
    def __init__(self, config: Config, *, dry_run: bool = False):
        self.config = config
        self.dry_run = dry_run

    def synthesize(self, script: Script, out_dir: Path) -> VoiceResult:
        out_dir.mkdir(parents=True, exist_ok=True)
        text = script.full_narration
        duration = max(script.estimated_seconds, 1.0)
        choice = self.config.providers.get("voiceover", "auto")
        chain = self._resolve_chain(choice)

        for backend in chain:
            try:
                result = self._run_backend(backend, text, duration, out_dir)
                if result is not None:
                    log.info("Voiceover via '%s' (%.1fs).", backend, result.duration)
                    return result
            except Exception as exc:  # pragma: no cover - backend variance
                log.warning("Voiceover backend '%s' failed: %s", backend, exc)

        log.warning("No voiceover backend succeeded; continuing without audio.")
        return VoiceResult(path=None, duration=duration, backend="none")

    # ------------------------------------------------------------------ #
    def _resolve_chain(self, choice: str) -> list[str]:
        if choice != "auto":
            return [choice, "silent"]
        chain = []
        if self.config.secrets.elevenlabs_api_key:
            chain.append("elevenlabs")
        if self.config.secrets.openai_api_key:
            chain.append("openai")
        if shutil.which("say") or shutil.which("espeak-ng") or shutil.which("espeak"):
            chain.append("system")
        chain.append("silent")
        return chain

    def _run_backend(
        self, backend: str, text: str, duration: float, out_dir: Path
    ) -> Optional[VoiceResult]:
        if self.dry_run and backend != "silent":
            # Don't make network/TTS calls in dry-run; jump to the silent track.
            return None
        if backend == "elevenlabs":
            return self._elevenlabs(text, out_dir)
        if backend == "openai":
            return self._openai(text, out_dir)
        if backend == "system":
            return self._system(text, out_dir)
        if backend == "silent":
            return self._silent(duration, out_dir)
        raise ValueError(f"Unknown voiceover backend: {backend}")

    # -- backends -------------------------------------------------------------
    def _elevenlabs(self, text: str, out_dir: Path) -> VoiceResult:
        import requests  # lazy

        key = self.config.secrets.elevenlabs_api_key
        voice = self.config.secrets.elevenlabs_voice_id or "21m00Tcm4TlvDq8ikWAM"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
        resp = requests.post(
            url,
            headers={"xi-api-key": key, "accept": "audio/mpeg"},
            json={"text": text, "model_id": "eleven_turbo_v2_5"},
            timeout=120,
        )
        resp.raise_for_status()
        mp3 = out_dir / "voiceover.mp3"
        mp3.write_bytes(resp.content)
        return self._finalize(mp3, out_dir, "elevenlabs")

    def _openai(self, text: str, out_dir: Path) -> VoiceResult:
        import requests  # lazy

        key = self.config.secrets.openai_api_key
        resp = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}"},
            json={
                "model": "gpt-4o-mini-tts",
                "voice": "onyx",
                "input": text,
                "response_format": "mp3",
            },
            timeout=120,
        )
        resp.raise_for_status()
        mp3 = out_dir / "voiceover.mp3"
        mp3.write_bytes(resp.content)
        return self._finalize(mp3, out_dir, "openai")

    def _system(self, text: str, out_dir: Path) -> VoiceResult:
        wav = out_dir / "voiceover.wav"
        if shutil.which("espeak-ng") or shutil.which("espeak"):
            espeak = shutil.which("espeak-ng") or shutil.which("espeak")
            run([espeak, "-w", str(wav), text])
            return self._finalize(wav, out_dir, "system")
        if shutil.which("say"):
            aiff = out_dir / "voiceover.aiff"
            run(["say", "-o", str(aiff), text])
            return self._finalize(aiff, out_dir, "system")
        raise RuntimeError("No system TTS binary found")

    def _silent(self, duration: float, out_dir: Path) -> VoiceResult:
        if not have_ffmpeg():
            return VoiceResult(path=None, duration=duration, backend="silent")
        wav = out_dir / "voiceover.wav"
        run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t", f"{duration:.2f}", str(wav),
            ]
        )
        return VoiceResult(path=str(wav), duration=duration, backend="silent")

    # -- helpers --------------------------------------------------------------
    def _finalize(self, src: Path, out_dir: Path, backend: str) -> VoiceResult:
        """Normalize to voiceover.wav and measure duration via ffprobe/ffmpeg."""
        wav = out_dir / "voiceover.wav"
        if have_ffmpeg() and src.suffix != ".wav":
            run(["ffmpeg", "-y", "-i", str(src), str(wav)])
        elif src != wav:
            shutil.copyfile(src, wav)
        duration = self._probe_duration(wav)
        return VoiceResult(path=str(wav), duration=duration, backend=backend)

    @staticmethod
    def _probe_duration(path: Path) -> float:
        if shutil.which("ffprobe"):
            try:
                proc = run(
                    [
                        "ffprobe", "-v", "error", "-show_entries",
                        "format=duration", "-of",
                        "default=noprint_wrappers=1:nokey=1", str(path),
                    ]
                )
                return round(float(proc.stdout.strip()), 2)
            except Exception:  # pragma: no cover
                pass
        return 0.0
