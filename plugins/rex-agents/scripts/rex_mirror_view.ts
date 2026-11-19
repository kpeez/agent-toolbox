/**
 * Show a mirror log in a Rex block and report its state with OSC 7501.
 *
 * Usage: bun rex_mirror_view.ts LOG LABEL NONCE
 *
 * Reports `working` at start. When rex_mirror.ts writes its exit line
 * `__rex_mirror_exit_<NONCE>=N`, reports `done` for status 0 or `error`
 * otherwise, with "LABEL: exit N" as the message, then deletes the log and
 * exits. Run the block with --keep-open so the record stays. OSC 7501 sequences
 * in the command's output cannot reach the terminal: the viewer keeps SGR
 * color sequences, tab, newline, and carriage return, and removes every other
 * C0 or C1 control, so only the viewer sets the block's status.
 */

import { closeSync, openSync, readSync, unlinkSync, writeSync } from "node:fs";

const CONTROL = /[\x00-\x1f\x7f-\x9f]/g;
// An SGR color sequence, kept; or any other C0 or C1 control (ESC included), removed.
const UNSAFE = /\x1b\[[0-9;:]*m|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]/g;

export function safe(text: string): string {
  return text.replace(UNSAFE, (m) => (m.startsWith("\x1b[") ? m : ""));
}

export function status(state: string, msg: string): void {
  const b64 = Buffer.from(msg.replace(CONTROL, " "), "utf8").toString("base64");
  writeSync(1, `\x1b]7501;state=${state}:app=rex-mirror:msg=${b64}\x1b\\`);
}

async function main(): Promise<number> {
  const [log, label, nonce] = process.argv.slice(2);
  const escaped = nonce.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const exitLine = new RegExp(`^__rex_mirror_exit_${escaped}=(\\d+)$`);
  status("working", label);
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
        return 0;
      }
      writeSync(1, safe(line));
      idx = partial.indexOf("\n");
    }
  }
}

if (import.meta.main) main().then((rc) => process.exit(rc));
