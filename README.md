# Kaley AI — Autonomous AI Content Agent

An autonomous Node.js app that **produces and publishes short-form vertical video**
(TikTok + YouTube Shorts) every day with no human in the loop after setup.

**Brand:** Kaley AI · **Niche:** AI workflows + spreadsheet systems for solopreneurs
**Signature format:** *"Old Way vs AI Way"* — contrasting the manual grind with the
AI-powered version, aimed at overwhelmed multi-business owners.

---

## How it works

Each daily run executes eight stages in order. Every stage is its own file in
`src/stages/`, wrapped in 3-retry error handling, and logs to the console **and**
a per-run file in `output/logs/`.

| # | Stage | File | What it does |
|---|-------|------|--------------|
| 1 | **Ideation** | `01-ideation.js` | Claude generates 5 concepts, scores virality, picks the winner. Avoids duplicates via the Google Sheets log. |
| 2 | **Script** | `02-script.js` | Writes a 30–45s script with the Hook → Old Way → AI Way → Proof → CTA template, plus B-roll keywords. |
| 3 | **Voiceover** | `03-voiceover.js` | ElevenLabs narrates the script → MP3 in `output/audio`. |
| 4 | **Visuals** | `04-visuals.js` | Pulls matching vertical B-roll from Pexels; adds placeholders for screen-recording shots. |
| 5 | **Captions** | `05-captions.js` | OpenAI Whisper transcribes the voiceover → word-level timestamps in `output/captions`. |
| 6 | **Assembly** | `06-assembly.js` | Creatomate stitches audio + visuals + captions into a 1080×1920 MP4 in `output/videos`. |
| 7 | **Publish** | `07-publish.js` | Generates per-platform captions + hashtags, posts to TikTok + YouTube Shorts via Blotato. |
| 8 | **Log** | `08-log.js` | Appends metadata + analytics rows to Google Sheets; always writes a local JSON summary. |

The orchestrator (`src/orchestrator.js`) threads a shared `context` object through
every stage. `src/index.js` is the entry point: it either runs once or starts the
cron scheduler.

```
src/
├── index.js            # entry point (cron scheduler / run-once)
├── orchestrator.js     # runs all 8 stages in sequence
├── stages/             # one file per pipeline stage
├── templates/          # topic list + script structure
└── utils/              # config, logger, retry, approval gate, sheets, ai helpers
config/
├── settings.json       # all tunable behavior (see below)
└── google-sheets-credentials.json   # (you add this — gitignored)
output/                 # generated audio/captions/videos/logs (gitignored)
```

---

## Setup (macOS)

Requires **Node.js 22** (already the target runtime).

```bash
# 1. Install dependencies
npm install

# 2. Create your env file and fill in the keys
cp .env.example .env
#    then edit .env with your real API keys

# 3. (For Google Sheets logging) drop your service-account key file at:
#    config/google-sheets-credentials.json
#    and share the target spreadsheet with the service account's email.
```

### Required keys (`.env`)

See `.env.example` for the full annotated list. At minimum you need:
`ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_ID`, `PEXELS_API_KEY`,
`OPENAI_API_KEY`, `CREATOMATE_API_KEY` + `CREATOMATE_TEMPLATE_ID`, `BLOTATO_API_KEY`
+ the TikTok/YouTube account IDs, and the Google Sheets variables.

> **Graceful degradation:** any stage whose key is missing will, in dry-run mode,
> emit a **mock artifact** so the pipeline still completes end-to-end. This is how
> `npm run test` works before you've added every key. In a real run
> (`npm run run-once` / scheduler) a missing required key throws instead.

---

## Running

```bash
# One full pass WITHOUT publishing (safe to run anytime)
npm run test

# One full pass WITH publishing (posts to TikTok + YouTube)
npm run run-once

# Start the daily cron scheduler (full auto)
npm start
```

Keep `npm start` alive with a process manager on your Mac, e.g.:

```bash
npx pm2 start npm --name kaley-ai -- start
npx pm2 save
```

---

## Configuration (`config/settings.json`)

Everything tunable lives here — no code edits needed for day-to-day changes.

| Key | Meaning |
|-----|---------|
| `approvalMode` | `true` = pause for manual approval after each stage (interactive). `false` = full auto. |
| `schedule.cron` / `schedule.timezone` | When the scheduler fires (default `0 9 * * *`, i.e. 9am daily). |
| `models.ideation` / `models.script` | Claude model IDs. Default `claude-sonnet-4-5`; bump to `claude-sonnet-4-6` or `claude-opus-4-8` for higher quality. |
| `ideation.conceptsPerRun` / `minViralityScore` | How many concepts to generate and the minimum acceptable score. |
| `script.targetSeconds` / `min` / `max` | Target spoken length. |
| `voiceover.*` | ElevenLabs voice settings (stability, similarity, style). |
| `visuals.clipsPerVideo` / `orientation` | B-roll count and orientation. |
| `assembly.width` / `height` | Output resolution (1080×1920). |
| `publish.platforms` / `hashtagCount` | Where to post and how many hashtags. |
| `retry.attempts` / `baseDelayMs` | Retry policy for every external call (exponential backoff). |

### The Creatomate template

The Creatomate template you reference with `CREATOMATE_TEMPLATE_ID` owns the visual
design. Stage 6 feeds it a `modifications` object keyed by element name
(`Video-1`…`Video-N`, `Voiceover`, `Captions`). If your template uses different
element names, edit `buildModifications()` in `src/stages/06-assembly.js`.

### The Google Sheet

Create a sheet with two tabs: **Log** and **Analytics** (names configurable in
`.env`). The agent creates header rows automatically. The **Log** tab's `topicId`
and `title` columns are what stage 1 reads to avoid repeating content.

---

## Output

Every run writes timestamped files:

- `output/audio/voiceover_<runId>.mp3`
- `output/captions/captions_<runId>.json`
- `output/videos/video_<runId>.mp4`
- `output/logs/run_<runId>.log` (full console log)
- `output/logs/summary_<runId>.json` (structured run summary)

All of `output/`, `.env`, and the Google credentials file are **gitignored**.

---

## Extending

- **Add topics:** append to `TOPICS` in `src/templates/topics.js`.
- **Change the script formula:** edit `SCRIPT_STRUCTURE` in `src/templates/scriptTemplate.js`.
- **Add a platform:** add it to `publish.platforms` and extend `buildPost()` in `src/stages/07-publish.js`.
