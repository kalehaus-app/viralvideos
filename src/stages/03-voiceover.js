/**
 * Stage 3 — VOICEOVER
 *
 * Generates an AI voiceover of the narration with ElevenLabs and saves it as an
 * MP3 under output/audio.
 *
 * Produces: ctx.voiceover = { audioPath, durationEstimate }
 */
import fs from "node:fs";
import path from "node:path";
import axios from "axios";
import { env, settings, PATHS } from "../utils/config.js";
import { withRetry } from "../utils/retry.js";

export const name = "voiceover";

function hasKey() {
  return Boolean(env.ELEVENLABS_API_KEY && env.ELEVENLABS_VOICE_ID);
}

export async function run(ctx) {
  const { logger, script, runId } = ctx;
  if (!script?.narration) throw new Error("voiceover stage requires ctx.script.narration.");

  const audioPath = path.join(PATHS.audio, `voiceover_${runId}.mp3`);

  if (!hasKey()) {
    if (!ctx.dryRun) throw new Error("ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set.");
    fs.writeFileSync(audioPath, Buffer.from("MOCK_AUDIO")); // placeholder
    ctx.voiceover = { audioPath, durationEstimate: script.estimatedSeconds, mock: true };
    logger.ok(`(mock) Voiceover placeholder written: ${audioPath}`);
    return ctx;
  }

  const voiceId = env.ELEVENLABS_VOICE_ID;
  const url = `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}`;
  const body = {
    text: script.narration,
    model_id: env.ELEVENLABS_MODEL_ID || "eleven_multilingual_v2",
    voice_settings: {
      stability: settings.voiceover.stability,
      similarity_boost: settings.voiceover.similarityBoost,
      style: settings.voiceover.style,
      use_speaker_boost: true
    }
  };

  const buffer = await withRetry(
    async () => {
      const res = await axios.post(url, body, {
        headers: {
          "xi-api-key": env.ELEVENLABS_API_KEY,
          "Content-Type": "application/json",
          Accept: "audio/mpeg"
        },
        responseType: "arraybuffer",
        timeout: 120000
      });
      return Buffer.from(res.data);
    },
    { label: "elevenlabs.tts", logger }
  );

  fs.writeFileSync(audioPath, buffer);
  ctx.voiceover = {
    audioPath,
    durationEstimate: script.estimatedSeconds,
    bytes: buffer.length
  };
  logger.ok(`Voiceover saved (${(buffer.length / 1024).toFixed(0)} KB): ${audioPath}`);
  return ctx;
}
