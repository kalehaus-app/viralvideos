/**
 * Stage 7 — PUBLISH
 *
 * Generates platform-optimized captions + hashtags with Claude, then publishes
 * the video to TikTok and YouTube Shorts through the Blotato API.
 *
 * Publishing is skipped when ctx.publishEnabled is false (e.g. `npm run test`),
 * but captions are still generated so you can review them.
 *
 * Produces: ctx.publish = { captions: {tiktok, youtube}, results: {tiktok, youtube} }
 */
import axios from "axios";
import { env, settings } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";
import { hasClaude, getClaude, textOf, extractJson } from "../utils/ai.js";

export const name = "publish";

function hasBlotato() {
  return Boolean(env.BLOTATO_API_KEY);
}

function mockCaptions(idea, n) {
  const tags = ["#AITools", "#Solopreneur", "#SmallBusiness", "#Productivity", "#Automation", "#SpreadsheetHacks", "#WorkSmarter", "#AIworkflow"].slice(0, n);
  const base = `${idea.title} — the old way wastes hours, the AI way takes minutes.`;
  return {
    tiktok: { caption: base, hashtags: tags },
    youtube: { caption: base, hashtags: tags, title: idea.title }
  };
}

async function generateCaptions(ctx) {
  const { logger, idea, script } = ctx;
  const n = settings.publish.hashtagCount;
  if (!hasClaude()) {
    if (!ctx.dryRun) throw new Error("ANTHROPIC_API_KEY is not set.");
    return mockCaptions(idea, n);
  }
  const client = getClaude();
  const brand = settings.brand;
  const prompt = `Write platform-optimized captions for this short video.
Title: ${idea.title}
Hook: ${script.hook}
Audience: ${brand.audience}
CTA goal: ${brand.cta}

Give ${n} relevant hashtags per platform. Keep the TikTok caption short and punchy; the YouTube Shorts description can be a touch longer and include the title-cased title.

Respond with ONLY this JSON:
{
  "tiktok":  { "caption": "...", "hashtags": ["#..."] },
  "youtube": { "title": "...", "caption": "...", "hashtags": ["#..."] }
}`;

  const message = await withRetry(
    () =>
      client.messages.create({
        model: settings.models.script,
        max_tokens: 800,
        messages: [{ role: "user", content: prompt }]
      }),
    { label: "claude.captions", logger }
  );
  return extractJson(textOf(message));
}

/** Upload media to Blotato so it returns a Blotato-hosted URL. */
async function uploadMedia(mediaUrl, logger) {
  const res = await axios.post(
    "https://backend.blotato.com/v2/media",
    { url: mediaUrl },
    {
      headers: { "blotato-api-key": env.BLOTATO_API_KEY, "Content-Type": "application/json" },
      timeout: 120000
    }
  );
  return res.data?.url || mediaUrl;
}

function buildPost(platform, accountId, caption, hashtags, mediaUrl, idea) {
  const text = `${caption}\n\n${(hashtags || []).join(" ")}`.trim();
  const target =
    platform === "youtube"
      ? { targetType: "youtube", title: caption.title || idea.title, privacyStatus: "public", shouldNotifySubscribers: true }
      : { targetType: "tiktok", privacyLevel: "PUBLIC_TO_EVERYONE", disabledComments: false };
  return {
    post: {
      accountId,
      target,
      content: { platform, text, mediaUrls: [mediaUrl] }
    }
  };
}

async function publishTo(platform, accountId, caption, hashtags, mediaUrl, idea, logger) {
  const body = buildPost(platform, accountId, caption, hashtags, mediaUrl, idea);
  const res = await axios.post("https://backend.blotato.com/v2/posts", body, {
    headers: { "blotato-api-key": env.BLOTATO_API_KEY, "Content-Type": "application/json" },
    timeout: 120000
  });
  return res.data;
}

export async function run(ctx) {
  const { logger, idea, assembly } = ctx;
  const captions = await generateCaptions(ctx);
  logger.ok("Platform captions generated.");

  const results = { tiktok: { status: "skipped" }, youtube: { status: "skipped" } };
  ctx.publish = { captions, results };

  if (!ctx.publishEnabled) {
    logger.warn("Publishing disabled (test/no-publish mode) — captions generated, nothing posted.");
    return ctx;
  }
  if (!hasBlotato()) {
    if (!ctx.dryRun) throw new Error("BLOTATO_API_KEY is not set.");
    logger.warn("(mock) Blotato not configured — marking publish as skipped.");
    return ctx;
  }
  if (assembly.mock) {
    logger.warn("Video is a mock placeholder — refusing to publish. Skipped.");
    return ctx;
  }

  const mediaSource = assembly.renderUrl || assembly.videoPath;
  const mediaUrl = await withRetry(() => uploadMedia(mediaSource, logger), {
    label: "blotato.media",
    logger
  });

  const targets = [
    { platform: "tiktok", accountId: env.BLOTATO_TIKTOK_ACCOUNT_ID, caption: captions.tiktok },
    { platform: "youtube", accountId: env.BLOTATO_YOUTUBE_ACCOUNT_ID, caption: captions.youtube }
  ];

  for (const t of settings.publish.platforms) {
    const target = targets.find((x) => x.platform === t);
    if (!target) continue;
    if (!target.accountId) {
      logger.warn(`No Blotato account id for ${t} — skipping.`);
      results[t] = { status: "skipped", reason: "no account id" };
      continue;
    }
    try {
      const out = await withRetry(
        () =>
          publishTo(
            t,
            target.accountId,
            target.caption.caption,
            target.caption.hashtags,
            mediaUrl,
            idea,
            logger
          ),
        { label: `blotato.publish.${t}`, logger }
      );
      results[t] = { status: "published", id: out?.id || out?.postId || null, url: out?.url || null, raw: out };
      logger.ok(`Published to ${t}.`);
    } catch (err) {
      results[t] = { status: "failed", error: err.message };
      logger.error(`Publish to ${t} failed: ${err.message}`);
    }
  }

  return ctx;
}
