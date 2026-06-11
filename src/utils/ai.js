/**
 * Anthropic client factory + a robust JSON extractor.
 *
 * Stages call `getClaude()` to lazily build a client (only when a key exists)
 * and `extractJson()` to safely pull a JSON object/array out of a model reply,
 * even if it's wrapped in prose or a ```json fence.
 */
import Anthropic from "@anthropic-ai/sdk";
import { env } from "./config.js";

export function hasClaude() {
  return Boolean(env.ANTHROPIC_API_KEY);
}

let _client;
export function getClaude() {
  if (!hasClaude()) throw new Error("ANTHROPIC_API_KEY is not set.");
  if (!_client) _client = new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  return _client;
}

/** Pull the plain-text content out of a Messages API response. */
export function textOf(message) {
  return (message.content || [])
    .filter((b) => b.type === "text")
    .map((b) => b.text)
    .join("\n")
    .trim();
}

/**
 * Extract the first balanced JSON value from a string. Tolerates ```json fences
 * and leading/trailing prose.
 * @param {string} text
 * @returns {any}
 */
export function extractJson(text) {
  if (!text) throw new Error("No text to parse JSON from.");
  // Strip code fences first.
  const fenced = text.match(/```(?:json)?\s*([\s\S]*?)```/i);
  const candidate = fenced ? fenced[1] : text;

  // Find the first { or [ and scan to its matching close.
  const start = candidate.search(/[[{]/);
  if (start === -1) throw new Error("No JSON object/array found in model output.");

  const open = candidate[start];
  const close = open === "{" ? "}" : "]";
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < candidate.length; i++) {
    const ch = candidate[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === "\\") esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === open) depth++;
    else if (ch === close) {
      depth--;
      if (depth === 0) {
        return JSON.parse(candidate.slice(start, i + 1));
      }
    }
  }
  throw new Error("Unbalanced JSON in model output.");
}
