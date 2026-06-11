/**
 * Stage 2 — SCRIPT
 *
 * Writes a 30-45s vertical video script using the "Old Way vs AI Way" template
 * (Hook -> Old Way -> AI Way -> Proof -> CTA). Also extracts B-roll keywords
 * and any screen-recording shot notes for the visuals stage.
 *
 * Produces: ctx.script = { hook, oldWay, aiWay, proof, cta, narration,
 *                          keywords[], screenRecordingShots[], estimatedSeconds }
 */
import { settings } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";
import { hasClaude, getClaude, textOf, extractJson } from "../utils/ai.js";
import { SCRIPT_STRUCTURE, toNarration } from "../templates/scriptTemplate.js";
import { TOPICS } from "../templates/topics.js";

export const name = "script";

function estimateSeconds(narration) {
  const words = narration.trim().split(/\s+/).filter(Boolean).length;
  // ~165 spoken words per minute => seconds = words / 2.75
  return Math.round((words / 165) * 60);
}

function mockScript(idea) {
  const topic = TOPICS.find((t) => t.id === idea.topicId) || {};
  const script = {
    hook: `The old way of ${idea.label.toLowerCase()} versus the AI way.`,
    oldWay: `Old way: ${topic.oldWay || "you do it all by hand"}, losing hours every single week and dreading it.`,
    aiWay: `AI way: ${topic.aiWay || "an AI-powered spreadsheet does it for you"}, in a couple of clicks.`,
    proof: `One client went from three hours a week to about three minutes. Same result, zero stress.`,
    cta: `Follow Kaley AI for the workflows that run your business while you sleep — templates dropping soon.`
  };
  const narration = toNarration(script);
  return {
    ...script,
    narration,
    keywords: ["laptop spreadsheet", "small business owner working", "automation technology", "relaxed entrepreneur", "office desk"],
    screenRecordingShots: ["Screen recording: the AI spreadsheet auto-filling rows"],
    estimatedSeconds: estimateSeconds(narration)
  };
}

export async function run(ctx) {
  const { logger, idea } = ctx;
  if (!idea) throw new Error("script stage requires ctx.idea from ideation.");

  if (!hasClaude()) {
    if (!ctx.dryRun) throw new Error("ANTHROPIC_API_KEY is not set.");
    ctx.script = mockScript(idea);
    logger.ok(`(mock) Script written (~${ctx.script.estimatedSeconds}s).`);
    return ctx;
  }

  const client = getClaude();
  const brand = settings.brand;
  const system = `You are a viral short-form scriptwriter for "${brand.name}".
Tone: ${brand.tone}. Audience: ${brand.audience}.
${SCRIPT_STRUCTURE}`;

  const prompt = `Write the script for this concept:
Title: ${idea.title}
Topic: ${idea.label}
Concept: ${idea.concept}
Hook idea: ${idea.hook}

Keep the TOTAL narration (hook + oldWay + aiWay + proof + cta combined) to 90-110 words MAX so it reads in 30-40 seconds. Be ruthless — cut filler, trim every line.

Also list 4-6 concrete stock-footage search keywords for vertical B-roll that matches the narration, and any screen-recording shots that would strengthen the "AI Way" section.

Respond with ONLY this JSON:
{
  "hook": "...",
  "oldWay": "...",
  "aiWay": "...",
  "proof": "...",
  "cta": "...",
  "keywords": ["...", "..."],
  "screenRecordingShots": ["..."]
}`;

  const message = await withRetry(
    () =>
      client.messages.create({
        model: settings.models.script,
        max_tokens: 1500,
        system,
        messages: [{ role: "user", content: prompt }]
      }),
    { label: "claude.script", logger }
  );

  const parsed = extractJson(textOf(message));
  const narration = toNarration(parsed);
  const estimatedSeconds = estimateSeconds(narration);

  ctx.script = {
    hook: parsed.hook,
    oldWay: parsed.oldWay,
    aiWay: parsed.aiWay,
    proof: parsed.proof,
    cta: parsed.cta,
    narration,
    keywords: parsed.keywords || [],
    screenRecordingShots: parsed.screenRecordingShots || [],
    estimatedSeconds
  };

  const { minSeconds, maxSeconds } = settings.script;
  if (estimatedSeconds < minSeconds || estimatedSeconds > maxSeconds) {
    logger.warn(`Script length ~${estimatedSeconds}s is outside ${minSeconds}-${maxSeconds}s target.`);
  }
  logger.ok(`Script written (~${estimatedSeconds}s, ${ctx.script.keywords.length} keywords).`);
  return ctx;
}
