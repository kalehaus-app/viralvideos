/**
 * Higgsfield AI video-clip generation (optional visuals enhancement).
 *
 * ⚠️ ENDPOINT/AUTH TO CONFIRM: Higgsfield's public REST docs are sparse (they
 * lead with a Python SDK). The auth pattern is a key + secret pair from the
 * cloud.higgsfield.ai dashboard. The submit/poll shapes below are best-effort
 * and isolated here so they're trivial to correct once you have real creds —
 * adjust BASE, the endpoint paths, and the field names to match your account's
 * API reference, then everything else (when it's called, fallback) just works.
 *
 * This is best-effort: the visuals stage treats any failure as non-fatal and
 * falls back to Pexels-only, so a wrong guess here never breaks a run.
 */
import axios from "axios";
import { env } from "./config.js";
import { withRetry } from "./retry.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const BASE = env.HIGGSFIELD_BASE_URL || "https://platform.higgsfield.ai/v1";

export function hasCreds() {
  return Boolean(env.HIGGSFIELD_API_KEY && env.HIGGSFIELD_API_SECRET);
}

function authHeaders() {
  return {
    "hf-api-key": env.HIGGSFIELD_API_KEY,
    "hf-secret": env.HIGGSFIELD_API_SECRET,
    "Content-Type": "application/json"
  };
}

/**
 * Generate one short vertical clip from a text prompt and return its public URL.
 * @returns {Promise<string>} direct video URL
 */
export async function generateClip(
  { prompt, model = "kling3_0", durationSeconds = 5, aspectRatio = "9:16" },
  logger
) {
  // --- 1. Submit the generation job (CONFIRM path + fields) ---
  const submit = await withRetry(
    async () => {
      const res = await axios.post(
        `${BASE}/text2video`,
        { model, prompt, duration: durationSeconds, aspect_ratio: aspectRatio },
        { headers: authHeaders(), timeout: 60000 }
      );
      return res.data;
    },
    { label: "higgsfield.submit", logger }
  );

  const jobId = submit.id || submit.job_id || submit.request_id;
  if (!jobId) throw new Error("Higgsfield submit returned no job id.");

  // --- 2. Poll until the job completes (CONFIRM path + status fields) ---
  for (let i = 0; i < 60; i++) {
    const res = await axios.get(`${BASE}/jobs/${jobId}`, {
      headers: authHeaders(),
      timeout: 30000
    });
    const status = res.data.status;
    if (status === "completed" || status === "succeeded") {
      const url =
        res.data?.results?.rawUrl ||
        res.data?.url ||
        res.data?.results?.[0]?.url ||
        res.data?.output?.[0];
      if (!url) throw new Error("Higgsfield job completed but no video URL found.");
      return url;
    }
    if (status === "failed" || status === "error") {
      throw new Error(`Higgsfield job failed: ${res.data?.error || "unknown"}`);
    }
    logger?.info?.(`Higgsfield job ${jobId}: ${status} (${i + 1})`);
    await sleep(5000);
  }
  throw new Error("Higgsfield job timed out.");
}
