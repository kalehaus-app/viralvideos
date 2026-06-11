# ⚽ ViralAgent — Autonomous Faceless Soccer/World Cup YouTube Channel

ViralAgent is an autonomous AI content engine that runs a **faceless YouTube channel**
dedicated to **viral soccer & World Cup content**. It discovers trending topics,
writes punchy scripts, generates voiceover and visuals, assembles a finished video,
writes SEO-optimized metadata + a thumbnail, and (optionally) uploads to YouTube —
on a schedule, with no human in the loop.

It is built on the **Claude API** (`claude-opus-4-8`) for the reasoning-heavy stages
(trend scouting, scriptwriting, packaging) and orchestrates the rest of the media
pipeline with ffmpeg and pluggable providers.

```
┌────────────┐  ┌─────────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐
│ TrendScout │─▶│ ScriptWriter│─▶│ Voiceover │─▶│ Visuals  │─▶│  Editor  │─▶│ Publisher │
│ (web+LLM)  │  │   (LLM)     │  │  (TTS)    │  │ (gen/ffm)│  │ (ffmpeg) │  │ (YouTube) │
└────────────┘  └─────────────┘  └───────────┘  └──────────┘  └──────────┘  └───────────┘
        └──────────────────────── Pipeline / Scheduler / State store ───────────────────┘
```

## Why "faceless"?

No on-camera talent. Every asset — narration, footage, captions, thumbnail, title —
is generated or sourced programmatically, so the channel can publish autonomously
around the clock.

## Quick start

```bash
# 1. Install (core deps only — the pipeline runs in dry-run with just these)
pip install -r requirements.txt

# 2. Configure (optional for dry-run)
cp .env.example .env            # add ANTHROPIC_API_KEY for real script generation
cp config.example.yaml config.yaml

# 3. Run one full cycle WITHOUT any API keys (offline templates + local assets)
python -m viralagent run-once --dry-run

# 4. Run one real cycle (needs ANTHROPIC_API_KEY; uploads only if YouTube is configured)
python -m viralagent run-once

# 5. Run autonomously forever (publishes on the configured cadence)
python -m viralagent daemon
```

Every run writes a self-contained bundle to `output/<slug>/`:

```
output/2026-world-cup-dark-horses/
├── plan.json          # topic + angle + hook + outline
├── script.json        # scene-by-scene script (hook, beats, CTA)
├── script.txt         # human-readable script
├── voiceover.wav      # narration (if TTS available)
├── scenes/            # generated/sourced visuals per scene
├── captions.srt       # burned-in subtitle source
├── video.mp4          # final rendered short/long-form video
├── thumbnail.png      # click-optimized thumbnail
└── metadata.json      # title, description, tags, category, publish settings
```

## Commands

| Command | Description |
|---|---|
| `run-once` | Run a single end-to-end cycle and exit |
| `daemon` | Run autonomously on the configured schedule |
| `scout` | Only discover & rank trending topics (prints the queue) |
| `script "<topic>"` | Generate a script for a specific topic |
| `package <slug>` | (Re)generate metadata + thumbnail for an existing bundle |
| `publish <slug>` | Upload an already-rendered bundle to YouTube |

Useful flags: `--dry-run` (no network/uploads), `--format short|long`, `--config <path>`,
`--count N` (topics to consider), `--no-upload`.

## Configuration

Configuration is layered: **defaults → `config.yaml` → environment variables**.
See `config.example.yaml` for every knob and `.env.example` for secrets.

Key settings:

- `channel.*` — niche, persona, tone, language, target audience
- `content.format` — `short` (≤60s vertical) or `long` (horizontal)
- `content.cadence_hours` — how often the daemon publishes
- `llm.model` — defaults to `claude-opus-4-8`
- `providers.*` — TTS / visuals / publish backends (with offline fallbacks)

## Provider backends (all optional, all degrade gracefully)

| Stage | Preferred | Fallback (no keys) |
|---|---|---|
| Trend discovery | Claude web search | Curated evergreen soccer angles |
| Scriptwriting | `claude-opus-4-8` | Deterministic template |
| Voiceover | ElevenLabs / OpenAI / `say`/`espeak` | Silent track sized to script |
| Visuals | Image-gen MCP / stock | ffmpeg text cards + Ken Burns |
| Video assembly | ffmpeg | (required for real video) |
| Publishing | YouTube Data API v3 | Dry-run manifest |

If a preferred backend isn't configured, ViralAgent logs it and uses the fallback so a
cycle always completes and always leaves an inspectable artifact bundle.

## Responsible automation

- Respects YouTube's policies: the publisher defaults to `private` visibility until you
  flip `publish.visibility` to `public`, so nothing goes live by accident.
- Only uses footage you have rights to. The default visual backend generates original
  motion graphics; wire in a licensed stock provider before enabling stock pulls.
- Adds attribution/disclosure fields to descriptions when configured.

## Development

```bash
pip install -r requirements-dev.txt
pytest -q
```

See `CONTRIBUTING`-style notes inline in each module under `viralagent/agents/`.
