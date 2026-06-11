/**
 * Thin Google Sheets client used for (a) checking which topics/titles have
 * already been used so the agent avoids duplicates, and (b) appending analytics
 * rows after publishing.
 *
 * Auth is via a service-account JSON key file (GOOGLE_SHEETS_CREDENTIALS). If
 * the credentials or spreadsheet ID are missing, isConfigured() returns false
 * and the caller can fall back to a local no-op.
 */
import fs from "node:fs";
import path from "node:path";
import { google } from "googleapis";
import { env, settings, ROOT } from "./config.js";

const LOG_TAB = env.GOOGLE_SHEETS_LOG_TAB || "Log";
const ANALYTICS_TAB = env.GOOGLE_SHEETS_ANALYTICS_TAB || "Analytics";

function credentialsPath() {
  const p = env.GOOGLE_SHEETS_CREDENTIALS || "./config/google-sheets-credentials.json";
  return path.isAbsolute(p) ? p : path.join(ROOT, p);
}

export function isConfigured() {
  return Boolean(env.GOOGLE_SHEETS_ID) && fs.existsSync(credentialsPath());
}

async function getClient() {
  const auth = new google.auth.GoogleAuth({
    keyFile: credentialsPath(),
    scopes: ["https://www.googleapis.com/auth/spreadsheets"]
  });
  const authClient = await auth.getClient();
  return google.sheets({ version: "v4", auth: authClient });
}

/**
 * Return the set of topic ids (and lowercased titles) already present in the
 * Log tab, so ideation can avoid repeats. Assumes the Log tab's columns include
 * a "topicId" and "title" header somewhere in row 1.
 * @returns {Promise<{topicIds:Set<string>, titles:Set<string>}>}
 */
export async function getUsed() {
  const sheets = await getClient();
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: env.GOOGLE_SHEETS_ID,
    range: `${LOG_TAB}!A1:Z10000`
  });
  const rows = res.data.values || [];
  const topicIds = new Set();
  const titles = new Set();
  if (rows.length < 2) return { topicIds, titles };

  const header = rows[0].map((h) => String(h).trim().toLowerCase());
  const topicCol = header.indexOf("topicid");
  const titleCol = header.indexOf("title");
  for (const row of rows.slice(1)) {
    if (topicCol >= 0 && row[topicCol]) topicIds.add(String(row[topicCol]).trim());
    if (titleCol >= 0 && row[titleCol]) titles.add(String(row[titleCol]).trim().toLowerCase());
  }
  return { topicIds, titles };
}

/** Append a row of values to a given tab, creating header if the tab is empty. */
async function appendRow(tab, header, values) {
  const sheets = await getClient();
  // Ensure a header row exists.
  const existing = await sheets.spreadsheets.values.get({
    spreadsheetId: env.GOOGLE_SHEETS_ID,
    range: `${tab}!A1:A1`
  });
  if (!existing.data.values || existing.data.values.length === 0) {
    await sheets.spreadsheets.values.update({
      spreadsheetId: env.GOOGLE_SHEETS_ID,
      range: `${tab}!A1`,
      valueInputOption: "RAW",
      requestBody: { values: [header] }
    });
  }
  await sheets.spreadsheets.values.append({
    spreadsheetId: env.GOOGLE_SHEETS_ID,
    range: `${tab}!A1`,
    valueInputOption: "RAW",
    insertDataOption: "INSERT_ROWS",
    requestBody: { values: [values] }
  });
}

const LOG_HEADER = [
  "timestamp",
  "runId",
  "topicId",
  "title",
  "viralityScore",
  "videoFile",
  "tiktokStatus",
  "youtubeStatus",
  "tiktokUrl",
  "youtubeUrl"
];

const ANALYTICS_HEADER = [
  "timestamp",
  "runId",
  "platform",
  "postId",
  "url",
  "views",
  "likes",
  "comments",
  "shares"
];

/** Append a single log row describing a completed run. */
export async function appendLog(row) {
  const values = LOG_HEADER.map((k) => row[k] ?? "");
  await appendRow(LOG_TAB, LOG_HEADER, values);
}

/** Append one analytics row per platform. */
export async function appendAnalytics(row) {
  const values = ANALYTICS_HEADER.map((k) => row[k] ?? "");
  await appendRow(ANALYTICS_TAB, ANALYTICS_HEADER, values);
}

export { LOG_TAB, ANALYTICS_TAB };
