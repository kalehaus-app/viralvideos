/**
 * Orchestrator — runs all eight pipeline stages in order, threading a shared
 * `context` object through each. Handles the approval gate between stages and
 * surfaces a clean pass/fail summary.
 */
import { ensureDirs } from "./utils/config.js";
import { Logger, fileTimestamp } from "./utils/logger.js";
import { approvalGate } from "./utils/approval.js";

import * as ideation from "./stages/01-ideation.js";
import * as script from "./stages/02-script.js";
import * as voiceover from "./stages/03-voiceover.js";
import * as visuals from "./stages/04-visuals.js";
import * as captions from "./stages/05-captions.js";
import * as assembly from "./stages/06-assembly.js";
import * as publish from "./stages/07-publish.js";
import * as log from "./stages/08-log.js";

export const STAGES = [ideation, script, voiceover, visuals, captions, assembly, publish, log];

/**
 * Run one full pipeline pass.
 * @param {object} [opts]
 * @param {boolean} [opts.publish=true]  Whether stage 7 actually posts.
 * @param {boolean} [opts.dryRun]        Allow mock fallbacks when keys are absent.
 *                                       Defaults to true unless publishing is on.
 * @returns {Promise<{ok:boolean, runId:string, ctx:object, error?:Error}>}
 */
export async function runPipeline(opts = {}) {
  ensureDirs();
  const runId = fileTimestamp();
  const logger = new Logger(runId);

  const publishEnabled = opts.publish ?? true;
  const dryRun = opts.dryRun ?? !publishEnabled;
  const privatePost = opts.privatePost ?? false;

  const ctx = { runId, logger, publishEnabled, dryRun, privatePost };

  logger.stage(
    `=== Kaley AI run ${runId} (publish=${publishEnabled}, dryRun=${dryRun}) ===`
  );

  const t0 = Date.now();
  for (const stage of STAGES) {
    const label = stage.name;
    const sStart = Date.now();
    logger.stage(`▶ Stage: ${label}`);
    try {
      await stage.run(ctx);
    } catch (err) {
      logger.error(`Stage "${label}" failed: ${err.message}`);
      return { ok: false, runId, ctx, error: err };
    }
    logger.info(`✓ ${label} done in ${((Date.now() - sStart) / 1000).toFixed(1)}s`);

    const proceed = await approvalGate(label, ctx, logger);
    if (!proceed) return { ok: false, runId, ctx, error: new Error("Aborted by operator.") };
  }

  logger.stage(`=== Run ${runId} complete in ${((Date.now() - t0) / 1000).toFixed(1)}s ===`);
  return { ok: true, runId, ctx };
}
