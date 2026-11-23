/**
 * SessionEnd hook: close this session's mirror blocks that ended `done` or `error`.
 *
 * rex_mirror.ts lists each block it opens in its own row file,
 * ~/.cache/rex-agents/<session_id>.<uuid>.json. The viewer closes its own block
 * when the command exits, so this hook retries a close that failed. A block
 * whose newest status record is `done` or `error` is closed; a block still
 * `working` stays open for the user. The hook deletes a row file only after
 * its block's close succeeded or the block is gone. A rex timeout, a failed
 * close, non-JSON stdout, or a missing key leaves the row file in place, and
 * the hook moves on to the next block. The hook never rewrites a file, so a
 * row that a mirror writes during the pass, or a pass that is killed, loses
 * no row.
 */

import { readFileSync, readdirSync, unlinkSync, accessSync, constants, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { isMain } from "../scripts/is_main.ts";

const CACHE = join(homedir(), ".cache", "rex-agents");
const ROW_NAME = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.json$/;

function which(name: string): string | null {
  for (const dir of (process.env.PATH ?? "").split(":")) {
    const p = join(dir, name);
    try {
      accessSync(p, constants.X_OK);
      if (statSync(p).isFile()) return p;
    } catch {
      // not executable or not there: keep searching
    }
  }
  return null;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/** Return the state of the block's newest record, "gone" if the block is gone, or null. */
export function newestState(rex: string, session: string, block: string): string | null {
  const r = spawnSync(rex, ["block", "call", "-s", session, "-b", block, "program_status"], {
    encoding: "utf8",
    timeout: 10_000,
  });
  if (r.error || r.status !== 0) {
    return (r.stderr ?? "").includes("not found") ? "gone" : null;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(r.stdout);
  } catch {
    return null;
  }
  if (!isRecord(parsed) || !Array.isArray(parsed.records) || parsed.records.length === 0) return null;
  const records = parsed.records.filter(isRecord);
  if (records.length === 0) return null;
  const updatedAt = (rec: Record<string, unknown>) => String(rec.updated_at ?? "");
  const newest = records.reduce((best, rec) => (updatedAt(rec) > updatedAt(best) ? rec : best));
  return typeof newest.state === "string" ? newest.state : null;
}

/** The row files of one session: `<session_id>.<uuid>.json` in dir. */
export function rowFiles(dir: string, sessionId: string): string[] {
  let names: string[];
  try {
    names = readdirSync(dir);
  } catch {
    return [];
  }
  const prefix = `${sessionId}.`;
  return names
    .filter((n) => n.startsWith(prefix) && ROW_NAME.test(n.slice(prefix.length)))
    .sort()
    .map((n) => join(dir, n));
}

/** Close the row's block if it settled, and delete the row once the block is closed or gone. */
function settle(rex: string, file: string): void {
  let entry: unknown;
  try {
    entry = JSON.parse(readFileSync(file, "utf8"));
  } catch {
    return; // unreadable, or a mirror is still writing it: keep it
  }
  if (!isRecord(entry) || typeof entry.rex_session !== "string" || typeof entry.block !== "string") return;
  const state = newestState(rex, entry.rex_session, entry.block);
  if (state === "done" || state === "error") {
    const r = spawnSync(rex, ["block", "close", "-s", entry.rex_session, entry.block], {
      encoding: "utf8",
      timeout: 10_000,
    });
    if (r.error || r.status !== 0) return; // the block may still be open: keep its row
  } else if (state !== "gone") {
    return;
  }
  try {
    unlinkSync(file);
  } catch {
    // another pass deleted it
  }
}

function main(): number {
  const data: unknown = JSON.parse(readFileSync(0, "utf8"));
  const sessionId = isRecord(data) && typeof data.session_id === "string" ? data.session_id : "";
  const rex = which("rex");
  if (!sessionId || !rex) return 0;
  for (const file of rowFiles(CACHE, sessionId)) settle(rex, file);
  return 0;
}

if (isMain(import.meta.url)) process.exit(main());
