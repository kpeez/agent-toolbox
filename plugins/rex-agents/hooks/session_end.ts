/**
 * SessionEnd hook: close this session's mirror blocks that ended `done`.
 *
 * rex_mirror.ts lists each block it opens in ~/.cache/rex-agents/<session_id>.jsonl.
 * A block whose newest status record is `done` is closed. An `error` block and a
 * block still `working` stay open for the user, and stay in the list. Each block
 * is best-effort: a rex timeout, non-JSON stdout, or a missing key leaves the
 * row in place and the hook moves on to the next block.
 */

import { existsSync, readFileSync, unlinkSync, writeFileSync, accessSync, constants, statSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const CACHE = join(homedir(), ".cache", "rex-agents");

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

function main(): number {
  const data: unknown = JSON.parse(readFileSync(0, "utf8"));
  const sessionId = isRecord(data) && typeof data.session_id === "string" ? data.session_id : "";
  const path = join(CACHE, `${sessionId}.jsonl`);
  const rex = which("rex");
  if (!sessionId || !rex || !existsSync(path)) return 0;
  const keep: string[] = [];
  for (const line of readFileSync(path, "utf8").split("\n")) {
    if (line.length === 0) continue;
    let entry: unknown;
    try {
      entry = JSON.parse(line);
    } catch {
      keep.push(line);
      continue;
    }
    if (!isRecord(entry) || typeof entry.rex_session !== "string" || typeof entry.block !== "string") {
      keep.push(line);
      continue;
    }
    const state = newestState(rex, entry.rex_session, entry.block);
    if (state === "done") {
      spawnSync(rex, ["block", "close", "-s", entry.rex_session, entry.block], {
        encoding: "utf8",
        timeout: 10_000,
      });
    } else if (state !== "gone") {
      keep.push(line);
    }
  }
  if (keep.length > 0) writeFileSync(path, keep.join("\n") + "\n");
  else unlinkSync(path);
  return 0;
}

if (import.meta.main) process.exit(main());
