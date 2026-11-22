/**
 * Tests for verify_gate.ts. Each row builds a throwaway repo with verify skills,
 * performs steps, then spawns `verify_gate.ts hook` with a PreToolUse event on stdin.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "verify_gate.ts");
const COMMIT = 'git commit -m "change"';

type Repo = { root: string; gitDir: string; fakeBin: string };
type HookResult = { status: number | null; stderr: string };
type Case = {
  name: string;
  skills?: Record<string, string | null>;
  env?: Record<string, string>;
  steps?: (ctx: Ctx) => void;
  command?: string;
  cwd?: (repo: Repo) => string;
  expectStatus: number;
  stderr?: RegExp[];
  log?: (lines: Record<string, unknown>[]) => void;
};

function sh(cwd: string, cmd: string, ...args: string[]): string {
  const r = spawnSync(cmd, args, { cwd, encoding: "utf-8" });
  assert.equal(r.status, 0, `${cmd} ${args.join(" ")}: ${r.stderr}`);
  return r.stdout.trim();
}

class Ctx {
  repo: Repo;
  constructor(repo: Repo) {
    this.repo = repo;
  }
  write(file: string, text: string): void {
    mkdirSync(dirname(join(this.repo.root, file)), { recursive: true });
    writeFileSync(join(this.repo.root, file), text);
  }
  verify(skill: string, ...command: string[]): void {
    const r = spawnSync(process.execPath, [SCRIPT, "run", "--skill", skill, "--", ...command], {
      cwd: this.repo.root,
      encoding: "utf-8",
    });
    assert.ok(r.stdout.includes(`${skill} `), `run printed no verdict: ${r.stdout} ${r.stderr}`);
  }
  hook(command: string, env: Record<string, string> = {}, session = "s1", cwd = this.repo.root): HookResult {
    const event = { tool_input: { command }, cwd, session_id: session };
    const r = spawnSync(process.execPath, [SCRIPT, "hook"], {
      input: JSON.stringify(event),
      encoding: "utf-8",
      env: { ...process.env, PATH: `${this.repo.fakeBin}:${process.env.PATH}`, SWE_VERIFY_GATE: "enforce", ...env },
    });
    return { status: r.status, stderr: r.stderr };
  }
  logLines(): Record<string, unknown>[] {
    const path = join(this.repo.gitDir, "swe-verify", "log.jsonl");
    return existsSync(path) ? readFileSync(path, "utf-8").trim().split("\n").map((l) => JSON.parse(l)) : [];
  }
}

function makeRepo(root: string, skills: Record<string, string | null>): Repo {
  const repoDir = join(root, "repo");
  mkdirSync(repoDir);
  sh(repoDir, "git", "init", "-q", "-b", "main");
  sh(repoDir, "git", "config", "user.email", "t@example.com");
  sh(repoDir, "git", "config", "user.name", "T");
  for (const [name, paths] of Object.entries(skills)) {
    const folder = join(repoDir, ".agents", "skills", name);
    mkdirSync(folder, { recursive: true });
    const header =
      paths === null ? "" : paths.startsWith("inline:") ? `paths: ${paths.slice(7)}\n` : `paths:\n${paths.split(",").map((p) => `  - ${p}`).join("\n")}\n`;
    writeFileSync(join(folder, "SKILL.md"), `---\nname: ${name}\ndescription: demo\n${header}---\nbody\n`);
  }
  mkdirSync(join(repoDir, "src"));
  mkdirSync(join(repoDir, "docs"));
  writeFileSync(join(repoDir, "src", "a.txt"), "one\n");
  writeFileSync(join(repoDir, "docs", "d.md"), "one\n");
  sh(repoDir, "git", "add", "-A");
  sh(repoDir, "git", "commit", "-q", "-m", "init");
  const fakeBin = join(root, "bin");
  mkdirSync(fakeBin);
  const realGit = sh(root, "which", "git");
  writeFileSync(join(fakeBin, "git"), `#!/bin/sh\necho called >> "${root}/git-called"\nexec ${realGit} "$@"\n`, { mode: 0o755 });
  return { root: repoDir, gitDir: join(repoDir, ".git"), fakeBin };
}

const ONE: Record<string, string | null> = { "verify-src": "src/**" };
const TWO: Record<string, string | null> = { "verify-src": "src/**", "verify-docs": "docs/**" };
const edit = (c: Ctx) => c.write("src/a.txt", "two\n");

const outside = (repo: Repo) => dirname(repo.root);
const tsx = (c: Ctx) => c.write("src/b.tsx", "x\n");
const crlfSkill = (c: Ctx) =>
  c.write(".agents/skills/verify-src/SKILL.md", "---\r\nname: verify-src\r\npaths:\r\n  - src/**\r\n---\r\nbody\r\n");
const HEREDOC_MSG = 'git commit -m "$(cat <<\'EOF\'\nwip\n\nVerification: none (spike)\nEOF\n)"';

const skillFile = (c: Ctx, paths: string) => c.write(".agents/skills/verify-src/SKILL.md", `---\nname: verify-src\n${paths}---\nbody\n`);
const tsFile = (name: string) => (c: Ctx) => c.write(`src/${name}`, "x\n");

const CASES: Case[] = [
  { name: "zero-indent yaml list gates", skills: ONE, steps: (c) => { skillFile(c, "paths:\n- src/**\n"); edit(c); }, expectStatus: 2 },
  { name: "trailing yaml comment on a list item is dropped", skills: ONE, steps: (c) => { skillFile(c, "paths:\n  - src/**  # main code\n"); edit(c); }, expectStatus: 2 },
  { name: "a hash inside quotes is kept", skills: ONE, steps: (c) => { skillFile(c, 'paths:\n  - "src/#x/**"  # note\n'); edit(c); }, expectStatus: 0 },
  { name: "empty brace alternative matches the short name", skills: { "verify-src": "inline:src/*.ts{,x}" }, steps: tsFile("a.ts"), expectStatus: 2 },
  { name: "empty brace alternative matches the long name", skills: { "verify-src": "inline:src/*.ts{,x}" }, steps: tsFile("a.tsx"), expectStatus: 2 },
  { name: "here-string does not swallow the commit", skills: ONE, steps: edit, command: 'grep x <<< "$v"\ngit commit -am x', expectStatus: 2 },
  { name: "arithmetic shift does not swallow the commit", skills: ONE, steps: edit, command: "echo $((1<<2))\ngit commit -am x", expectStatus: 2 },
  {
    name: "apostrophe in a comment does not break heredoc stripping",
    skills: ONE,
    steps: edit,
    command: "# don't forget\ncat > notes.md <<'EOF'\ngit commit -m example\nEOF",
    expectStatus: 0,
  },
  { name: "commit inside if/then is gated", skills: ONE, steps: edit, command: "if true; then git commit -am x; fi", expectStatus: 2 },
  { name: "commit after do is gated", skills: ONE, steps: edit, command: "for i in 1; do git commit -am x; done", expectStatus: 2 },
  { name: "negated commit is gated", skills: ONE, steps: edit, command: "! git commit -am x", expectStatus: 2 },
  { name: "timeout wrapper is gated", skills: ONE, steps: edit, command: "timeout 30 git commit -am x", expectStatus: 2 },
  { name: "timeout with a flag value is gated", skills: ONE, steps: edit, command: "timeout -k 5 30 git commit -am x", expectStatus: 2 },
  { name: "nice wrapper is gated", skills: ONE, steps: edit, command: "nice -n 5 git commit -am x", expectStatus: 2 },
  { name: "nohup wrapper is gated", skills: ONE, steps: edit, command: "nohup git commit -am x", expectStatus: 2 },
  { name: "command and exec wrappers are gated", skills: ONE, steps: edit, command: "exec git commit -am x", expectStatus: 2 },
  { name: "fish -c is parsed again", skills: ONE, steps: edit, command: "fish -c 'git commit -am x'", expectStatus: 2 },
  { name: "git commit --help is not a commit", skills: ONE, steps: edit, command: "git commit --help", expectStatus: 0 },
  { name: "git commit -h is not a commit", skills: ONE, steps: edit, command: "git commit -h", expectStatus: 0 },
  { name: "a -h message value is still a commit", skills: ONE, steps: edit, command: "git commit -am -h", expectStatus: 2 },
  { name: "cd into the repo before commit is gated", skills: ONE, steps: edit, cwd: outside, command: "cd repo && git commit -am x", expectStatus: 2 },
  { name: "cd with an absolute path is gated", skills: ONE, steps: edit, cwd: outside, command: "ABS", expectStatus: 2 },
  {
    name: "-F after cd reads from the new folder",
    skills: ONE,
    steps: (c) => { edit(c); c.write("msg.txt", "wip\n\nVerification: none (spike)\n"); },
    cwd: (repo) => join(repo.root, "src"),
    command: "cd .. && git commit -F msg.txt",
    expectStatus: 0,
  },
  { name: "cd - falls back to the session folder", skills: ONE, steps: edit, command: "cd - && git commit -am x", expectStatus: 2 },
  { name: "bare filename glob matches at any depth", skills: { "verify-src": "inline:*.tsx" }, steps: tsx, expectStatus: 2 },
  { name: "brace glob matches", skills: { "verify-src": "inline:src/*.{ts,tsx}" }, steps: tsx, expectStatus: 2 },
  { name: "brace glob skips other extensions", skills: { "verify-src": "inline:src/*.{ts,js}" }, steps: tsx, expectStatus: 0 },
  { name: "bracket glob matches", skills: { "verify-src": "inline:src/[ab].txt" }, steps: edit, expectStatus: 2 },
  { name: "bracket glob skips other names", skills: { "verify-src": "inline:src/[bc].txt" }, steps: edit, expectStatus: 0 },
  { name: "inline comma string splits outside braces", skills: { "verify-src": 'inline:"nope/**, src/*.{txt,md}"' }, steps: edit, expectStatus: 2 },
  { name: "inline flow list", skills: { "verify-src": "inline:[nope/**, src/**]" }, steps: edit, expectStatus: 2 },
  {
    name: "unparseable glob warns and requires the skill",
    skills: { "verify-docs": "inline:src/{a,b" },
    steps: (c) => c.write("docs/d.md", "two\n"),
    expectStatus: 2,
    stderr: [/cannot parse/, /verify-docs/],
  },
  { name: "heredoc body line is not a commit", skills: ONE, steps: edit, command: "cat > notes.md <<'EOF'\ngit commit -m example\nEOF", expectStatus: 0 },
  { name: "unquoted dash heredoc body is not a commit", skills: ONE, steps: edit, command: "cat > notes.md <<-EOF\n\tgit commit -m example\n\tEOF\necho done", expectStatus: 0 },
  { name: "commit after a heredoc is still gated", skills: ONE, steps: edit, command: "cat > n.md <<EOF\ntext\nEOF\ngit commit -am x", expectStatus: 2 },
  { name: "heredoc inside the message keeps the escape line", skills: ONE, steps: edit, command: HEREDOC_MSG, expectStatus: 0 },
  { name: "env -i git commit is gated", skills: ONE, steps: edit, command: "env -i git commit -am x", expectStatus: 2 },
  { name: "env -u X VAR=1 git commit is gated", skills: ONE, steps: edit, command: "env -u X VAR=1 git commit -am x", expectStatus: 2 },
  { name: "sudo git commit is gated", skills: ONE, steps: edit, command: "sudo git commit -am x", expectStatus: 2 },
  { name: "bash -c is parsed again", skills: ONE, steps: edit, command: "bash -c 'git commit -am x'", expectStatus: 2 },
  { name: "sh -c with cd is parsed again", skills: ONE, steps: edit, cwd: outside, command: 'sh -c "cd repo && git commit -am x"', expectStatus: 2 },
  { name: "--trailer escape allows", skills: ONE, steps: edit, command: "git commit -m x --trailer 'Verification: none (spike)'", expectStatus: 0 },
  { name: "--trailer= escape allows", skills: ONE, steps: edit, command: "git commit -m x --trailer='Verification: none (spike)'", expectStatus: 0 },
  {
    name: "CRLF skill file still gates",
    skills: ONE,
    steps: (c) => { crlfSkill(c); edit(c); },
    expectStatus: 2,
    stderr: [/verify-src/],
  },

  { name: "no verify skill in the repo", skills: {}, steps: edit, expectStatus: 0 },
  { name: "skill without paths requires nothing", skills: { "verify-src": null }, steps: edit, expectStatus: 0, stderr: [/sets no paths/] },
  { name: "commit outside every skill's paths", skills: ONE, steps: (c) => c.write("docs/d.md", "two\n"), expectStatus: 0 },
  { name: "unverified change is blocked", skills: ONE, steps: edit, expectStatus: 2, stderr: [/verify-src/, /run --skill verify-src --/, /no VERIFIED result/] },
  { name: "fresh pass is allowed", skills: ONE, steps: (c) => { edit(c); c.verify("verify-src", "true"); }, expectStatus: 0 },
  {
    name: "edit after the run is stale",
    skills: ONE,
    steps: (c) => { edit(c); c.verify("verify-src", "true"); c.write("src/a.txt", "three\n"); },
    expectStatus: 2,
    stderr: [/verify result is stale: files changed since the run/],
  },
  {
    name: "reverting the edit makes the pass valid again",
    skills: ONE,
    steps: (c) => { edit(c); c.verify("verify-src", "true"); c.write("src/a.txt", "three\n"); c.write("src/a.txt", "two\n"); },
    expectStatus: 0,
  },
  { name: "failing verdict is blocked", skills: ONE, steps: (c) => { edit(c); c.verify("verify-src", "false"); }, expectStatus: 2, stderr: [/no VERIFIED result/] },
  { name: "pass from the wrong skill is blocked", skills: TWO, steps: (c) => { edit(c); c.verify("verify-docs", "true"); }, expectStatus: 2, stderr: [/verify-src/] },
  {
    name: "two skills touched, one passed",
    skills: TWO,
    steps: (c) => { edit(c); c.write("docs/d.md", "two\n"); c.verify("verify-src", "true"); },
    expectStatus: 2,
    stderr: [/verify-docs/, /^(?![\s\S]*Run: [^\n]*verify-src)/],
  },
  {
    name: "escape line allows the commit",
    skills: ONE,
    steps: edit,
    command: 'git commit -m "wip" -m "Verification: none (docs only, checked by eye)"',
    expectStatus: 0,
  },
  { name: "escape line with an empty reason does not allow", skills: ONE, steps: edit, command: 'git commit -m "Verification: none ()"', expectStatus: 2 },
  {
    name: "escape line from -F file",
    skills: ONE,
    steps: (c) => { edit(c); c.write("msg.txt", "wip\n\nVerification: none (scratch spike)\n"); },
    command: "git commit -F msg.txt",
    expectStatus: 0,
  },
  { name: "git -C dir commit is gated", skills: ONE, steps: edit, command: 'git -C . commit -m x', expectStatus: 2 },
  { name: "chained add and commit is gated", skills: ONE, steps: edit, command: 'git add -A && git commit -m x', expectStatus: 2 },
  {
    name: "observe mode logs and allows",
    skills: ONE,
    env: { SWE_VERIFY_GATE: "observe" },
    steps: edit,
    expectStatus: 0,
    log: (lines) => {
      assert.equal(lines.length, 1);
      assert.equal(lines[0].decision, "would-block");
      assert.deepEqual(lines[0].missing, ["verify-src"]);
      assert.equal(lines[0].session_id, "s1");
    },
  },
  { name: "default mode is observe", skills: ONE, env: { SWE_VERIFY_GATE: "" }, steps: edit, expectStatus: 0, log: (l) => assert.equal(l.length, 1) },
  { name: "off mode does nothing", skills: ONE, env: { SWE_VERIFY_GATE: "off" }, steps: edit, expectStatus: 0, log: (l) => assert.equal(l.length, 0) },
];

for (const c of CASES) {
  test(c.name, () => {
    const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
    try {
      const ctx = new Ctx(makeRepo(root, c.skills ?? {}));
      c.steps?.(ctx);
      const command = c.command === "ABS" ? `cd ${ctx.repo.root} && git commit -am x` : (c.command ?? COMMIT);
      const result = ctx.hook(command, c.env, "s1", c.cwd?.(ctx.repo));
      assert.equal(result.status, c.expectStatus, result.stderr);
      for (const pattern of c.stderr ?? []) assert.match(result.stderr, pattern);
      c.log?.(ctx.logLines());
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
}

test("exactly one commit passes after two blocks, then the gate blocks again", () => {
  const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
  try {
    const ctx = new Ctx(makeRepo(root, ONE));
    edit(ctx);
    assert.equal(ctx.hook(COMMIT).status, 2);
    assert.equal(ctx.hook(COMMIT).status, 2);
    assert.equal(ctx.hook(COMMIT).status, 0);
    ctx.write("src/a.txt", "three\n");
    assert.equal(ctx.hook(COMMIT).status, 2);
    assert.equal(ctx.hook(COMMIT, {}, "other-session").status, 2);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("non-commit commands exit without a git call", () => {
  const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
  try {
    const ctx = new Ctx(makeRepo(root, ONE));
    edit(ctx);
    for (const command of ["ls -la", 'echo "git commit"', "git status", 'rg "commit" src', "git log --oneline"]) {
      assert.equal(ctx.hook(command).status, 0, command);
    }
    assert.equal(existsSync(join(root, "git-called")), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a paths glob that matches no tracked file warns once", () => {
  const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
  try {
    const ctx = new Ctx(makeRepo(root, { "verify-src": "src/**,gone/**" }));
    edit(ctx);
    const first = ctx.hook(COMMIT);
    assert.match(first.stderr, /"gone\/\*\*" matches no tracked file/);
    assert.doesNotMatch(first.stderr, /"src\/\*\*" matches no tracked file/);
    assert.equal(ctx.hook(COMMIT).stderr.includes("matches no tracked file"), false);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("run records the exit code and a changed tree is inconclusive", () => {
  const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
  try {
    const ctx = new Ctx(makeRepo(root, ONE));
    const run = (...command: string[]) =>
      spawnSync(process.execPath, [SCRIPT, "run", "--skill", "verify-src", "--", ...command], { cwd: ctx.repo.root, encoding: "utf-8" });
    assert.match(run("true").stdout, /verify-src VERIFIED/);
    const failed = run("sh", "-c", "exit 3");
    assert.equal(failed.status, 3);
    assert.match(failed.stdout, /NOT VERIFIED/);
    const racing = run("sh", "-c", "echo x >> src/a.txt");
    assert.match(racing.stdout, /INCONCLUSIVE/);
    assert.equal(racing.status, 3);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("session-start prints one line only in a repo with a verify skill", () => {
  const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
  try {
    const ctx = new Ctx(makeRepo(root, ONE));
    const start = (cwd: string) =>
      spawnSync(process.execPath, [SCRIPT, "session-start"], { input: JSON.stringify({ cwd }), encoding: "utf-8" }).stdout;
    const line = start(ctx.repo.root);
    assert.equal(line.trim().split("\n").length, 1);
    assert.match(line, /scripts\/verify_gate\.ts run --skill/);
    assert.equal(start(root), "");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("a repo with no commit gates on untracked files and skips the stale-glob warning", () => {
  const root = mkdtempSync(join(tmpdir(), "verify-gate-"));
  try {
    const repo = makeRepo(root, ONE);
    rmSync(join(repo.gitDir), { recursive: true, force: true });
    sh(repo.root, "git", "init", "-q", "-b", "main");
    const ctx = new Ctx({ ...repo, gitDir: join(repo.root, ".git") });
    const result = ctx.hook(COMMIT);
    assert.equal(result.status, 2, result.stderr);
    assert.doesNotMatch(result.stderr, /matches no tracked file/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
