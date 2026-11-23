import { readFileSync, readdirSync, renameSync, unlinkSync, writeFileSync, accessSync, constants, statSync } from "node:fs";
import { createHash } from "node:crypto";
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
    } catch {}
  }
  return null;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

export type NewestState = { kind: "gone" } | { kind: "state"; state: string } | { kind: "unknown" };
const GONE: NewestState = { kind: "gone" };
const UNKNOWN_STATE: NewestState = { kind: "unknown" };

export function newestState(rex: string, session: string, block: string): NewestState {
  const r = spawnSync(rex, ["block", "call", "-s", session, "-b", block, "program_status"], {
    encoding: "utf8",
    timeout: 10_000,
  });
  if (r.error || r.status !== 0) {
    return (r.stderr ?? "").includes("not found") ? GONE : UNKNOWN_STATE;
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(r.stdout);
  } catch {
    return UNKNOWN_STATE;
  }
  if (!isRecord(parsed) || !Array.isArray(parsed.records) || parsed.records.length === 0) return UNKNOWN_STATE;
  const records = parsed.records.filter(isRecord);
  if (records.length === 0) return UNKNOWN_STATE;
  const updatedAt = (rec: Record<string, unknown>) => String(rec.updated_at ?? "");
  const newest = records.reduce((best, rec) => (updatedAt(rec) > updatedAt(best) ? rec : best));
  if (typeof newest.state !== "string") return UNKNOWN_STATE;
  return newest.state === "gone" ? GONE : { kind: "state", state: newest.state };
}

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

function legacyRowId(line: string): string {
  const h = createHash("sha256").update(line).digest("hex");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20, 32)}`;
}

function writeRowAtomically(path: string, data: string): void {
  const temp = `${path}.tmp.${process.pid}`;
  writeFileSync(temp, data);
  renameSync(temp, path);
}

export function drainLegacyList(dir: string, sessionId: string): void {
  const path = join(dir, `${sessionId}.jsonl`);
  let text: string;
  try {
    text = readFileSync(path, "utf8");
  } catch {
    return;
  }
  for (const name of readdirSync(dir)) {
    if (name.startsWith(`${sessionId}.`) && name.includes(".json.tmp.")) {
      try {
        unlinkSync(join(dir, name));
      } catch {}
    }
  }
  for (const line of text.split("\n")) {
    if (line.length === 0) continue;
    const file = join(dir, `${sessionId}.${legacyRowId(line)}.json`);
    try {
      writeRowAtomically(file, line + "\n");
    } catch {
      return;
    }
  }
  try {
    unlinkSync(path);
  } catch {}
}

function settle(rex: string, file: string): void {
  let entry: unknown;
  try {
    entry = JSON.parse(readFileSync(file, "utf8"));
  } catch {
    return;
  }
  if (!isRecord(entry) || typeof entry.rex_session !== "string" || typeof entry.block !== "string") return;
  const newest = newestState(rex, entry.rex_session, entry.block);
  if (newest.kind === "state" && (newest.state === "done" || newest.state === "error")) {
    const r = spawnSync(rex, ["block", "close", "-s", entry.rex_session, entry.block], {
      encoding: "utf8",
      timeout: 10_000,
    });
    if (r.error || r.status !== 0) return;
  } else if (newest.kind !== "gone") {
    return;
  }
  try {
    unlinkSync(file);
  } catch {}
}

function main(): number {
  const data: unknown = JSON.parse(readFileSync(0, "utf8"));
  const sessionId = isRecord(data) && typeof data.session_id === "string" ? data.session_id : "";
  const rex = which("rex");
  if (!sessionId || !rex) return 0;
  drainLegacyList(CACHE, sessionId);
  for (const file of rowFiles(CACHE, sessionId)) settle(rex, file);
  return 0;
}

if (isMain(import.meta.url)) process.exit(main());
