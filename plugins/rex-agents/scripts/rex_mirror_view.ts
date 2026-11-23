import { spawnSync } from "node:child_process";
import { closeSync, openSync, readSync, unlinkSync, writeSync } from "node:fs";
import { isMain } from "./is_main.ts";

const CONTROL = /[\x00-\x1f\x7f-\x9f]/g;
const SGR_SEQUENCE = /\x1b\[[0-9;:]*m/;
const CONTROLS_EXCEPT_TAB_LF_CR = /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/;
const SGR_OR_CONTROL = new RegExp(`${SGR_SEQUENCE.source}|${CONTROLS_EXCEPT_TAB_LF_CR.source}`, "g");
// A waiter already running gets the final status without this delay. The using-rex skill promises a late waiter 1 s.
const STATUS_GRACE_MS = 1_000;
const CLOSE_TIMEOUT_MS = 5_000;

export function stripStatusSpoofing(text: string): string {
  return text.replace(SGR_OR_CONTROL, (m) => (m.startsWith("\x1b[") ? m : ""));
}

export function formatHeader(label: string, now: Date = new Date()): string {
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  return `\x1b[2m${label.replace(CONTROL, " ")} · started ${hh}:${mm}:${ss}\x1b[0m\n`;
}

export function status(state: string, msg: string): void {
  const b64 = Buffer.from(msg.replace(CONTROL, " "), "utf8").toString("base64");
  writeSync(1, `\x1b]7501;state=${state}:app=rex-mirror:msg=${b64}\x1b\\`);
}

// Rex sends SIGHUP to this process when its block closes, so nothing after a successful close runs.
function closeBlock(session: string, block: string): void {
  spawnSync("rex", ["block", "close", "-s", session, block], {
    stdio: "ignore",
    timeout: CLOSE_TIMEOUT_MS,
  });
}

async function main(): Promise<number> {
  const [log, label, unforgeableExitTag] = process.argv.slice(2);
  const escaped = unforgeableExitTag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const exitLine = new RegExp(`^__rex_mirror_exit_${escaped}=(\\d+)$`);
  status("working", label);
  writeSync(1, formatHeader(label));
  const fd = openSync(log, "r");
  const buf = Buffer.alloc(65536);
  const decoder = new TextDecoder("utf-8");
  let partial = "";
  for (;;) {
    const n = readSync(fd, buf, 0, buf.length, null);
    if (n === 0) {
      await new Promise<void>((resolve) => setTimeout(resolve, 200));
      continue;
    }
    partial += decoder.decode(buf.subarray(0, n), { stream: true });
    let idx = partial.indexOf("\n");
    while (idx !== -1) {
      const line = partial.slice(0, idx + 1);
      partial = partial.slice(idx + 1);
      const m = exitLine.exec(line.replace(/\n+$/, ""));
      if (m) {
        const rc = Number(m[1]);
        status(rc === 0 ? "done" : "error", `${label}: exit ${rc}`);
        closeSync(fd);
        unlinkSync(log);
        const session = process.env.REX_SESSION;
        const block = process.env.REX_BLOCK;
        if (session && block) {
          await new Promise<void>((resolve) => setTimeout(resolve, STATUS_GRACE_MS));
          closeBlock(session, block);
        }
        return 0;
      }
      writeSync(1, stripStatusSpoofing(line));
      idx = partial.indexOf("\n");
    }
  }
}

if (isMain(import.meta.url)) main().then((rc) => process.exit(rc));
