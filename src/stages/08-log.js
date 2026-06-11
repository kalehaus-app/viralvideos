/**
 * Stage 8 — LOG
 *
 * Appends a run summary to the Google Sheets Log tab (used by ideation for
 * dedupe) and an analytics row per published platform. Always also writes a
 * local JSON summary under output/logs so there's a record even when Sheets
 * isn't configured.
 *
 * Produces: ctx.logResult = { sheet: bool, summaryPath }
 */
import fs from "node:fs";
import path from "node:path";
import { PATHS } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";
import * as sheets from "../utils/sheets.js";

export const name = "log";

function buildSummary(ctx) {
  const { idea, script, voiceover, visuals, captions, assembly, publish, runId } = ctx;
  return {
    timestamp: new Date().toISOString(),
    runId,
    idea,
    script: script && {
      narration: script.narration,
      estimatedSeconds: script.estimatedSeconds,
      keywords: script.keywords
    },
    audioPath: voiceover?.audioPath,
    clipCount: visuals?.clips?.length,
    captionsPath: captions?.captionsPath,
    videoPath: assembly?.videoPath,
    publish: publish && { captions: publish.captions, results: publish.results }
  };
}

export async function run(ctx) {
  const { logger, runId } = ctx;
  const summary = buildSummary(ctx);

  const summaryPath = path.join(PATHS.logs, `summary_${runId}.json`);
  fs.writeFileSync(summaryPath, JSON.stringify(summary, null, 2));
  logger.ok(`Run summary written: ${summaryPath}`);

  let wroteSheet = false;
  if (sheets.isConfigured()) {
    try {
      const results = ctx.publish?.results || {};
      await withRetry(
        () =>
          sheets.appendLog({
            timestamp: summary.timestamp,
            runId,
            topicId: ctx.idea?.topicId,
            title: ctx.idea?.title,
            viralityScore: ctx.idea?.viralityScore,
            videoFile: path.basename(ctx.assembly?.videoPath || ""),
            tiktokStatus: results.tiktok?.status,
            youtubeStatus: results.youtube?.status,
            tiktokUrl: results.tiktok?.url || "",
            youtubeUrl: results.youtube?.url || ""
          }),
        { label: "sheets.appendLog", logger }
      );

      // One analytics row per platform that actually published.
      for (const platform of ["tiktok", "youtube"]) {
        const r = results[platform];
        if (r?.status === "published") {
          await withRetry(
            () =>
              sheets.appendAnalytics({
                timestamp: summary.timestamp,
                runId,
                platform,
                postId: r.id || "",
                url: r.url || "",
                views: 0,
                likes: 0,
                comments: 0,
                shares: 0
              }),
            { label: `sheets.appendAnalytics.${platform}`, logger }
          );
        }
      }
      wroteSheet = true;
      logger.ok("Logged to Google Sheets.");
    } catch (err) {
      logger.error(`Google Sheets logging failed (local summary still saved): ${err.message}`);
    }
  } else {
    logger.warn("Google Sheets not configured — only the local summary was written.");
  }

  ctx.logResult = { sheet: wroteSheet, summaryPath };
  return ctx;
}
