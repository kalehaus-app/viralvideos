/**
 * Retry helper with exponential backoff. Used to wrap every external API call
 * so a transient network blip doesn't kill a whole run.
 */
import { settings } from "./config.js";

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * @param {() => Promise<T>} fn         The async operation to attempt.
 * @param {object} [opts]
 * @param {number} [opts.attempts]      Max attempts (default from settings).
 * @param {number} [opts.baseDelayMs]   Base backoff delay (default from settings).
 * @param {string} [opts.label]         Human label for log messages.
 * @param {import('./logger.js').Logger} [opts.logger]
 * @returns {Promise<T>}
 * @template T
 */
export async function withRetry(fn, opts = {}) {
  const attempts = opts.attempts ?? settings.retry.attempts;
  const baseDelayMs = opts.baseDelayMs ?? settings.retry.baseDelayMs;
  const label = opts.label ?? "operation";
  const log = opts.logger;

  let lastErr;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      return await fn();
    } catch (err) {
      lastErr = err;
      const detail = err?.response?.data
        ? JSON.stringify(err.response.data).slice(0, 300)
        : err?.message || String(err);
      if (log) log.warn(`${label} failed (attempt ${attempt}/${attempts}): ${detail}`);
      if (attempt < attempts) {
        const delay = baseDelayMs * 2 ** (attempt - 1);
        await sleep(delay);
      }
    }
  }
  throw new Error(`${label} failed after ${attempts} attempts: ${lastErr?.message || lastErr}`);
}
