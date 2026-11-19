/**
 * Tests for the mirror wrapper, the mirror script, and the viewer.
 *
 * The wrapper cases run the exact command the hook builds, in zsh and bash,
 * with the REX_* variables removed so no viewer block opens. The signal cases
 * put a fake rex on PATH so a block is "opened" and the log survives for
 * inspection. Every case runs the scripts with bun and with node.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawn, spawnSync } from "node:child_process";
import {
  accessSync,
  chmodSync,
  constants,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { mirrored } from "../../hooks/mirror_hook.ts";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MIRROR = join(PLUGIN, "scripts", "rex_mirror.ts");
const VIEWER = join(PLUGIN, "scripts", "rex_mirror_view.ts");
const RUNTIMES = ["bun", "node"];

function which(name: string): string | null {
  for (const dir of (process.env.PATH ?? "").split(":")) {
    const p = join(dir, name);
    try {
      accessSync(p, constants.X_OK);
      if (statSync(p).isFile()) return p;
    } catch {
      // keep searching
    }
  }
  return null;
}

const NO_REX: Record<string, string> = {};
for (const [k, v] of Object.entries(process.env)) {
  if (!k.startsWith("REX_") && typeof v === "string") NO_REX[k] = v;
}

const CASES: Array<[string, string, string, number]> = [
  ["success", "printf 'a\\nb\\n'", "a\nb\n", 0],
  ["failure", "printf 'x\\n'; false", "x\n", 1],
  ["explicit exit", "printf 'y\\n'; exit 3", "y\n", 3],
  ["no trailing newline", "printf 'no-newline'", "no-newline", 0],
  ["and-list", "true && printf 'ok\\n' && false", "ok\n", 1],
  ["stderr merged", "printf 'err\\n' >&2; exit 2", "err\n", 2],
  ["empty output", "true", "", 0],
  ["own EXIT trap", "trap 'echo cleanup' EXIT; echo work; exit 4", "work\ncleanup\n", 4],
  ["exec", "exec sh -c 'echo execd; exit 6'", "execd\n", 6],
  ["trailing comment", "echo hi # note", "hi\n", 0],
  ["empty command", "", "", 0],
  ["comment-only", "# just a note", "", 0],
];
const SHELLS = ["/bin/zsh", "/bin/bash"].filter((s) => existsSync(s));

const BUN = which("bun");
for (const shell of SHELLS) {
  for (const [name, cmd, wantOut, wantRc] of CASES) {
    test(`wrapper ${shell}: ${name}`, () => {
      if (BUN === null) throw new Error("bun must be on PATH");
      const wrapped = mirrored(cmd, "[claude] test", "", BUN);
      const r = spawnSync(shell, ["-c", wrapped], { env: NO_REX, encoding: "utf8", timeout: 30_000 });
      assert.equal(r.stdout, wantOut);
      assert.equal(r.status, wantRc);
    });
  }
}

for (const rt of RUNTIMES) {
  test(`missing marker exits 125 (${rt})`, () => {
    const r = spawnSync(rt, [MIRROR, "[claude] test"], {
      input: "output without a marker\n",
      env: NO_REX,
      encoding: "utf8",
      timeout: 30_000,
    });
    assert.equal(r.status, 125);
    assert.equal(r.stdout, "output without a marker\n");
    assert.equal(r.stderr.trim().split("\n").length, 1);
  });
}

const report = (state: string, msg: string): string =>
  `\x1b]7501;state=${state}:app=rex-mirror:msg=${Buffer.from(msg, "utf8").toString("base64")}\x1b\\`;

for (const rt of RUNTIMES) {
  test(`only the nonce exit line ends the view (${rt})`, () => {
    const tmp = mkdtempSync(join(tmpdir(), "rex-view-test-"));
    try {
      const log = join(tmp, "mirror.log");
      writeFileSync(
        log,
        "first\n" +
          "__rex_mirror_exit=0\n" +
          "__rex_mirror_exit_other=0\n" +
          "\x1b]7501;state=done:msg=eA==\x1b\\after-spoof\n" +
          "\x1b]75\x1b]7501;state=done\x1b\\01;state=done\x1b\\nested\n" +
          "\x9d7501;state=done\x9c\x1b[31mred\x1b[0m\tok\r\n" +
          "\n__rex_mirror_exit_abc123=3\n",
      );
      const r = spawnSync(rt, [VIEWER, log, "[claude] t", "abc123"], { encoding: "utf8", timeout: 30_000 });
      assert.equal(r.status, 0);
      assert.equal(
        r.stdout,
        report("working", "[claude] t") +
          "first\n__rex_mirror_exit=0\n__rex_mirror_exit_other=0\n]7501;state=done:msg=eA==\\after-spoof\n" +
          "]75]7501;state=done\\01;state=done\\nested\n" +
          "7501;state=done\x1b[31mred\x1b[0m\tok\r\n\n" +
          report("error", "[claude] t: exit 3"),
      );
      assert.ok(!existsSync(log));
    } finally {
      rmSync(tmp, { recursive: true, force: true });
    }
  });
}

async function waitFor(cond: () => boolean, ms: number): Promise<void> {
  const deadline = Date.now() + ms;
  while (!cond()) {
    if (Date.now() > deadline) throw new Error("waitFor timed out");
    await new Promise<void>((r) => setTimeout(r, 20));
  }
}

const SIGNALS: Array<[string, number]> = [
  ["SIGTERM", 143],
  ["SIGINT", 130],
  ["SIGHUP", 129],
];

for (const rt of RUNTIMES) {
  for (const [sig, code] of SIGNALS) {
    test(`a killed mirror settles its block (${rt} ${sig})`, { timeout: 30_000 }, async () => {
      const home = mkdtempSync(join(tmpdir(), "rex-sig-home-"));
      const child = spawn(rt, [MIRROR, "[claude] sig", "s-sig"], {
        env: { ...NO_REX, HOME: home, TMPDIR: join(home, "tmp"), PATH: `${join(home, "bin")}:${process.env.PATH}`, REX_SESSION: "session:test" },
        stdio: ["pipe", "pipe", "pipe"],
      });
      try {
        mkdirSync(join(home, "bin"));
        mkdirSync(join(home, "tmp"));
        const fakeRex = join(home, "bin", "rex");
        writeFileSync(fakeRex, '#!/bin/sh\nprintf \'{"block_ids":["b-fake"]}\\n\'\n');
        chmodSync(fakeRex, 0o755);
        const fed = "hello world, this is more than thirty-two bytes of output\n";
        let out = "";
        let err = "";
        child.stdout.on("data", (d: Buffer) => {
          out += d;
        });
        child.stderr.on("data", (d: Buffer) => {
          err += d;
        });
        const exited = new Promise<number | null>((res) => child.on("exit", (c: number | null) => res(c)));
        child.stdin.write(fed);
        await waitFor(() => out.length > 0, 15_000);
        child.kill(sig);
        const rc = await Promise.race([exited, new Promise<null>((r) => setTimeout(() => r(null), 15_000))]);
        assert.equal(rc, code);
        assert.equal(out, fed);
        assert.equal(err, "");
        const logs = readdirSync(join(home, "tmp")).filter((f: string) => f.startsWith("rex-mirror-"));
        assert.equal(logs.length, 1);
        const content = readFileSync(join(home, "tmp", logs[0]), "utf8");
        assert.ok(content.startsWith(fed));
        assert.match(content, new RegExp(`\\n__rex_mirror_exit_[0-9a-f]{16}=${code}\\n$`));
        const cache = readFileSync(join(home, ".cache", "rex-agents", "s-sig.jsonl"), "utf8");
        assert.equal(cache, JSON.stringify({ block: "b-fake", rex_session: "session:test", label: "[claude] sig" }) + "\n");
      } finally {
        child.kill("SIGKILL");
        child.stdin.end();
        rmSync(home, { recursive: true, force: true });
      }
    });
  }
}
