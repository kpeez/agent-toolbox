/**
 * Pass a command's output through unchanged, mirror it into a Rex block, and exit with its status.
 *
 * The mirror hook pipes a background command into this script in this form:
 *
 *     { ( :; CMD
 *      ); printf '\n__rex_rc=%d\n' "$?"; } 2>&1 | bun rex_mirror.ts LABEL [SESSION_ID]
 *
 * The printf after the subshell appends a status marker. This script holds back
 * the last bytes of the stream so the marker never reaches stdout, then exits
 * with the status it names. A stream without the marker exits 125. A SIGTERM,
 * SIGINT, or SIGHUP flushes the held tail, writes the exit line with 128 plus
 * the signal number, and exits with that code, so the block settles instead of
 * staying `working`.
 */

import { appendFileSync, closeSync, mkdirSync, openSync, unlinkSync, writeFileSync, writeSync, accessSync, constants, statSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

// Scan the tail as latin1 so regex offsets stay byte offsets, as in Python's bytes regex.
const MARKER = /\n__rex_rc=(\d+)\n\n?$/;
const HOLD = 32; // longer than any marker, so a marker split across reads is still held back
const NO_MARKER = 125;
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

/** Open a Rex block that shows the log. Return its block ID, or null. */
export function startViewer(label: string, log: string, nonce: string): string | null {
  const rex = which("rex");
  const bun = which("bun");
  const session = process.env.REX_SESSION;
  if (!rex || !bun || !session) return null;
  const viewer = resolve(dirname(fileURLToPath(import.meta.url)), "rex_mirror_view.ts");
  const r = spawnSync(
    rex,
    ["run", "-s", session, "--focus=false", "--keep-open", "--shell=none", "--label", label, "--json", "--", bun, viewer, log, label, nonce],
    { encoding: "utf8", timeout: 15_000 },
  );
  if (r.error || r.status !== 0) return null;
  try {
    const parsed: unknown = JSON.parse(r.stdout);
    if (!isRecord(parsed)) return null;
    const ids = parsed.block_ids;
    if (Array.isArray(ids) && typeof ids[0] === "string") return ids[0];
    return null;
  } catch {
    return null;
  }
}

/** Record the block so the session-end hook can close it. */
export function remember(sessionId: string, block: string, label: string): void {
  mkdirSync(CACHE, { recursive: true });
  appendFileSync(
    join(CACHE, `${sessionId}.jsonl`),
    JSON.stringify({ block, rex_session: process.env.REX_SESSION, label }) + "\n",
  );
}

async function main(): Promise<number> {
  const label = process.argv[2] ?? "[claude] job";
  const sessionId = process.argv[3] ?? "";
  const log = join(tmpdir(), `rex-mirror-${randomUUID()}.log`);
  writeFileSync(log, "", { flag: "wx", mode: 0o600 });
  const nonce = randomBytes(8).toString("hex"); // the exit line names it, so command output cannot fake one
  const block = startViewer(label, log, nonce);
  if (block && sessionId) remember(sessionId, block, label);
  const logf = openSync(log, "a");
  let tail = Buffer.alloc(0);
  const emit = (buf: Buffer): void => {
    writeSync(1, buf);
    writeSync(logf, buf);
  };
  const onSignal = (code: number): void => {
    try {
      emit(tail);
    } catch {
      // stdout may already be closed; the exit line still settles the block
    }
    try {
      writeSync(logf, `\n__rex_mirror_exit_${nonce}=${code}\n`);
      closeSync(logf);
    } catch {
      // best-effort: the exit code below still reaches the caller
    }
    if (!block) {
      try {
        unlinkSync(log);
      } catch {
        // already gone
      }
    }
    process.exit(code);
  };
  process.on("SIGTERM", () => onSignal(143));
  process.on("SIGINT", () => onSignal(130));
  process.on("SIGHUP", () => onSignal(129));
  for await (const chunk of process.stdin) {
    tail = Buffer.concat([tail, chunk]);
    if (tail.length > HOLD) {
      emit(tail.subarray(0, tail.length - HOLD));
      tail = tail.subarray(tail.length - HOLD);
    }
  }
  const m = MARKER.exec(tail.toString("latin1"));
  const rc = m ? Number(m[1]) : NO_MARKER;
  emit(m ? tail.subarray(0, m.index) : tail);
  writeSync(logf, `\n__rex_mirror_exit_${nonce}=${rc}\n`);
  closeSync(logf);
  if (!block) unlinkSync(log);
  if (!m) console.error("rex_mirror: the command's exit status marker is missing");
  return rc;
}

if (import.meta.main) main().then((rc) => process.exit(rc));
