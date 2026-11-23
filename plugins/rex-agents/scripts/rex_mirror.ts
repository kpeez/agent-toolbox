import { closeSync, mkdirSync, openSync, renameSync, unlinkSync, writeFileSync, writeSync, accessSync, constants, statSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import { spawnSync } from "node:child_process";
import type { SpawnSyncReturns } from "node:child_process";
import { fileURLToPath } from "node:url";
import { isMain } from "./is_main.ts";
import { runtimeFlags } from "./runtime_flags.ts";

const MARKER = /\n__rex_rc=(\d+)\n\n?$/;
const TAIL_LONGER_THAN_MARKER = 32;
const NO_MARKER = 125;
const OPEN_DELAY_MS = 1_500;
const FLOAT_BOUNDS: readonly [number, number, number, number] = [0.15, 0.15, 0.7, 0.7];
const CACHE = join(homedir(), ".cache", "rex-agents");

type ViewerState =
  | { kind: "pending"; timer: ReturnType<typeof setTimeout> }
  | { kind: "open" }
  | { kind: "maybeOpen" }
  | { kind: "skipped" };

export type Opened = { kind: "open"; block: string } | { kind: "none" } | { kind: "maybeOpen" };
const NONE: Opened = { kind: "none" };
const MAYBE_OPEN: Opened = { kind: "maybeOpen" };

function exitedBySignal(status: number): boolean {
  return status >= 128;
}

function diedBeforeReply(r: SpawnSyncReturns<string>): boolean {
  const code = (r.error as NodeJS.ErrnoException | undefined)?.code;
  return r.signal !== null || code === "ETIMEDOUT" || (r.status !== null && exitedBySignal(r.status));
}

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
    } catch {}
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

export function startViewer(label: string, log: string, unforgeableExitTag: string): Opened {
  const rex = which("rex");
  const session = process.env.REX_SESSION;
  if (!rex || !session) return NONE;
  const viewer = resolve(dirname(fileURLToPath(import.meta.url)), "rex_mirror_view.ts");
  const command = [process.execPath, ...runtimeFlags(), viewer, log, label, unforgeableExitTag];
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
  if (diedBeforeReply(layer)) return MAYBE_OPEN;
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
        return { kind: "open", block: parsed.block_ids[0] };
      }
    } catch {}
    return MAYBE_OPEN;
  }
  const r = spawnSync(
    rex,
    ["run", "-s", session, "--focus=false", "--keep-open", "--shell=none", "--label", label, "--json", "--", ...command],
    { encoding: "utf8", timeout: 15_000 },
  );
  if (diedBeforeReply(r)) return MAYBE_OPEN;
  if (r.error || r.status !== 0) return NONE;
  try {
    const parsed: unknown = JSON.parse(r.stdout);
    const ids = isRecord(parsed) ? parsed.block_ids : null;
    if (Array.isArray(ids) && typeof ids[0] === "string" && ids[0].length > 0) return { kind: "open", block: ids[0] };
  } catch {}
  return MAYBE_OPEN;
}

export function remember(sessionId: string, block: string, label: string): void {
  mkdirSync(CACHE, { recursive: true });
  // The temp name does not start with the session ID, so drainLegacyList never deletes it.
  const temp = join(CACHE, `.${randomUUID()}.tmp`);
  writeFileSync(temp, JSON.stringify({ block, rex_session: process.env.REX_SESSION, label }) + "\n");
  renameSync(temp, join(CACHE, `${sessionId}.${randomUUID()}.json`));
}

// latin1 maps each byte to one UTF-16 code unit, so the match index is a byte offset into tail.
function markerAt(tail: Buffer): { rc: number; offset: number } | null {
  const match = MARKER.exec(tail.toString("latin1"));
  return match ? { rc: Number(match[1]), offset: match.index } : null;
}

// A stop during an open with no handler kills the mirror before it writes the exit line, and the block shows
// working forever. Only this function returns the open, so no code can open a block before the handlers exist.
function withSignalHandlers(onSignal: (code: number) => void, open: () => void): () => void {
  process.on("SIGTERM", () => onSignal(143));
  process.on("SIGINT", () => onSignal(130));
  process.on("SIGHUP", () => onSignal(129));
  return open;
}

async function main(): Promise<number> {
  const label = process.argv[2] ?? "[claude] job";
  const sessionId = process.argv[3] ?? "";
  const log = join(tmpdir(), `rex-mirror-${randomUUID()}.log`);
  writeFileSync(log, "", { flag: "wx", mode: 0o600 });
  const logf = openSync(log, "a");
  const unforgeableExitTag = randomBytes(8).toString("hex");
  let viewer: ViewerState = { kind: "skipped" };
  let tail = Buffer.alloc(0);
  const emit = (buf: Buffer): void => {
    writeSync(1, buf);
    writeSync(logf, buf);
  };
  const closeAndUnlinkLog = (): void => {
    try {
      closeSync(logf);
    } catch {}
    try {
      unlinkSync(log);
    } catch {}
  };
  const settleLog = (code: number): void => {
    switch (viewer.kind) {
      case "pending":
        clearTimeout(viewer.timer);
        viewer = { kind: "skipped" };
        closeAndUnlinkLog();
        return;
      case "open":
      case "maybeOpen":
        try {
          writeSync(logf, `\n__rex_mirror_exit_${unforgeableExitTag}=${code}\n`);
          closeSync(logf);
        } catch {}
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
    } catch {}
    settleLog(code);
    process.exit(code);
  };
  const openViewer = withSignalHandlers(onSignal, (): void => {
    const opened = startViewer(label, log, unforgeableExitTag);
    if (opened.kind === "open" && sessionId) remember(sessionId, opened.block, label);
    viewer = opened.kind === "none" ? { kind: "skipped" } : { kind: opened.kind };
  });
  if (process.env.REX_SESSION && which("rex")) {
    const delay = openDelayMs();
    if (delay === 0) {
      openViewer();
    } else {
      viewer = { kind: "pending", timer: setTimeout(openViewer, delay) };
    }
  }
  for await (const chunk of process.stdin) {
    tail = Buffer.concat([tail, chunk]);
    if (tail.length > TAIL_LONGER_THAN_MARKER) {
      emit(tail.subarray(0, tail.length - TAIL_LONGER_THAN_MARKER));
      tail = tail.subarray(tail.length - TAIL_LONGER_THAN_MARKER);
    }
  }
  // A stop during a synchronous open leaves both the signal and the end of input pending.
  // Let a pending signal handler run first, so the block reports 143, not a missing marker.
  await new Promise<void>((resolve) => setImmediate(resolve));
  const marker = markerAt(tail);
  const rc = marker ? marker.rc : NO_MARKER;
  emit(marker ? tail.subarray(0, marker.offset) : tail);
  settleLog(rc);
  if (!marker) console.error("rex_mirror: the command's exit status marker is missing");
  return rc;
}

if (isMain(import.meta.url)) main().then((rc) => process.exit(rc));
