/**
 * Stage 1 — IDEATION
 *
 * Generates several "Old Way vs AI Way" video concepts with Claude, scores each
 * for virality, and picks the winner. Avoids repeating topics/titles already in
 * the Google Sheets log.
 *
 * Produces: ctx.idea = { topicId, label, title, concept, hook, viralityScore, reasoning }
 */
import { settings } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";
import { hasClaude, getClaude, textOf, extractJson } from "../utils/ai.js";
import { TOPICS } from "../templates/topics.js";
import * as sheets from "../utils/sheets.js";

export const name = "ideation";

async function loadUsed(logger) {
  if (!sheets.isConfigured()) {
    logger.warn("Google Sheets not configured — skipping duplicate check.");
    return { topicIds: new Set(), titles: new Set() };
  }
  try {
    return await withRetry(() => sheets.getUsed(), { label: "sheets.getUsed", logger });
  } catch (err) {
    logger.warn(`Could not read used topics (continuing without dedupe): ${err.message}`);
    return { topicIds: new Set(), titles: new Set() };
  }
}

function pickCandidateTopics(used) {
  const fresh = TOPICS.filter((t) => !used.topicIds.has(t.id));
  // If everything has been used, fall back to the full list (cycle around).
  const pool = fresh.length > 0 ? fresh : TOPICS;
  // Shuffle and keep enough to give Claude variety.
  return [...pool].sort(() => Math.random() - 0.5).slice(0, Math.min(8, pool.length));
}

function mockIdea(candidates) {
  const t = candidates[0];
  return {
    topicId: t.id,
    label: t.label,
    title: `The Old Way vs AI Way of ${t.label}`,
    concept: `Contrast the manual grind of ${t.oldWay.toLowerCase()} with ${t.aiWay.toLowerCase()}.`,
    hook: `Still doing ${t.label.toLowerCase()} the old way? Watch this.`,
    viralityScore: 8,
    reasoning: "Mock idea generated in dry-run mode (no ANTHROPIC_API_KEY)."
  };
}

export async function run(ctx) {
  const { logger } = ctx;
  const used = await loadUsed(logger);
  const candidates = pickCandidateTopics(used);
  logger.info(`Candidate topics: ${candidates.map((t) => t.id).join(", ")}`);

  if (!hasClaude()) {
    if (!ctx.dryRun) throw new Error("ANTHROPIC_API_KEY is not set.");
    ctx.idea = mockIdea(candidates);
    logger.ok(`(mock) Chose idea: "${ctx.idea.title}" [score ${ctx.idea.viralityScore}]`);
    return ctx;
  }

  const client = getClaude();
  const n = settings.ideation.conceptsPerRun;
  const brand = settings.brand;

  const system = `You are the head of content for "${brand.name}", a brand in the niche: ${brand.niche}.
Signature format: "${brand.signatureFormat}". Tone: ${brand.tone}.
Audience: ${brand.audience}.
You create short-form vertical videos for TikTok and YouTube Shorts that drive followers toward a future template product line (${brand.productLine}).`;

  const topicList = candidates
    .map((t) => `- ${t.id}: ${t.label} — old way: ${t.oldWay}; AI way: ${t.aiWay}`)
    .join("\n");

  const usedTitles = [...used.titles].slice(0, 50).join("; ") || "(none yet)";

  const prompt = `Generate ${n} distinct "Old Way vs AI Way" video concepts, each based on one of these topics:
${topicList}

Avoid concepts that duplicate any of these already-used titles: ${usedTitles}

For EACH concept, score its virality from 1-10 considering hook strength, relatability to overwhelmed solopreneurs, and shareability. Then choose the single best one.

Respond with ONLY a JSON object of this exact shape:
{
  "concepts": [
    { "topicId": "<one of the ids above>", "title": "<short punchy title>", "concept": "<1-2 sentence description>", "hook": "<the spoken opening line>", "viralityScore": <number 1-10>, "reasoning": "<why this scores that>" }
  ],
  "winnerIndex": <0-based index of the best concept>
}`;

  const message = await withRetry(
    () =>
      client.messages.create({
        model: settings.models.ideation,
        max_tokens: 2000,
        system,
        messages: [{ role: "user", content: prompt }]
      }),
    { label: "claude.ideation", logger }
  );

  const parsed = extractJson(textOf(message));
  const concepts = parsed.concepts || [];
  if (concepts.length === 0) throw new Error("Ideation returned no concepts.");

  let winner = concepts[parsed.winnerIndex] || concepts[0];
  // Defensive: respect the configured minimum score by re-picking the top scorer.
  const best = [...concepts].sort((a, b) => (b.viralityScore || 0) - (a.viralityScore || 0))[0];
  if ((winner.viralityScore || 0) < settings.ideation.minViralityScore) winner = best;

  const topic = TOPICS.find((t) => t.id === winner.topicId) || candidates[0];
  ctx.idea = {
    topicId: winner.topicId || topic.id,
    label: topic.label,
    title: winner.title,
    concept: winner.concept,
    hook: winner.hook,
    viralityScore: winner.viralityScore,
    reasoning: winner.reasoning
  };
  ctx.allConcepts = concepts;

  logger.ok(`Chose idea: "${ctx.idea.title}" [score ${ctx.idea.viralityScore}]`);
  return ctx;
}
