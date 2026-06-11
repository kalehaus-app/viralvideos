/**
 * Stage 4 — VISUALS
 *
 * Pulls matching vertical stock B-roll from Pexels for each script keyword, and
 * appends placeholder entries for any screen-recording shots the script called
 * for (you drop the real recordings in later, or swap them in Creatomate).
 *
 * Produces: ctx.visuals = { clips: [{ keyword, type, url, previewImage, source }] }
 */
import axios from "axios";
import { env, settings } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";
import * as higgsfield from "../utils/higgsfield.js";

export const name = "visuals";

/**
 * Optionally generate one AI hook clip with Higgsfield and return it as a clip
 * object to lead the video. Best-effort: any failure (or missing creds) returns
 * null so the stage falls back to Pexels-only.
 */
async function maybeAiClip(ctx) {
  const cfg = settings.visuals.aiClip || {};
  if (!cfg.enabled) return null;
  if (!higgsfield.hasCreds()) {
    ctx.logger.warn("aiClip is enabled but HIGGSFIELD_API_KEY/SECRET are missing — skipping.");
    return null;
  }
  const prompt = `Vertical 9:16, cinematic, scroll-stopping hook visual for a short video about: ${ctx.idea?.concept || ctx.script?.hook}. Modern, clean, warm lighting, subtle motion. No text.`;
  try {
    const url = await higgsfield.generateClip(
      { prompt, model: cfg.model, durationSeconds: cfg.durationSeconds, aspectRatio: "9:16" },
      ctx.logger
    );
    ctx.logger.ok("AI hook clip generated via Higgsfield.");
    return { keyword: "AI hook", type: "ai", url, previewImage: null, source: "higgsfield" };
  } catch (err) {
    ctx.logger.warn(`Higgsfield AI clip failed (using Pexels only): ${err.message}`);
    return null;
  }
}

function hasKey() {
  return Boolean(env.PEXELS_API_KEY);
}

/** Choose the best portrait video file link from a Pexels video object. */
function pickFile(video) {
  const files = (video.video_files || []).filter((f) => f.width && f.height);
  const portrait = files.filter((f) => f.height >= f.width);
  const pool = portrait.length ? portrait : files;
  // Prefer something close to 1080 wide but not enormous.
  pool.sort((a, b) => Math.abs((a.width || 0) - 1080) - Math.abs((b.width || 0) - 1080));
  return pool[0];
}

async function searchOne(keyword, logger) {
  const res = await axios.get("https://api.pexels.com/videos/search", {
    headers: { Authorization: env.PEXELS_API_KEY },
    params: {
      query: keyword,
      orientation: settings.visuals.orientation,
      per_page: settings.visuals.perPage,
      size: "medium"
    },
    timeout: 60000
  });
  const videos = res.data.videos || [];
  if (videos.length === 0) return null;
  const video = videos[Math.floor(Math.random() * Math.min(videos.length, 5))];
  const file = pickFile(video);
  if (!file) return null;
  return {
    keyword,
    type: "broll",
    url: file.link,
    previewImage: video.image,
    source: `pexels:${video.id}`
  };
}

function mockClips(keywords) {
  return keywords.slice(0, settings.visuals.clipsPerVideo).map((kw, i) => ({
    keyword: kw,
    type: "broll",
    url: `https://example.com/mock-broll-${i}.mp4`,
    previewImage: `https://example.com/mock-broll-${i}.jpg`,
    source: "mock"
  }));
}

export async function run(ctx) {
  const { logger, script } = ctx;
  if (!script?.keywords) throw new Error("visuals stage requires ctx.script.keywords.");

  const screenRecordingPlaceholders = (script.screenRecordingShots || []).map((shot) => ({
    keyword: shot,
    type: "screen-recording",
    url: null,
    previewImage: null,
    source: "placeholder"
  }));

  // Optional AI hook clip (Higgsfield) leads the video when enabled.
  const aiClip = await maybeAiClip(ctx);

  if (!hasKey()) {
    if (!ctx.dryRun) throw new Error("PEXELS_API_KEY is not set.");
    const lead = aiClip ? [aiClip] : [];
    ctx.visuals = { clips: [...lead, ...mockClips(script.keywords), ...screenRecordingPlaceholders] };
    logger.ok(`(mock) ${ctx.visuals.clips.length} visual entries prepared.`);
    return ctx;
  }

  const clips = aiClip ? [aiClip] : [];
  const want = settings.visuals.clipsPerVideo;
  for (const keyword of script.keywords) {
    if (clips.length >= want) break;
    try {
      const clip = await withRetry(() => searchOne(keyword, logger), {
        label: `pexels.search(${keyword})`,
        logger
      });
      if (clip) clips.push(clip);
      else logger.warn(`No Pexels results for "${keyword}".`);
    } catch (err) {
      logger.warn(`Pexels search failed for "${keyword}": ${err.message}`);
    }
  }

  if (clips.length === 0) throw new Error("No B-roll clips could be sourced from Pexels.");

  ctx.visuals = { clips: [...clips, ...screenRecordingPlaceholders] };
  logger.ok(
    `${clips.length} B-roll clips sourced (+${screenRecordingPlaceholders.length} screen-recording placeholders).`
  );
  return ctx;
}
