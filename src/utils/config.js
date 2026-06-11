/**
 * Loads environment variables and config/settings.json once, and exposes them
 * to the rest of the app. Also resolves a handful of useful absolute paths.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/** Absolute path to the project root. */
export const ROOT = path.resolve(__dirname, "..", "..");

/** Commonly used output directories. */
export const PATHS = {
  output: path.join(ROOT, "output"),
  videos: path.join(ROOT, "output", "videos"),
  audio: path.join(ROOT, "output", "audio"),
  captions: path.join(ROOT, "output", "captions"),
  visuals: path.join(ROOT, "output", "visuals"),
  logs: path.join(ROOT, "output", "logs")
};

/** Ensure every output directory exists. */
export function ensureDirs() {
  for (const dir of Object.values(PATHS)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

/** Load and parse config/settings.json. */
export function loadSettings() {
  const file = path.join(ROOT, "config", "settings.json");
  const raw = fs.readFileSync(file, "utf-8");
  return JSON.parse(raw);
}

export const settings = loadSettings();
export const env = process.env;
