/**
 * Stage 6 — ASSEMBLY (Option B: code-generated composition)
 *
 * Instead of a pre-built Creatomate template, this stage builds the entire 9:16
 * video definition in code and sends it to Creatomate as a `source`:
 *   - B-roll clips from Pexels, sequenced back-to-back to fill the voiceover
 *   - the ElevenLabs voiceover as the audio track (sent as a data URI)
 *   - word-by-word highlight captions, auto-generated from the voiceover
 *   - optional background music (set BACKGROUND_MUSIC_URL in .env)
 * No manual template building required.
 *
 * Caption styling lives in buildCaptionElement() — tweak font/colors there.
 *
 * Produces: ctx.assembly = { videoPath, renderId, renderUrl }
 */
import fs from "node:fs";
import path from "node:path";
import axios from "axios";
import { env, settings, PATHS } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";

export const name = "assembly";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function hasKey() {
  return Boolean(env.CREATOMATE_API_KEY);
}

function audioDataUri(audioPath) {
  const b64 = fs.readFileSync(audioPath).toString("base64");
  return `data:audio/mpeg;base64,${b64}`;
}

/** Best estimate of the voiceover's true length, in seconds. */
function voiceoverSeconds(ctx) {
  const words = ctx.captions?.words || [];
  const lastEnd = words.length ? words[words.length - 1].end : 0;
  const fromCaptions = lastEnd ? Math.ceil(lastEnd) + 1 : 0;
  return fromCaptions || ctx.voiceover?.durationEstimate || ctx.script?.estimatedSeconds || 40;
}

/** Only clips we can actually render (real http(s) urls, not mock placeholders). */
function realClips(ctx) {
  return (ctx.visuals?.clips || []).filter(
    (c) => c.url && c.source !== "mock" && !String(c.url).includes("example.com")
  );
}

/** Big, bold, centered, word-by-word highlight captions (the Shorts look). */
function buildCaptionElement() {
  return {
    type: "text",
    name: "Captions",
    transcript_source: "Voiceover",
    transcript_effect: "highlight",
    transcript_color: "#FFD400",
    transcript_maximum_length: 24,
    x: "50%",
    y: "78%",
    width: "86%",
    x_alignment: "50%",
    y_alignment: "50%",
    font_family: "Montserrat",
    font_weight: "800",
    font_size: "7.5 vmin",
    fill_color: "#ffffff",
    stroke_color: "#000000",
    stroke_width: "1.1 vmin",
    text_transform: "uppercase",
    line_height: "118%",
    track: 3
  };
}

function buildSource(ctx) {
  const total = voiceoverSeconds(ctx);
  const clips = realClips(ctx);
  const perClip = +(total / clips.length).toFixed(2);

  const elements = [];

  // Track 1: B-roll clips, sequenced back-to-back to cover the full duration.
  clips.forEach((clip, i) => {
    elements.push({
      type: "video",
      name: `Video-${i + 1}`,
      source: clip.url,
      track: 1,
      time: +(i * perClip).toFixed(2),
      duration: perClip,
      fit: "cover",
      volume: 0
    });
  });

  // Track 2: the voiceover (named so captions can transcribe it).
  elements.push({
    type: "audio",
    name: "Voiceover",
    source: audioDataUri(ctx.voiceover.audioPath),
    track: 2,
    time: 0
  });

  // Track 4: optional background music, ducked under the voice.
  if (settings.assembly.backgroundMusic && env.BACKGROUND_MUSIC_URL) {
    elements.push({
      type: "audio",
      name: "Music",
      source: env.BACKGROUND_MUSIC_URL,
      track: 4,
      time: 0,
      duration: total,
      loop: true,
      volume: 18
    });
  }

  // Track 3: captions on top.
  elements.push(buildCaptionElement());

  return {
    output_format: "mp4",
    width: settings.assembly.width,
    height: settings.assembly.height,
    frame_rate: 30,
    duration: total,
    elements
  };
}

async function pollRender(renderId, logger) {
  for (let i = 0; i < 60; i++) {
    const res = await axios.get(`https://api.creatomate.com/v1/renders/${renderId}`, {
      headers: { Authorization: `Bearer ${env.CREATOMATE_API_KEY}` },
      timeout: 30000
    });
    const status = res.data.status;
    if (status === "succeeded") return res.data;
    if (status === "failed") {
      throw new Error(`Creatomate render failed: ${res.data.error_message || "unknown"}`);
    }
    logger.info(`Creatomate render ${renderId}: ${status} (${i + 1})`);
    await sleep(5000);
  }
  throw new Error("Creatomate render timed out.");
}

async function download(url, dest) {
  const res = await axios.get(url, { responseType: "arraybuffer", timeout: 120000 });
  fs.writeFileSync(dest, Buffer.from(res.data));
}

export async function run(ctx) {
  const { logger, runId } = ctx;
  if (!ctx.visuals?.clips) throw new Error("assembly stage requires ctx.visuals.");
  const videoPath = path.join(PATHS.videos, `video_${runId}.mp4`);

  const clips = realClips(ctx);
  const canRender = hasKey() && !ctx.voiceover.mock && clips.length > 0;

  if (!canRender) {
    if (!ctx.dryRun) {
      if (!hasKey()) throw new Error("CREATOMATE_API_KEY not set.");
      if (ctx.voiceover.mock) throw new Error("Voiceover is a mock — cannot assemble.");
      throw new Error("No real B-roll clips available — cannot assemble.");
    }
    fs.writeFileSync(videoPath, Buffer.from("MOCK_VIDEO"));
    ctx.assembly = { videoPath, renderId: null, renderUrl: null, mock: true };
    logger.ok(`(mock) Video placeholder written: ${videoPath}`);
    return ctx;
  }

  const source = buildSource(ctx);
  logger.info(`Assembling ${clips.length} clips over ~${source.duration}s with captions.`);

  const render = await withRetry(
    async () => {
      const res = await axios.post(
        "https://api.creatomate.com/v1/renders",
        { source },
        {
          headers: {
            Authorization: `Bearer ${env.CREATOMATE_API_KEY}`,
            "Content-Type": "application/json"
          },
          timeout: 120000
        }
      );
      return Array.isArray(res.data) ? res.data[0] : res.data;
    },
    { label: "creatomate.render", logger }
  );

  const finished = await withRetry(() => pollRender(render.id, logger), {
    label: "creatomate.poll",
    logger,
    attempts: 1
  });

  await withRetry(() => download(finished.url, videoPath), {
    label: "creatomate.download",
    logger
  });

  ctx.assembly = { videoPath, renderId: finished.id, renderUrl: finished.url };
  logger.ok(`Final video assembled: ${videoPath}`);
  return ctx;
}
