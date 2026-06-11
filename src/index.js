/**
 * Entry point.
 *
 *   node src/index.js                 -> start the cron scheduler (full auto)
 *   node src/index.js --run-once      -> run the pipeline once and exit
 *   node src/index.js --run-once --no-publish  -> one dry run, nothing posted
 *
 * npm scripts:
 *   npm start      -> scheduler
 *   npm run test   -> one full pass with publishing OFF
 *   npm run run-once -> one full pass with publishing ON
 */
import cron from "node-cron";
import { settings } from "./utils/config.js";
import { logger } from "./utils/logger.js";
import { runPipeline } from "./orchestrator.js";

const args = process.argv.slice(2);
const runOnce = args.includes("--run-once");
const noPublish = args.includes("--no-publish");
const privatePost = args.includes("--private");

async function once() {
  const result = await runPipeline({ publish: !noPublish, privatePost });
  if (!result.ok) {
    logger.error(`Pipeline run ${result.runId} did not complete.`);
    process.exitCode = 1;
  }
  return result;
}

async function main() {
  if (runOnce) {
    await once();
    return;
  }

  // Scheduler mode.
  const { cron: expr, timezone } = settings.schedule;
  if (!cron.validate(expr)) {
    logger.error(`Invalid cron expression in settings.json: "${expr}"`);
    process.exit(1);
  }

  logger.stage(`Kaley AI scheduler started. Cron "${expr}" (${timezone}). Waiting for the next run…`);
  let running = false;
  cron.schedule(
    expr,
    async () => {
      if (running) {
        logger.warn("Previous run still in progress — skipping this tick.");
        return;
      }
      running = true;
      try {
        await runPipeline({ publish: !noPublish, privatePost });
      } catch (err) {
        logger.error(`Scheduled run crashed: ${err.message}`);
      } finally {
        running = false;
      }
    },
    { timezone }
  );

  // Keep the process alive.
  process.stdin.resume();
}

main().catch((err) => {
  logger.error(`Fatal: ${err.stack || err.message}`);
  process.exit(1);
});
