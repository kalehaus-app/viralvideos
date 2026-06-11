/**
 * Tiny logger that writes to both the console and a timestamped run log file
 * under output/logs. Each run gets its own file so failures are easy to inspect.
 */
import fs from "node:fs";
import path from "node:path";
import { PATHS, ensureDirs } from "./config.js";

const LEVEL_COLORS = {
  info: "\x1b[36m", // cyan
  ok: "\x1b[32m", // green
  warn: "\x1b[33m", // yellow
  error: "\x1b[31m", // red
  stage: "\x1b[35m" // magenta
};
const RESET = "\x1b[0m";

/** A short timestamp safe for filenames, e.g. 2026-06-11_09-00-03. */
export function fileTimestamp(d = new Date()) {
  return d.toISOString().replace(/:/g, "-").replace(/\..+/, "").replace("T", "_");
}

export class Logger {
  constructor(runId = fileTimestamp()) {
    ensureDirs();
    this.runId = runId;
    this.logFile = path.join(PATHS.logs, `run_${runId}.log`);
  }

  _write(level, args) {
    const ts = new Date().toISOString();
    const line = `[${ts}] [${level.toUpperCase()}] ${args
      .map((a) => (typeof a === "string" ? a : JSON.stringify(a)))
      .join(" ")}`;
    const color = LEVEL_COLORS[level] || "";
    // eslint-disable-next-line no-console
    console.log(`${color}${line}${RESET}`);
    try {
      fs.appendFileSync(this.logFile, line + "\n");
    } catch {
      // Logging must never crash the pipeline.
    }
  }

  info(...a) { this._write("info", a); }
  ok(...a) { this._write("ok", a); }
  warn(...a) { this._write("warn", a); }
  error(...a) { this._write("error", a); }
  stage(...a) { this._write("stage", a); }
}

export const logger = new Logger();
