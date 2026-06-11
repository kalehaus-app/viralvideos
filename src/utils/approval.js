/**
 * Manual approval gate. When settings.approvalMode is true (and we're running
 * interactively), the pipeline pauses after each stage and waits for the
 * operator to press Enter (or type "n" to abort). In full-auto mode this is a
 * no-op.
 */
import readline from "node:readline";
import { settings } from "./config.js";

/**
 * @param {string} stageName
 * @param {object} ctx          The current pipeline context (for inspection).
 * @param {import('./logger.js').Logger} logger
 * @returns {Promise<boolean>}  true to continue, false to abort.
 */
export async function approvalGate(stageName, ctx, logger) {
  if (!settings.approvalMode) return true;
  if (!process.stdin.isTTY) {
    logger.warn(`approvalMode is on but no TTY is attached — auto-continuing after ${stageName}.`);
    return true;
  }

  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  const answer = await new Promise((resolve) => {
    rl.question(
      `\n⏸  Approve output of "${stageName}"? [Enter = continue, n = abort] `,
      resolve
    );
  });
  rl.close();
  const proceed = answer.trim().toLowerCase() !== "n";
  if (!proceed) logger.warn(`Operator aborted at stage "${stageName}".`);
  return proceed;
}
