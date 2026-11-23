/**
 * Pass a command's output through unchanged, mirror it into a Rex block, and exit with its status.
 *
 * The mirror hook pipes a background command into this script in this form:
 *
 *     { ( :; CMD
 *      ); printf '\n__rex_rc=%d\n' "$?"; } 2>&1 | RUNTIME rex_mirror.ts LABEL [SESSION_ID]
 *
 * The printf after the subshell appends a status marker. This script holds back
 * the last bytes of the stream so the marker never reaches stdout, then exits
 * with the status it names. A stream without the marker exits 125. A SIGTERM,
 * SIGINT, or SIGHUP flushes the held tail, writes the exit line with 128 plus
 * the signal number, and exits with that code, so the block settles instead of
 * staying `working`.
 */

import { closeSync, mkdirSync, openSync, unlinkSync, writeFileSync, writeSync, accessSync, constants, statSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { isMain } from "./is_main.ts";
import { runtimeFlags } from "./runtime_flags.ts";

// Scan the tail as latin1 so regex offsets stay byte offsets, as in Python's bytes regex.
const MARKER = /\n__rex_rc=(\d+)\n\n?$/;
const HOLD = 32; // longer than any marker, so a marker split across reads is still held back
const NO_MARKER = 125;
const OPEN_DELAY_MS = 1_500;
const FLOAT_BOUNDS: readonly [number, number, number, number] = [0.15, 0.15, 0.7, 0.7];
const CACHE = join(homedir(), ".cache", "rex-agents");

type ViewerState =
  | { kind: "pending"; timer: ReturnType<typeof setTimeout> }
  | { kind: "open"; block: string }
  | { kind: "skipped" };

export function openDelayMs(env: NodeJS.ProcessEnv = process.env): number {
  const raw = env.REX_AGENTS_MIRROR_DELAY_MS?.trim();
  if (!raw) return OPEN_DELAY_MS;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed >= 0 ? Math.floor(parsed) : OPEN_DELAY_MS;
}

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

function windowForBlock(rex: string, session: string, blockId: string): string | null {
  const r = spawnSync(rex, ["block", "inspect", blockId, "-s", session, "--json"], {
    encoding: "utf8",
    timeout: 5_000,
  });
  if (r.error || r.status !== 0) return null;
  try {
    const parsed: unknown = JSON.parse(r.stdout);
    if (!isRecord(parsed) || !isRecord(parsed.block)) return null;
    const windowId = parsed.block.window_id;
    return typeof windowId === "string" && windowId.length > 0 ? windowId : null;
  } catch {
    return null;
  }
}

/** Open a minimized floating Rex pane (or fallback block) that shows the log. Return its block ID, or null. */
export function startViewer(label: string, log: string, nonce: string): string | null {
  const rex = which("rex");
  const session = process.env.REX_SESSION;
  if (!rex || !session) return null;
  const viewer = resolve(dirname(fileURLToPath(import.meta.url)), "rex_mirror_view.ts");
  const command = [process.execPath, ...runtimeFlags(), viewer, log, label, nonce];
  const windowId = process.env.REX_BLOCK ? windowForBlock(rex, session, process.env.REX_BLOCK) : null;
  const params: Record<string, unknown> = {
    bounds: FLOAT_BOUNDS,
    focus: false,
    layout: {
      block: {
        flavor: "com.superlogical.terminal.shell",
        label,
        options: {
          shell: "none",
          login: false,
          command,
          exit: { on_completion: false },
        },
      },
    },
  };
  if (windowId) params.window_id = windowId;
  const layer = spawnSync(
    rex,
    ["api", "call", "-s", session, "session.new_layer", JSON.stringify(params)],
    { encoding: "utf8", timeout: 15_000 },
  );
  if (!layer.error && layer.status === 0) {
    try {
      const parsed: unknown = JSON.parse(layer.stdout);
      if (
        isRecord(parsed) &&
        typeof parsed.layer_id === "string" &&
        parsed.layer_id.length > 0 &&
        Array.isArray(parsed.block_ids) &&
        typeof parsed.block_ids[0] === "string" &&
        parsed.block_ids[0].length > 0
      ) {
        spawnSync(
          rex,
          [
            "api",
            "call",
            "-s",
            session,
            "session.set_layer_state",
            JSON.stringify({ layer_id: parsed.layer_id, state: "minimized" }),
          ],
          { stdio: "ignore", timeout: 5_000 },
        );
        return parsed.block_ids[0];
      }
    } catch {
      // fall through to rex run
    }
  }
  const r = spawnSync(
    rex,
    ["run", "-s", session, "--focus=false", "--keep-open", "--shell=none", "--label", label, "--json", "--", ...command],
    { encoding: "utf8", timeout: 15_000 },
  );
  if (r.error || r.status !== 0) return null;
  try {
    const parsed: unknown = JSON.parse(r.stdout);
    if (!isRecord(parsed)) return null;
    const ids = parsed.block_ids;
    if (Array.isArray(ids) && typeof ids[0] === "string" && ids[0].length > 0) return ids[0];
    return null;
  } catch {
    return null;
  }
}

/**
 * Record the block so the session-end hook can close it. Each block gets its own
 * file, which only the hook deletes, so no writer can lose another's row.
 */
export function remember(sessionId: string, block: string, label: string): void {
  mkdirSync(CACHE, { recursive: true });
  writeFileSync(
    join(CACHE, `${sessionId}.${randomUUID()}.json`),
    JSON.stringify({ block, rex_session: process.env.REX_SESSION, label }) + "\n",
    { flag: "wx" },
  );
}

async function main(): Promise<number> {
  const label = process.argv[2] ?? "[claude] job";
  const sessionId = process.argv[3] ?? "";
  const log = join(tmpdir(), `rex-mirror-${randomUUID()}.log`);
  writeFileSync(log, "", { flag: "wx", mode: 0o600 });
  const logf = openSync(log, "a");
  const nonce = randomBytes(8).toString("hex"); // the exit line names it, so command output cannot fake one
  let viewer: ViewerState = { kind: "skipped" };
  const openViewer = (): void => {
    const block = startViewer(label, log, nonce);
    if (block) {
      if (sessionId) remember(sessionId, block, label);
      viewer = { kind: "open", block };
    } else {
      viewer = { kind: "skipped" };
    }
  };
  if (process.env.REX_SESSION && which("rex")) {
    const delay = openDelayMs();
    if (delay === 0) {
      openViewer();
    } else {
      viewer = { kind: "pending", timer: setTimeout(openViewer, delay) };
    }
  }
  let tail = Buffer.alloc(0);
  const emit = (buf: Buffer): void => {
    writeSync(1, buf);
    writeSync(logf, buf);
  };
  const closeAndUnlinkLog = (): void => {
    try {
      closeSync(logf);
    } catch {
      // best-effort
    }
    try {
      unlinkSync(log);
    } catch {
      // already gone
    }
  };
  const settleLog = (code: number): void => {
    switch (viewer.kind) {
      case "pending":
        clearTimeout(viewer.timer);
        viewer = { kind: "skipped" };
        closeAndUnlinkLog();
        return;
      case "open":
        try {
          writeSync(logf, `\n__rex_mirror_exit_${nonce}=${code}\n`);
          closeSync(logf);
        } catch {
          // best-effort: the exit code still reaches the caller
        }
        return;
      case "skipped":
        closeAndUnlinkLog();
        return;
      default: {
        const _exhaustive: never = viewer;
        return _exhaustive;
      }
    }
  };
  const onSignal = (code: number): void => {
    try {
      emit(tail);
    } catch {
      // stdout may already be closed; the exit line still settles the block
    }
    settleLog(code);
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
  settleLog(rc);
  if (!m) console.error("rex_mirror: the command's exit status marker is missing");
  return rc;
}

if (isMain(import.meta.url)) main().then((rc) => process.exit(rc));
