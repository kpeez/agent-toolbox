/**
 * Tests for the hook decisions, the session-end cleanup, and the node fallback.
 *
 * The decide cases pass a fake which, so they need no real rex. The
 * session-end cases run the hook against a fake rex script and a temporary
 * HOME. The smoke cases spawn every hook with node and sample stdin, which
 * proves the erasable syntax and the node: APIs run without bun.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { decide, shquote } from "../../hooks/mirror_hook.ts";
import { body } from "../../hooks/session_start.ts";
import { RULE } from "../../hooks/subagent_start.ts";

const PLUGIN = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOKS = join(PLUGIN, "hooks");
const MIRROR = join(PLUGIN, "scripts", "rex_mirror.ts");

const NO_REX: Record<string, string> = {};
for (const [k, v] of Object.entries(process.env)) {
  if (!k.startsWith("REX_") && typeof v === "string") NO_REX[k] = v;
}

function event(
  command = "make test",
  background: boolean | null = true,
  extra: Record<string, unknown> = {},
): { tool_input: Record<string, unknown> } & Record<string, unknown> {
  const toolInput: Record<string, unknown> = { command, description: "Run the tests", timeout: 600000 };
  if (background !== null) toolInput.run_in_background = background;
  return { tool_name: "Bash", session_id: "s-1", permission_mode: "auto", tool_input: toolInput, ...extra };
}

const whichAll = (name: string): string => `/usr/local/bin/${name}`;
const RUNTIME = "/opt/rt/bin/node";
const ENV = { REX_SESSION: "session:x" };

function wrappedCommand(e: Record<string, unknown>, env: Record<string, string> = ENV): string {
  const out = decide(e, env, whichAll, RUNTIME);
  if (out === null) throw new Error("expected a rewrite");
  return String(out.hookSpecificOutput.updatedInput.command);
}

test("rewrites a background call in rex", () => {
  const out = decide(event(), ENV, whichAll, RUNTIME);
  if (out === null) throw new Error("expected a rewrite");
  const spec = out.hookSpecificOutput;
  assert.equal(spec.hookEventName, "PreToolUse");
  assert.ok(!("permissionDecision" in spec));
  const updated = spec.updatedInput;
  const cmd = String(updated.command);
  assert.ok(cmd.includes(`{ ( :; make test\n ); printf '\\n__rex_rc=%d\\n' "$?"; } 2>&1 | ${RUNTIME} `));
  assert.ok(cmd.includes(MIRROR));
  assert.ok(cmd.includes("'[claude] Run the tests' s-1"));
  const rest = { ...updated };
  delete rest.command;
  assert.deepEqual(rest, { description: "Run the tests", timeout: 600000, run_in_background: true });
});

test("leaves foreground calls alone", () => {
  assert.equal(decide(event("make test", false), ENV, whichAll), null);
  assert.equal(decide(event("make test", null), ENV, whichAll), null);
});

test("leaves calls outside rex alone", () => {
  assert.equal(decide(event(), {}, whichAll), null);
});

test("kill switch", () => {
  assert.equal(decide(event(), { ...ENV, REX_AGENTS_MIRROR: "0" }, whichAll), null);
  assert.ok(decide(event(), { ...ENV, REX_AGENTS_MIRROR: "1" }, whichAll) !== null);
});

test("no double wrap", () => {
  const once = wrappedCommand(event());
  assert.equal(decide(event(once), ENV, whichAll), null);
});

test("needs rex, and runs the mirror with the running runtime", () => {
  assert.equal(decide(event(), ENV, (n) => (n === "rex" ? null : whichAll(n))), null);
  const onlyRex = (n: string): string | null => (n === "rex" ? "/usr/local/bin/rex" : null);
  const out = decide(event(), ENV, onlyRex);
  if (out === null) throw new Error("expected a rewrite without bun on PATH");
  assert.ok(String(out.hookSpecificOutput.updatedInput.command).includes(` | ${process.execPath} `));
});

test("only modes that do not prompt", () => {
  for (const mode of ["auto", "bypassPermissions"]) {
    assert.ok(decide(event("make test", true, { permission_mode: mode }), ENV, whichAll) !== null);
  }
  for (const mode of ["manual", "default", "acceptEdits", "plan", "dontAsk", null]) {
    assert.equal(decide(event("make test", true, { permission_mode: mode }), ENV, whichAll), null);
  }
});

test("other tools are ignored", () => {
  assert.equal(decide({ ...event(), tool_name: "Monitor" }, ENV, whichAll), null);
});

test("labels", () => {
  assert.ok(wrappedCommand(event("make test", true, { agent_id: "a1" })).includes("'[claude:sub] Run the tests'"));
  const long = event();
  long.tool_input.description = "x".repeat(100);
  assert.ok(wrappedCommand(long).includes(`'[claude] ${"x".repeat(60)}'`));
  const bare = event();
  delete bare.tool_input.description;
  assert.ok(wrappedCommand(bare).includes("'[claude] make test'"));
});

test("leaves rex commands alone", () => {
  assert.equal(decide(event("rex do -s session:x wait-status.lua block=b1 timeout=600"), ENV, whichAll), null);
  assert.ok(decide(event("printf 'rex ok\\n'"), ENV, whichAll) !== null);
});

test("quotes labels like shlex.quote", () => {
  assert.equal(shquote("s-1"), "s-1");
  assert.equal(shquote(""), "''");
  assert.equal(shquote("it's"), "'it'\\''s'");
  const e = event();
  e.tool_input.description = "it's a test";
  assert.ok(wrappedCommand(e).includes("'[claude] it'\\''s a test'"));
});

test("body strips the YAML frontmatter", () => {
  assert.equal(body("---\nname: x\n---\n\n# Title\ntext\n"), "# Title\ntext\n");
  assert.equal(body("---\nname: x\n---\n# Title\n"), "# Title\n");
  assert.equal(body("no frontmatter\n"), "no frontmatter\n");
  assert.equal(body("---\nunclosed\n"), "---\nunclosed\n");
});

test("the subagent rule names both mirroring modes", () => {
  assert.ok(RULE.includes("auto"));
  assert.ok(RULE.includes("bypassPermissions"));
});

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
    *) exit 1 ;;
  esac
  exit 0
fi
if [ "$2" = "close" ]; then
  printf '%s\\n' "$5" >> "$CLOSE_LOG"
  exit 0
fi
exit 1
`;

const row = (block: string, i: number): string =>
  JSON.stringify({ block, rex_session: "session:end", label: `l${i}` });

for (const [rt, withTimeout] of [["bun", true], ["node", false]] as Array<[string, boolean]>) {
  test(`session end is best-effort per block (${rt})`, { timeout: 60_000 }, () => {
    const home = mkdtempSync(join(tmpdir(), "rex-end-home-"));
    try {
      const bin = join(home, "bin");
      mkdirSync(bin);
      writeFileSync(join(bin, "rex"), FAKE_REX);
      chmodSync(join(bin, "rex"), 0o755);
      const cacheDir = join(home, ".cache", "rex-agents");
      mkdirSync(cacheDir, { recursive: true });
      const blocks = [
        "b-nonjson",
        "b-done",
        "b-error",
        "b-working",
        "b-gone",
        "b-missingkeys",
        "b-nostate",
        "b-multi",
        "b-tie",
      ];
      if (withTimeout) blocks.push("b-timeout");
      const lines = blocks.map(row);
      writeFileSync(join(cacheDir, "s-end.jsonl"), lines.join("\n") + "\n");
      const closed = join(home, "closed.txt");
      const r = spawnSync(rt, [join(HOOKS, "session_end.ts")], {
        input: JSON.stringify({ session_id: "s-end" }),
        env: { ...NO_REX, HOME: home, PATH: `${bin}:${process.env.PATH}`, CLOSE_LOG: closed },
        encoding: "utf8",
        timeout: 60_000,
      });
      assert.equal(r.status, 0);
      assert.equal(r.stdout, "");
      const keepBlocks = blocks.filter((b) => !["b-done", "b-gone", "b-multi"].includes(b));
      const kept = readFileSync(join(cacheDir, "s-end.jsonl"), "utf8").split("\n").filter((l: string) => l.length > 0);
      assert.deepEqual(kept, lines.filter((l) => keepBlocks.includes(JSON.parse(l).block)));
      assert.equal(readFileSync(closed, "utf8"), "b-done\nb-multi\n");
    } finally {
      rmSync(home, { recursive: true, force: true });
    }
  });
}

function stubBin(home: string): string {
  const bin = join(home, "bin");
  mkdirSync(bin, { recursive: true });
  for (const name of ["rex", "bun"]) {
    writeFileSync(join(bin, name), "#!/bin/sh\nexit 0\n");
    chmodSync(join(bin, name), 0o755);
  }
  return bin;
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

test("node runs mirror_hook.ts", () => {
  const home = mkdtempSync(join(tmpdir(), "rex-smoke-home-"));
  try {
    const bin = stubBin(home);
    const r = spawnSync("node", [join(HOOKS, "mirror_hook.ts")], {
      input: JSON.stringify(event()),
      env: { ...NO_REX, REX_SESSION: "session:x", PATH: `${bin}:${process.env.PATH}` },
      encoding: "utf8",
      timeout: 30_000,
    });
    assert.equal(r.status, 0);
    const out = JSON.parse(r.stdout);
    assert.equal(out.hookSpecificOutput.hookEventName, "PreToolUse");
    assert.ok(String(out.hookSpecificOutput.updatedInput.command).includes("rex_mirror.ts"));
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
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
  assert.ok(out.hookSpecificOutput.additionalContext.includes("auto"));
  assert.ok(out.hookSpecificOutput.additionalContext.includes("bypassPermissions"));
  const outside = spawnSync("node", [hook], { input: "{}", env: NO_REX, encoding: "utf8", timeout: 30_000 });
  assert.equal(outside.status, 0);
  assert.equal(outside.stdout, "");
});

test("node runs session_end.ts", () => {
  const home = mkdtempSync(join(tmpdir(), "rex-smoke-home-"));
  try {
    const r = spawnSync("node", [join(HOOKS, "session_end.ts")], {
      input: JSON.stringify({ session_id: "s-smoke" }),
      env: { ...NO_REX, HOME: home },
      encoding: "utf8",
      timeout: 30_000,
    });
    assert.equal(r.status, 0);
    assert.equal(r.stdout, "");
  } finally {
    rmSync(home, { recursive: true, force: true });
  }
});
