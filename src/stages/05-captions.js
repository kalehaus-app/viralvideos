/**
 * Stage 5 — CAPTIONS
 *
 * Transcribes the voiceover with OpenAI Whisper to get word-level timestamps for
 * burned-in captions, and writes them to a JSON file under output/captions.
 *
 * Produces: ctx.captions = { captionsPath, words: [{ word, start, end }], text }
 */
import fs from "node:fs";
import path from "node:path";
import axios from "axios";
import FormData from "form-data";
import { env, PATHS } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";

export const name = "captions";

function hasKey() {
  return Boolean(env.OPENAI_API_KEY);
}

/** Evenly distribute narration words across the estimated duration. */
function mockWords(narration, seconds) {
  const tokens = narration.trim().split(/\s+/).filter(Boolean);
  const per = seconds / Math.max(tokens.length, 1);
  return tokens.map((word, i) => ({
    word,
    start: +(i * per).toFixed(2),
    end: +((i + 1) * per).toFixed(2)
  }));
}

export async function run(ctx) {
  const { logger, voiceover, script, runId } = ctx;
  if (!voiceover?.audioPath) throw new Error("captions stage requires ctx.voiceover.audioPath.");

  const captionsPath = path.join(PATHS.captions, `captions_${runId}.json`);

  const canTranscribe = hasKey() && !voiceover.mock;
  if (!canTranscribe) {
    if (!ctx.dryRun) throw new Error("OPENAI_API_KEY not set (or voiceover is a mock).");
    const words = mockWords(script.narration, voiceover.durationEstimate || script.estimatedSeconds);
    const payload = { text: script.narration, words };
    fs.writeFileSync(captionsPath, JSON.stringify(payload, null, 2));
    ctx.captions = { captionsPath, words, text: script.narration, mock: true };
    logger.ok(`(mock) ${words.length} word timestamps written: ${captionsPath}`);
    return ctx;
  }

  const transcript = await withRetry(
    async () => {
      const form = new FormData();
      form.append("file", fs.createReadStream(voiceover.audioPath));
      form.append("model", "whisper-1");
      form.append("response_format", "verbose_json");
      form.append("timestamp_granularities[]", "word");
      const res = await axios.post("https://api.openai.com/v1/audio/transcriptions", form, {
        headers: { ...form.getHeaders(), Authorization: `Bearer ${env.OPENAI_API_KEY}` },
        maxBodyLength: Infinity,
        timeout: 120000
      });
      return res.data;
    },
    { label: "openai.whisper", logger }
  );

  const words = (transcript.words || []).map((w) => ({
    word: w.word,
    start: w.start,
    end: w.end
  }));
  const payload = { text: transcript.text, words };
  fs.writeFileSync(captionsPath, JSON.stringify(payload, null, 2));

  ctx.captions = { captionsPath, words, text: transcript.text };
  logger.ok(`${words.length} word timestamps transcribed: ${captionsPath}`);
  return ctx;
}
