/**
 * Stage 6 — ASSEMBLY
 *
 * Stitches voiceover + B-roll + captions into a final 9:16 1080x1920 MP4 using
 * the Creatomate API, then downloads it to output/videos.
 *
 * The Creatomate template (CREATOMATE_TEMPLATE_ID) owns the visual design. This
 * stage feeds it a `modifications` object whose keys are template element names:
 *   - Video-1 ... Video-N : B-roll/screen-recording clip sources
 *   - Voiceover            : the narration audio (sent as a data URI)
 *   - Captions             : the transcript text for burned-in captions
 * Rename these in buildModifications() to match your own template.
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
  return Boolean(env.CREATOMATE_API_KEY && env.CREATOMATE_TEMPLATE_ID);
}

function audioDataUri(audioPath) {
  const b64 = fs.readFileSync(audioPath).toString("base64");
  return `data:audio/mpeg;base64,${b64}`;
}

function buildModifications(ctx) {
  const mods = {};
  const usable = ctx.visuals.clips.filter((c) => c.url); // skip placeholder screen recordings
  usable.forEach((clip, i) => {
    mods[`Video-${i + 1}.source`] = clip.url;
  });
  // Audio: only embed a real file (mock placeholders aren't valid media).
  if (!ctx.voiceover.mock) {
    mods["Voiceover.source"] = audioDataUri(ctx.voiceover.audioPath);
  }
  mods["Captions.text"] = ctx.captions.text;
  return mods;
}

async function pollRender(renderId, logger) {
  for (let i = 0; i < 60; i++) {
    const res = await axios.get(`https://api.creatomate.com/v1/renders/${renderId}`, {
      headers: { Authorization: `Bearer ${env.CREATOMATE_API_KEY}` },
      timeout: 30000
    });
    const status = res.data.status;
    if (status === "succeeded") return res.data;
    if (status === "failed") throw new Error(`Creatomate render failed: ${res.data.error_message || "unknown"}`);
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

  if (!hasKey()) {
    if (!ctx.dryRun) throw new Error("CREATOMATE_API_KEY / CREATOMATE_TEMPLATE_ID not set.");
    fs.writeFileSync(videoPath, Buffer.from("MOCK_VIDEO")); // placeholder
    ctx.assembly = { videoPath, renderId: null, renderUrl: null, mock: true };
    logger.ok(`(mock) Video placeholder written: ${videoPath}`);
    return ctx;
  }

  const modifications = buildModifications(ctx);
  const body = {
    template_id: env.CREATOMATE_TEMPLATE_ID,
    output_format: "mp4",
    frame_rate: 30,
    width: settings.assembly.width,
    height: settings.assembly.height,
    modifications
  };

  const render = await withRetry(
    async () => {
      const res = await axios.post("https://api.creatomate.com/v1/renders", body, {
        headers: {
          Authorization: `Bearer ${env.CREATOMATE_API_KEY}`,
          "Content-Type": "application/json"
        },
        timeout: 120000
      });
      // Creatomate returns an array of render jobs.
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
