/**
 * Tests for the hooks, run as processes the way Claude Code runs them.
 *
 * The mirror cases feed the hook a PreToolUse event and run the command it
 * returns in sh, with a fake rex on PATH that logs its calls. The session-end
 * cases write rows with the real `remember` and run the hook against a fake
 * rex and a temporary HOME. Each case runs a hook with bun or node, or both,
 * which proves the erasable syntax and the node: APIs run without bun.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOKS = join(PLUGIN, "hooks");
const MIRROR = join(PLUGIN, "scripts", "rex_mirror.ts");

const NO_REX: Record<string, string> = {};
for (const [k, v] of Object.entries(process.env)) {
  if (!k.startsWith("REX_") && typeof v === "string") NO_REX[k] = v;
}

const locate = (rt: string): string => spawnSync("sh", ["-c", 'command -v "$0"', rt], { encoding: "utf8" }).stdout.trim();
const flagsFor = (rt: string): string[] => (basename(rt) === "node" ? ["--disable-warning=ExperimentalWarning"] : []);

function event(
  command = "make test",
  background: boolean | null = true,
  extra: Record<string, unknown> = {},
): { tool_input: Record<string, unknown> } & Record<string, unknown> {
  const toolInput: Record<string, unknown> = { command, description: "Run the tests", timeout: 600000 };
  if (background !== null) toolInput.run_in_background = background;
  return { tool_name: "Bash", session_id: "s-1", permission_mode: "auto", tool_input: toolInput, ...extra };
}

const ENV = { REX_SESSION: "session:x" };
const LAYER_REX = `#!/bin/sh
printf '%s\\t' "$@" >> "$HOME/rex-calls"
printf '\\n' >> "$HOME/rex-calls"
[ "$5" = session.new_layer ] && printf '{"layer_id":"layer:1","block_ids":["b-1"]}\\n'
exit 0
`;

/** A scratch HOME and TMPDIR, and a PATH with the fake rex and no bun or node. */
type Sandbox = { home: string; tmp: string; path: string };

function withSandbox(run: (sb: Sandbox) => void): void {
  const home = mkdtempSync(join(tmpdir(), "rex-hook-"));
  try {
    mkdirSync(join(home, "bin"));
    mkdirSync(join(home, "tmp"));
    writeFileSync(join(home, "bin", "rex"), LAYER_REX);
    chmodSync(join(home, "bin", "rex"), 0o755);
    run({ home, tmp: join(home, "tmp"), path: `${join(home, "bin")}:/usr/bin:/bin` });
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
}

/** Run mirror_hook.ts on one event; return its updatedInput, or null when it leaves the call alone. */
function runHook(
  sb: Sandbox,
  e: Record<string, unknown>,
  env: Record<string, string> = ENV,
  rt = process.execPath,
  path = sb.path,
): Record<string, unknown> | null {
  const r = spawnSync(rt, [...flagsFor(rt), join(HOOKS, "mirror_hook.ts")], {
    input: JSON.stringify(e),
    env: { ...NO_REX, PATH: path, ...env },
    encoding: "utf8",
    timeout: 30_000,
  });
  assert.equal(r.status, 0, r.stderr);
  if (r.stdout === "") return null;
  const spec = JSON.parse(r.stdout).hookSpecificOutput;
  assert.equal(spec.hookEventName, "PreToolUse");
  assert.ok(!("permissionDecision" in spec));
  return spec.updatedInput;
}

/** Run the rewritten command as Claude Code would, and return its result and the labels of the blocks rex opened. */
function runRewritten(sb: Sandbox, command: unknown) {
  rmSync(join(sb.home, "rex-calls"), { force: true });
  const r = spawnSync("/bin/sh", ["-c", String(command)], {
    env: { ...NO_REX, HOME: sb.home, TMPDIR: sb.tmp, PATH: sb.path, ...ENV, REX_AGENTS_MIRROR_DELAY_MS: "0" },
    encoding: "utf8",
    timeout: 30_000,
  });
  const calls = existsSync(join(sb.home, "rex-calls")) ? readFileSync(join(sb.home, "rex-calls"), "utf8").split("\n") : [];
  const labels = calls
    .map((line) => line.split("\t"))
    .filter((c) => c[4] === "session.new_layer")
    .map((c) => JSON.parse(c[5]).layout.block.label);
  return { r, labels };
}

function mirror(sb: Sandbox, e: Record<string, unknown>) {
  const updated = runHook(sb, e);
  if (updated === null) throw new Error("expected a rewrite");
  return runRewritten(sb, updated.command);
}

for (const name of ["bun", "node"]) {
  const rt = locate(name);
  test(`a rewritten background call keeps its output and exit code and opens one block (${name})`, { skip: rt ? false : `${name} is not on PATH` }, () => {
    withSandbox((sb) => {
      const updated = runHook(sb, event("printf 'out\\n'; printf 'err\\n' >&2; exit 3"), ENV, rt);
      if (updated === null) throw new Error("expected a rewrite");
      const { command, ...rest } = updated;
      assert.deepEqual(rest, { description: "Run the tests", timeout: 600000, run_in_background: true });
      const { r, labels } = runRewritten(sb, command);
      assert.equal(r.stdout, "out\nerr\n");
      assert.equal(r.stderr, "", "the runtime prints no warning into the command's stderr");
      assert.equal(r.status, 3);
      assert.deepEqual(labels, ["[claude] Run the tests"]);
      assert.deepEqual(readdirSync(join(sb.home, ".cache", "rex-agents")).map((f) => f.split(".")[0]), ["s-1"]);
    });
  });
}

test("rewrites only an unmirrored background Bash call in rex, with rex on PATH", () => {
  withSandbox((sb) => {
    const rewrites = (e: Record<string, unknown>, env: Record<string, string> = ENV, path = sb.path): boolean =>
      runHook(sb, e, env, process.execPath, path) !== null;
    assert.ok(rewrites(event()));
    assert.ok(!rewrites(event("make test", false)));
    assert.ok(!rewrites(event("make test", null)));
    assert.ok(!rewrites(event(), {}));
    assert.ok(!rewrites(event(), { ...ENV, REX_AGENTS_MIRROR: "0" }));
    assert.ok(rewrites(event(), { ...ENV, REX_AGENTS_MIRROR: "1" }));
    assert.ok(!rewrites({ ...event(), tool_name: "Monitor" }));
    assert.ok(!rewrites(event(), ENV, "/usr/bin:/bin"));
    assert.ok(!rewrites(event("rex do -s session:x wait-status.lua block=b1 timeout=600")));
    assert.ok(rewrites(event("printf 'rex ok\\n'")));
    assert.ok(!rewrites(event(String(runHook(sb, event())?.command))));
  });
});

test("only modes that do not prompt", () => {
  withSandbox((sb) => {
    for (const mode of ["auto", "bypassPermissions"]) {
      assert.ok(runHook(sb, event("make test", true, { permission_mode: mode })) !== null, mode);
    }
    for (const mode of ["manual", "default", "acceptEdits", "plan", "dontAsk", null]) {
      assert.equal(runHook(sb, event("make test", true, { permission_mode: mode })), null, String(mode));
    }
  });
});

test("labels", () => {
  withSandbox((sb) => {
    assert.deepEqual(mirror(sb, event("true", true, { agent_id: "a1" })).labels, ["[claude:sub] Run the tests"]);
    const long = event("true");
    long.tool_input.description = "x".repeat(100);
    assert.deepEqual(mirror(sb, long).labels, [`[claude] ${"x".repeat(60)}`]);
    const bare = event("true");
    delete bare.tool_input.description;
    assert.deepEqual(mirror(sb, bare).labels, ["[claude] true"]);
  });
});

test("a model-written description runs no shell code and reaches rex unchanged", () => {
  withSandbox((sb) => {
    const canary = join(sb.home, "canary");
    const pieces = ["'", '"', "\\", "`", "$", "(", ")", ";", "|", "&", "\n", "\t", " ", "x", "é", "#", "*", "!", "%",
      `$(touch ${canary})`, `\`touch ${canary}\``, `'; touch ${canary}; '`, `"; touch ${canary}; "`];
    let seed = 7;
    const next = (): number => (seed = (seed * 48271) % 2147483647);
    for (let i = 0; i < 20; i++) {
      const description = Array.from({ length: next() % 12 }, () => pieces[next() % pieces.length]).join("");
      const e = event("printf 'ok\\n'");
      e.tool_input.description = description;
      const { r, labels } = mirror(sb, e);
      const text = String(description || e.tool_input.command).split(/[ \t\n]+/).filter(Boolean).join(" ").slice(0, 60);
      assert.equal(r.stdout, "ok\n", JSON.stringify(description));
      assert.deepEqual(labels, [`[claude] ${text}`], JSON.stringify(description));
      assert.ok(!existsSync(canary), JSON.stringify(description));
    }
  });
});

// Rows go through the real `remember`, and listedBlocks reads every row file, so
// these cases do not depend on how rex_mirror.ts stores its rows.
const FAKE_REX = `#!/bin/sh
if [ "$2" = "call" ]; then
  case "$6" in
    b-done) printf '{"records":[{"state":"done","updated_at":"t2"}]}\\n' ;;
    b-error) printf '{"records":[{"state":"error","updated_at":"t2"}]}\\n' ;;
    b-working) printf '{"records":[{"state":"working","updated_at":"t2"}]}\\n' ;;
    b-multi) printf '{"records":[{"state":"working","updated_at":"t1"},{"state":"done","updated_at":"t2"}]}\\n' ;;
    b-tie) printf '{"records":[{"state":"error","updated_at":"t1"},{"state":"done","updated_at":"t1"}]}\\n' ;;
    b-nonjson) printf 'not json\\n' ;;
    b-missingkeys) printf '{}\\n' ;;
    b-nostate) printf '{"records":[{"updated_at":"t2"}]}\\n' ;;
    b-gone) printf 'block not found\\n' >&2; exit 1 ;;
    b-timeout) sleep 30 ;;
    b-closefail) printf '{"records":[{"state":"done","updated_at":"t2"}]}\\n' ;;
    b-trigger)
      "$RT" $RT_FLAGS "$REMEMBER" b-late
      printf '{"records":[{"state":"done","updated_at":"t2"}]}\\n' ;;
    *) exit 1 ;;
  esac
  exit 0
fi
if [ "$2" = "close" ]; then
  [ "$5" = "$CLOSE_FAIL" ] && exit 1
  printf '%s\\n' "$5" >> "$CLOSE_LOG"
  exit 0
fi
exit 1
`;

const row = (block: string): string => JSON.stringify({ block, rex_session: "session:end", label: "l" });

type EndHome = { home: string; rt: string; remember: (block: string) => void; run: (closeFail?: string) => void };

/** A scratch HOME with the fake rex, a remember helper, and a runner for session_end.ts. */
function endHome(rt: string): EndHome {
  const home = mkdtempSync(join(tmpdir(), "rex-end-home-"));
  const bin = join(home, "bin");
  mkdirSync(bin);
  writeFileSync(join(bin, "rex"), FAKE_REX);
  chmodSync(join(bin, "rex"), 0o755);
  const helper = join(home, "remember.ts");
  writeFileSync(helper, `import { remember } from ${JSON.stringify(MIRROR)};\nremember("s-end", process.argv[2], "l");\n`);
  const flags = rt === "node" ? "--disable-warning=ExperimentalWarning" : "";
  const env = {
    ...NO_REX,
    HOME: home,
    PATH: `${bin}:${process.env.PATH}`,
    REX_SESSION: "session:end",
    CLOSE_LOG: join(home, "closed.txt"),
    RT: rt,
    RT_FLAGS: flags,
    REMEMBER: helper,
  };
  const remember = (block: string): void => {
    const r = spawnSync(rt, [...(flags ? [flags] : []), helper, block], { env, encoding: "utf8", timeout: 30_000 });
    assert.equal(r.status, 0, r.stderr);
  };
  const run = (closeFail = ""): void => {
    const hookEnv: Record<string, string> = { ...env, CLOSE_FAIL: closeFail };
    delete hookEnv.REX_SESSION;
    const r = spawnSync(rt, [join(HOOKS, "session_end.ts")], {
      input: JSON.stringify({ session_id: "s-end" }),
      env: hookEnv,
      encoding: "utf8",
      timeout: 60_000,
    });
    assert.equal(r.status, 0, r.stderr);
    assert.equal(r.stdout, "");
  };
  return { home, rt, remember, run };
}

/** The blocks that the session's rows still list, sorted. */
function listedBlocks(home: string): string[] {
  const dir = join(home, ".cache", "rex-agents");
  const blocks: string[] = [];
  for (const name of existsSync(dir) ? readdirSync(dir) : []) {
    if (!name.startsWith("s-end.")) continue;
    for (const line of readFileSync(join(dir, name), "utf8").split("\n")) {
      if (line.length > 0) blocks.push(JSON.parse(line).block);
    }
  }
  return blocks.sort();
}

function closedBlocks(home: string): string[] {
  const p = join(home, "closed.txt");
  return existsSync(p) ? readFileSync(p, "utf8").split("\n").filter((l) => l.length > 0).sort() : [];
}

for (const [rt, withTimeout] of [["bun", true], ["node", false]] as Array<[string, boolean]>) {
  const skip = spawnSync(rt, ["--version"], { stdio: "ignore" }).status === 0 ? false : `${rt} is not on PATH`;
  test(`session end is best-effort per block (${rt})`, { timeout: 90_000, skip }, () => {
    const h = endHome(rt);
    try {
      const blocks = ["b-nonjson", "b-done", "b-error", "b-working", "b-gone", "b-missingkeys", "b-nostate", "b-multi", "b-tie"];
      if (withTimeout) blocks.push("b-timeout");
      for (const b of blocks) h.remember(b);
      h.run();
      const closes = ["b-done", "b-error", "b-multi", "b-tie"];
      assert.deepEqual(listedBlocks(h.home), blocks.filter((b) => !closes.includes(b) && b !== "b-gone").sort());
      assert.deepEqual(closedBlocks(h.home), closes.sort());
    } finally {
      rmSync(h.home, { recursive: true, force: true });
    }
  });

  test(`session end keeps the row of a block whose close failed, and a later pass closes it (${rt})`, { timeout: 60_000, skip }, () => {
    const h = endHome(rt);
    try {
      h.remember("b-done");
      h.remember("b-closefail");
      h.run("b-closefail");
      assert.deepEqual(listedBlocks(h.home), ["b-closefail"]);
      assert.deepEqual(closedBlocks(h.home), ["b-done"]);
      h.run();
      assert.deepEqual(listedBlocks(h.home), []);
      assert.deepEqual(closedBlocks(h.home), ["b-closefail", "b-done"]);
    } finally {
      rmSync(h.home, { recursive: true, force: true });
    }
  });

  // A session that started under the old plugin listed its blocks in one shared <session>.jsonl.
  test(`session end settles the rows of an old shared list, and a rerun after a kill lists each row once (${rt})`, { timeout: 60_000, skip }, () => {
    const h = endHome(rt);
    try {
      const cacheDir = join(h.home, ".cache", "rex-agents");
      const legacy = join(cacheDir, "s-end.jsonl");
      const rows = ["b-done", "b-working"].map(row).join("\n") + "\n";
      mkdirSync(cacheDir, { recursive: true });
      writeFileSync(legacy, rows);
      h.run();
      assert.equal(existsSync(legacy), false);
      assert.deepEqual(closedBlocks(h.home), ["b-done"]);
      assert.deepEqual(listedBlocks(h.home), ["b-working"]);
      // A pass killed after it converted the rows but before it deleted the old file.
      writeFileSync(legacy, rows);
      h.run();
      assert.equal(existsSync(legacy), false);
      assert.deepEqual(listedBlocks(h.home), ["b-working"]);
    } finally {
      rmSync(h.home, { recursive: true, force: true });
    }
  });

  // A kill between the open and the write of a row file leaves it empty, with the old list still there.
  test(`session end rewrites an empty row file from the old shared list, and drops stale temp files (${rt})`, { timeout: 60_000, skip }, () => {
    const h = endHome(rt);
    try {
      const cacheDir = join(h.home, ".cache", "rex-agents");
      const legacy = join(cacheDir, "s-end.jsonl");
      const line = row("b-done");
      const hash = createHash("sha256").update(line).digest("hex");
      const id = `${hash.slice(0, 8)}-${hash.slice(8, 12)}-${hash.slice(12, 16)}-${hash.slice(16, 20)}-${hash.slice(20, 32)}`;
      mkdirSync(cacheDir, { recursive: true });
      writeFileSync(legacy, line + "\n");
      writeFileSync(join(cacheDir, `s-end.${id}.json`), "");
      writeFileSync(join(cacheDir, `s-end.${id}.json.tmp.99999`), line); // a killed pass's temp file
      h.run();
      assert.equal(existsSync(legacy), false);
      assert.deepEqual(closedBlocks(h.home), ["b-done"]);
      assert.deepEqual(readdirSync(cacheDir), []);
    } finally {
      rmSync(h.home, { recursive: true, force: true });
    }
  });

  test(`session end keeps a row that a mirror writes during the pass (${rt})`, { timeout: 60_000, skip }, () => {
    const h = endHome(rt);
    try {
      h.remember("b-trigger"); // its status call runs the real remember for b-late
      h.run();
      assert.deepEqual(closedBlocks(h.home), ["b-trigger"]);
      assert.deepEqual(listedBlocks(h.home), ["b-late"]);
    } finally {
      rmSync(h.home, { recursive: true, force: true });
    }
  });
}

test("node runs session_start.ts", () => {
  const hook = join(HOOKS, "session_start.ts");
  const r = spawnSync("node", [hook], {
    input: "{}",
    env: { ...NO_REX, REX_SESSION: "session:x" },
    encoding: "utf8",
    timeout: 30_000,
  });
  assert.equal(r.status, 0);
  assert.ok(r.stdout.startsWith("Skill folder: "));
  assert.ok(r.stdout.includes("# Using the Rex terminal"));
  assert.ok(!r.stdout.includes("---\nname: using-rex"));
  const outside = spawnSync("node", [hook], { input: "{}", env: NO_REX, encoding: "utf8", timeout: 30_000 });
  assert.equal(outside.status, 0);
  assert.equal(outside.stdout, "");
  const sdk = spawnSync("node", [hook], {
    input: "{}",
    env: { ...NO_REX, REX_SESSION: "session:x", CLAUDE_CODE_ENTRYPOINT: "sdk-cli" },
    encoding: "utf8",
    timeout: 30_000,
  });
  assert.equal(sdk.status, 0);
  assert.equal(sdk.stdout, "");
});

test("node runs subagent_start.ts", () => {
  const hook = join(HOOKS, "subagent_start.ts");
  const r = spawnSync("node", [hook], {
    input: "{}",
    env: { ...NO_REX, REX_SESSION: "session:x" },
    encoding: "utf8",
    timeout: 30_000,
  });
  assert.equal(r.status, 0);
  const out = JSON.parse(r.stdout);
  assert.equal(out.hookSpecificOutput.hookEventName, "SubagentStart");
  assert.match(out.hookSpecificOutput.additionalContext, /\bauto\b/);
  assert.match(out.hookSpecificOutput.additionalContext, /\bbypassPermissions\b/);
  const outside = spawnSync("node", [hook], { input: "{}", env: NO_REX, encoding: "utf8", timeout: 30_000 });
  assert.equal(outside.status, 0);
  assert.equal(outside.stdout, "");
});
