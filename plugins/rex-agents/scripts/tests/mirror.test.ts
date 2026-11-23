import assert from "node:assert/strict";
import { test } from "node:test";
import { spawn, spawnSync } from "node:child_process";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { formatHeader } from "../rex_mirror_view.ts";
import { openDelayMs } from "../rex_mirror.ts";
import { mirrored } from "../../hooks/mirror_hook.ts";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const MIRROR = join(PLUGIN, "scripts", "rex_mirror.ts");
const VIEWER = join(PLUGIN, "scripts", "rex_mirror_view.ts");
const RUNTIMES = ["bun", "node"];
const skipFor = (rt: string): string | false =>
  spawnSync(rt, ["--version"], { stdio: "ignore" }).status === 0 ? false : `${rt} is not on PATH`;
const flagsFor = (rt: string): string[] => (rt === "node" ? ["--disable-warning=ExperimentalWarning"] : []);

const NO_REX: Record<string, string> = {};
for (const [k, v] of Object.entries(process.env)) {
  if (!k.startsWith("REX_") && typeof v === "string") NO_REX[k] = v;
}

const CASES: Array<[string, string, string, number]> = [
  ["success", "printf 'a\\nb\\n'", "a\nb\n", 0],
  ["failure", "printf 'x\\n'; false", "x\n", 1],
  ["explicit exit", "printf 'y\\n'; exit 3", "y\n", 3],
  ["no trailing newline", "printf 'no-newline'", "no-newline", 0],
  ["stderr merged", "printf 'err\\n' >&2; exit 2", "err\n", 2],
  ["empty output", "true", "", 0],
  ["own EXIT trap", "trap 'echo cleanup' EXIT; echo work; exit 4", "work\ncleanup\n", 4],
  ["exec", "exec sh -c 'echo execd; exit 6'", "execd\n", 6],
  ["trailing comment", "echo hi # note", "hi\n", 0],
  ["empty command", "", "", 0],
  ["comment-only", "# just a note", "", 0],
  ["multibyte output before the marker", "printf 'é→😀'", "é→😀", 0],
];
const SHELLS = ["/bin/zsh", "/bin/bash"].filter((s) => existsSync(s));

for (const shell of SHELLS) {
  for (const [name, cmd, wantOut, wantRc] of CASES) {
    test(`wrapper ${shell}: ${name}`, () => {
      const wrapped = mirrored(cmd, "[claude] test", "", process.execPath);
      const r = spawnSync(shell, ["-c", wrapped], { env: NO_REX, encoding: "utf8", timeout: 30_000 });
      assert.equal(r.stdout, wantOut);
      assert.equal(r.stderr, "", "the runtime prints no warning into the command's stderr");
      assert.equal(r.status, wantRc);
    });
  }
}

for (const rt of RUNTIMES) {
  test(`missing marker exits 125 (${rt})`, { skip: skipFor(rt) }, () => {
    const r = spawnSync(rt, [...flagsFor(rt), MIRROR, "[claude] test"], {
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

function stripHeader(out: string, label: string): string {
  const prefix = report("working", label);
  assert.ok(out.startsWith(prefix), "stdout starts with the working OSC 7501 report");
  const rest = out.slice(prefix.length);
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const m = new RegExp(`^\\x1b\\[2m${escaped} · started \\d{2}:\\d{2}:\\d{2}\\x1b\\[0m\\n`).exec(rest);
  assert.ok(m, `expected dim header after working status, got: ${JSON.stringify(rest.slice(0, 80))}`);
  return rest.slice(m[0].length);
}

test("formatHeader renders dim label and local HH:MM:SS", () => {
  const dt = new Date(2026, 10, 22, 7, 5, 9);
  assert.equal(formatHeader("[claude] build", dt), "\x1b[2m[claude] build · started 07:05:09\x1b[0m\n");
  assert.equal(
    formatHeader("[claude] \x1b]7501;x\x1b\\\x1b[31mred\x1b[0m\r\nok", dt),
    "\x1b[2m[claude]  ]7501;x \\ [31mred [0m  ok · started 07:05:09\x1b[0m\n",
  );
});

test("openDelayMs parses non-negative finite numbers and falls back to 1500", () => {
  assert.equal(openDelayMs({}), 1_500);
  assert.equal(openDelayMs({ REX_AGENTS_MIRROR_DELAY_MS: "" }), 1_500);
  assert.equal(openDelayMs({ REX_AGENTS_MIRROR_DELAY_MS: "0" }), 0);
  assert.equal(openDelayMs({ REX_AGENTS_MIRROR_DELAY_MS: "250.9" }), 250);
  assert.equal(openDelayMs({ REX_AGENTS_MIRROR_DELAY_MS: "-1" }), 1_500);
  assert.equal(openDelayMs({ REX_AGENTS_MIRROR_DELAY_MS: "nope" }), 1_500);
});

for (const rt of RUNTIMES) {
  test(`only the exit tag line ends the view (${rt})`, { skip: skipFor(rt) }, () => {
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
      const r = spawnSync(rt, [VIEWER, log, "[claude] t", "abc123"], { env: NO_REX, encoding: "utf8", timeout: 30_000 });
      assert.equal(r.status, 0);
      assert.equal(
        stripHeader(r.stdout, "[claude] t"),
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

for (const rt of RUNTIMES) {
  test(`an exited view closes its own block (${rt})`, { skip: skipFor(rt) }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-view-close-"));
    try {
      const bin = join(home, "bin");
      mkdirSync(bin);
      writeFileSync(join(bin, "rex"), '#!/bin/sh\nprintf \'%s\\n\' "$@" >> "$HOME/rex-args"\n');
      chmodSync(join(bin, "rex"), 0o755);
      const log = join(home, "mirror.log");
      writeFileSync(log, "out\n\n__rex_mirror_exit_abc123=7\n");
      const r = spawnSync(rt, [...flagsFor(rt), VIEWER, log, "[claude] t", "abc123"], {
        env: { ...NO_REX, HOME: home, PATH: `${bin}:${process.env.PATH}`, REX_SESSION: "session:t", REX_BLOCK: "block:b" },
        encoding: "utf8",
        timeout: 30_000,
      });
      assert.equal(r.status, 0);
      assert.equal(stripHeader(r.stdout, "[claude] t"), "out\n\n" + report("error", "[claude] t: exit 7"));
      assert.equal(readFileSync(join(home, "rex-args"), "utf8"), "block\nclose\n-s\nsession:t\nblock:b\n");
      assert.ok(!existsSync(log));
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test(`an exited view without both rex ids closes nothing (${rt})`, { skip: skipFor(rt) }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-view-noclose-"));
    try {
      const bin = join(home, "bin");
      mkdirSync(bin);
      writeFileSync(join(bin, "rex"), '#!/bin/sh\nprintf \'%s\\n\' "$@" >> "$HOME/rex-args"\n');
      chmodSync(join(bin, "rex"), 0o755);
      const log = join(home, "mirror.log");
      for (const ids of [{}, { REX_SESSION: "session:t" }, { REX_BLOCK: "block:b" }]) {
        writeFileSync(log, "out\n\n__rex_mirror_exit_abc123=0\n");
        const r = spawnSync(rt, [...flagsFor(rt), VIEWER, log, "[claude] t", "abc123"], {
          env: { ...NO_REX, HOME: home, PATH: `${bin}:${process.env.PATH}`, ...ids },
          encoding: "utf8",
          timeout: 30_000,
        });
        assert.equal(r.status, 0);
        assert.ok(!existsSync(join(home, "rex-args")), JSON.stringify(ids));
      }
    } finally {
      rmSync(home, { recursive: true, force: true });
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

function writeFakeRex(bin: string, opts: { failNewLayer?: boolean; newLayer?: string; run?: string } = {}): void {
  const newLayerBody =
    opts.newLayer ?? (opts.failNewLayer ? "exit 1" : 'printf \'{"layer_id":"layer:fake","block_ids":["b-fake"]}\\n\'');
  const script = `#!/bin/sh
printf '%s\\t' "$@" >> "$HOME/rex-calls"
printf '\\n' >> "$HOME/rex-calls"
if [ "$1" = "block" ] && [ "$2" = "inspect" ]; then
  printf '{"block":{"id":"%s","window_id":"win:agent"}}\\n' "$3"
elif [ "$1" = "api" ] && [ "$2" = "call" ] && [ "$5" = "session.new_layer" ]; then
  ${newLayerBody}
elif [ "$1" = "api" ] && [ "$2" = "call" ] && [ "$5" = "session.set_layer_state" ]; then
  printf '{}\\n'
elif [ "$1" = "run" ]; then
  ${opts.run ?? 'printf \'{"block_ids":["b-fallback"]}\\n\''}
fi
`;
  const fakeRex = join(bin, "rex");
  writeFileSync(fakeRex, script);
  chmodSync(fakeRex, 0o755);
}

function readRexCalls(home: string): string[][] {
  const p = join(home, "rex-calls");
  if (!existsSync(p)) return [];
  return readFileSync(p, "utf8")
    .trimEnd()
    .split("\n")
    .filter(Boolean)
    .map((line) => line.replace(/\t$/, "").split("\t"));
}

function readRows(home: string, session: string): unknown[] {
  const dir = join(home, ".cache", "rex-agents");
  return readdirSync(dir)
    .filter((f: string) => f.startsWith(`${session}.`) && f.endsWith(".json"))
    .map((f: string) => JSON.parse(readFileSync(join(dir, f), "utf8")));
}

const SIGNALS: Array<[NodeJS.Signals, number]> = [
  ["SIGTERM", 143],
  ["SIGINT", 130],
  ["SIGHUP", 129],
];

for (const rt of RUNTIMES) {
  for (const [sig, code] of SIGNALS) {
    test(`a killed mirror settles its block (${rt} ${sig})`, { timeout: 30_000, skip: skipFor(rt) }, async () => {
      const home = mkdtempSync(join(tmpdir(), "rex-sig-home-"));
      mkdirSync(join(home, "bin"));
      mkdirSync(join(home, "tmp"));
      writeFakeRex(join(home, "bin"));
      const child = spawn(rt, [...flagsFor(rt), MIRROR, "[claude] sig", "s-sig"], {
        env: {
          ...NO_REX,
          HOME: home,
          TMPDIR: join(home, "tmp"),
          PATH: `${join(home, "bin")}:${process.env.PATH}`,
          REX_SESSION: "session:test",
          REX_AGENTS_MIRROR_DELAY_MS: "0",
        },
        stdio: ["pipe", "pipe", "pipe"],
      });
      try {
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
        const calls = readRexCalls(home);
        const newLayerCall = calls.find((c) => c[0] === "api" && c[4] === "session.new_layer");
        assert.ok(newLayerCall, "expected session.new_layer call");
        const params = JSON.parse(newLayerCall[5]);
        const viewerArgs: string[] = params.layout.block.options.command;
        assert.deepEqual(
          viewerArgs.slice(1, 2),
          rt === "node" ? ["--disable-warning=ExperimentalWarning"] : [VIEWER],
          "node runs the viewer with the warning suppressed; bun needs no flag",
        );
        const cacheDir = join(home, ".cache", "rex-agents");
        const rows = readdirSync(cacheDir);
        assert.equal(rows.length, 1);
        assert.match(rows[0], /^s-sig\.[0-9a-f-]{36}\.json$/);
        const row = readFileSync(join(cacheDir, rows[0]), "utf8");
        assert.equal(row, JSON.stringify({ block: "b-fake", rex_session: "session:test", label: "[claude] sig" }) + "\n");
      } finally {
        child.kill("SIGKILL");
        child.stdin.end();
        rmSync(home, { recursive: true, force: true });
      }
    });
  }

  test(`fast command skips rex and removes temp log (${rt})`, { skip: skipFor(rt) }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-fast-home-"));
    try {
      mkdirSync(join(home, "bin"));
      mkdirSync(join(home, "tmp"));
      writeFakeRex(join(home, "bin"));
      const r = spawnSync(rt, [...flagsFor(rt), MIRROR, "[claude] fast", "s-fast"], {
        input: "quick\n\n__rex_rc=0\n",
        env: {
          ...NO_REX,
          HOME: home,
          TMPDIR: join(home, "tmp"),
          PATH: `${join(home, "bin")}:${process.env.PATH}`,
          REX_SESSION: "session:test",
          REX_AGENTS_MIRROR_DELAY_MS: "5000",
        },
        encoding: "utf8",
        timeout: 30_000,
      });
      assert.equal(r.status, 0);
      assert.equal(r.stdout, "quick\n");
      assert.equal(r.stderr, "");
      assert.deepEqual(readRexCalls(home), []);
      assert.deepEqual(
        readdirSync(join(home, "tmp")).filter((f: string) => f.startsWith("rex-mirror-")),
        [],
      );
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test(`delayed open creates a minimized floating layer in REX_BLOCK window (${rt})`, { timeout: 30_000, skip: skipFor(rt) }, async () => {
    const home = mkdtempSync(join(tmpdir(), "rex-delay-home-"));
    mkdirSync(join(home, "bin"));
    mkdirSync(join(home, "tmp"));
    writeFakeRex(join(home, "bin"));
    const child = spawn(rt, [...flagsFor(rt), MIRROR, "[claude] delayed", "s-delay"], {
      env: {
        ...NO_REX,
        HOME: home,
        TMPDIR: join(home, "tmp"),
        PATH: `${join(home, "bin")}:${process.env.PATH}`,
        REX_SESSION: "session:test",
        REX_BLOCK: "block:agent",
        REX_AGENTS_MIRROR_DELAY_MS: "100",
      },
      stdio: ["pipe", "pipe", "pipe"],
    });
    try {
      let out = "";
      let err = "";
      child.stdout.on("data", (d: Buffer) => {
        out += d;
      });
      child.stderr.on("data", (d: Buffer) => {
        err += d;
      });
      const exited = new Promise<number | null>((res) => child.on("exit", (c: number | null) => res(c)));
      child.stdin.write("before delay\n");
      await waitFor(() => readRexCalls(home).some((c) => c[0] === "api" && c[4] === "session.set_layer_state"), 15_000);
      child.stdin.end("after delay\n\n__rex_rc=0\n");
      const rc = await Promise.race([exited, new Promise<null>((r) => setTimeout(() => r(null), 15_000))]);
      assert.equal(rc, 0);
      assert.equal(out, "before delay\nafter delay\n");
      assert.equal(err, "");
      const calls = readRexCalls(home);
      assert.deepEqual(calls[0], ["block", "inspect", "block:agent", "-s", "session:test", "--json"]);
      assert.equal(calls[1][0], "api");
      assert.equal(calls[1][4], "session.new_layer");
      const layerParams = JSON.parse(calls[1][5]);
      assert.equal(layerParams.window_id, "win:agent");
      assert.equal(layerParams.focus, false);
      assert.deepEqual(layerParams.bounds, [0.15, 0.15, 0.7, 0.7]);
      assert.equal(layerParams.layout.block.label, "[claude] delayed");
      assert.equal(layerParams.layout.block.options.shell, "none");
      assert.deepEqual(layerParams.layout.block.options.exit, { on_completion: false });
      assert.equal(calls[2][0], "api");
      assert.equal(calls[2][4], "session.set_layer_state");
      assert.deepEqual(JSON.parse(calls[2][5]), { layer_id: "layer:fake", state: "minimized" });
      const logs = readdirSync(join(home, "tmp")).filter((f: string) => f.startsWith("rex-mirror-"));
      assert.equal(logs.length, 1);
      const logText = readFileSync(join(home, "tmp", logs[0]), "utf8");
      assert.ok(logText.startsWith("before delay\nafter delay\n"));
      assert.match(logText, /\n__rex_mirror_exit_[0-9a-f]{16}=0\n$/);
      assert.deepEqual(readRows(home, "s-delay"), [{ block: "b-fake", rex_session: "session:test", label: "[claude] delayed" }]);
    } finally {
      child.kill("SIGKILL");
      child.stdin.end();
      rmSync(home, { recursive: true, force: true });
    }
  });

  test(`falls back to rex run when session.new_layer fails (${rt})`, { skip: skipFor(rt) }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-fallback-home-"));
    try {
      mkdirSync(join(home, "bin"));
      mkdirSync(join(home, "tmp"));
      writeFakeRex(join(home, "bin"), { failNewLayer: true });
      const r = spawnSync(rt, [...flagsFor(rt), MIRROR, "[claude] fb", "s-fb"], {
        input: "fallback out\n\n__rex_rc=0\n",
        env: {
          ...NO_REX,
          HOME: home,
          TMPDIR: join(home, "tmp"),
          PATH: `${join(home, "bin")}:${process.env.PATH}`,
          REX_SESSION: "session:test",
          REX_AGENTS_MIRROR_DELAY_MS: "0",
        },
        encoding: "utf8",
        timeout: 30_000,
      });
      assert.equal(r.status, 0);
      assert.equal(r.stdout, "fallback out\n");
      assert.equal(r.stderr, "");
      const calls = readRexCalls(home);
      assert.equal(calls.length, 2);
      assert.equal(calls[0][0], "api");
      assert.equal(calls[0][4], "session.new_layer");
      assert.deepEqual(calls[1].slice(0, 10), [
        "run",
        "-s",
        "session:test",
        "--focus=false",
        "--keep-open",
        "--shell=none",
        "--label",
        "[claude] fb",
        "--json",
        "--",
      ]);
      assert.deepEqual(readRows(home, "s-fb"), [{ block: "b-fallback", rex_session: "session:test", label: "[claude] fb" }]);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  const runOpen = (home: string, fake: { failNewLayer?: boolean; newLayer?: string; run?: string }) => {
    mkdirSync(join(home, "bin"));
    mkdirSync(join(home, "tmp"));
    writeFakeRex(join(home, "bin"), fake);
    const r = spawnSync(rt, [...flagsFor(rt), MIRROR, "[claude] late", "s-late"], {
      input: "late out\n\n__rex_rc=4\n",
      env: {
        ...NO_REX,
        HOME: home,
        TMPDIR: join(home, "tmp"),
        PATH: `${join(home, "bin")}:${process.env.PATH}`,
        REX_SESSION: "session:test",
        REX_AGENTS_MIRROR_DELAY_MS: "0",
      },
      encoding: "utf8",
      timeout: 30_000,
    });
    const logs = readdirSync(join(home, "tmp")).filter((f: string) => f.startsWith("rex-mirror-"));
    const text = logs.map((f: string) => readFileSync(join(home, "tmp", f), "utf8"));
    return { r, calls: readRexCalls(home), text };
  };

  test(`a new_layer client that dies before its reply opens no fallback block (${rt})`, { skip: skipFor(rt) }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-late-layer-home-"));
    try {
      const { r, calls, text } = runOpen(home, { newLayer: "exit 143" });
      assert.equal(r.status, 4);
      assert.equal(r.stdout, "late out\n");
      assert.deepEqual(calls.map((c) => c[0] === "api" ? c[4] : c[0]), ["session.new_layer"]);
      assert.equal(text.length, 1, "the log stays for a viewer that may have opened");
      assert.match(text[0], /\n__rex_mirror_exit_[0-9a-f]{16}=4\n$/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  test(`a rex run client that dies before its reply still gets the exit line (${rt})`, { skip: skipFor(rt) }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-late-run-home-"));
    try {
      const { r, calls, text } = runOpen(home, { failNewLayer: true, run: "exit 143" });
      assert.equal(r.status, 4);
      assert.deepEqual(calls.map((c) => c[0] === "api" ? c[4] : c[0]), ["session.new_layer", "run"]);
      assert.equal(text.length, 1);
      assert.match(text[0], /\n__rex_mirror_exit_[0-9a-f]{16}=4\n$/);
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });

  for (const delay of ["0", "100"]) test(`at delay ${delay}, a stop during the open still writes the exit line 143 (${rt})`, { timeout: 30_000, skip: skipFor(rt) }, async () => {
    const home = mkdtempSync(join(tmpdir(), "rex-stop-open-home-"));
    mkdirSync(join(home, "bin"));
    mkdirSync(join(home, "tmp"));
    writeFakeRex(join(home, "bin"), { newLayer: "sleep 20" });
    const child = spawn(rt, [...flagsFor(rt), MIRROR, "[claude] stop", "s-stop"], {
      env: {
        ...NO_REX,
        HOME: home,
        TMPDIR: join(home, "tmp"),
        PATH: `${join(home, "bin")}:${process.env.PATH}`,
        REX_SESSION: "session:test",
        REX_AGENTS_MIRROR_DELAY_MS: delay,
      },
      stdio: ["pipe", "pipe", "pipe"],
      detached: true,
    });
    try {
      const exited = new Promise<number | null>((res) => child.on("exit", (c: number | null) => res(c)));
      child.stdin.write("before stop\n");
      await waitFor(() => readRexCalls(home).some((c) => c[4] === "session.new_layer"), 15_000);
      process.kill(-(child.pid as number), "SIGTERM");
      child.stdin.end();
      const rc = await Promise.race([exited, new Promise<null>((r) => setTimeout(() => r(null), 15_000))]);
      assert.equal(rc, 143);
      const logs = readdirSync(join(home, "tmp")).filter((f: string) => f.startsWith("rex-mirror-"));
      assert.equal(logs.length, 1);
      assert.match(readFileSync(join(home, "tmp", logs[0]), "utf8"), /\n__rex_mirror_exit_[0-9a-f]{16}=143\n$/);
    } finally {
      try {
        process.kill(-(child.pid as number), "SIGKILL");
      } catch {}
      rmSync(home, { recursive: true, force: true });
    }
  });
}
