import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdirSync, mkdtempSync, realpathSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "transcripts.ts");

function git(cwd: string, ...args: string[]): void {
  const result = spawnSync("git", ["-c", "user.email=test@example.com", "-c", "user.name=Test", ...args], { cwd, encoding: "utf-8" });
  assert.equal(result.status, 0, `git ${args.join(" ")} failed: ${result.stderr}`);
}

const claudeSlug = (path: string): string => path.replace(/[^A-Za-z0-9]/g, "-");

type Fixture = { home: string; repo: string; listed: Map<string, string>; unlisted: Map<string, string>; subagent: [string, string] };

function buildFixture(root: string): Fixture {
  const home = join(root, "home");
  const repo = join(root, "repo");
  const worktree = join(root, "repo-worktree");
  const otherProject = join(root, "other-project");
  const siblingWithSharedPrefix = join(root, "repo-sibling");
  mkdirSync(repo);
  mkdirSync(otherProject);
  mkdirSync(siblingWithSharedPrefix);
  git(repo, "init", "-b", "main");
  git(repo, "commit", "--allow-empty", "-m", "initial");
  git(repo, "worktree", "add", worktree, "-b", "feature");

  const listed = new Map<string, string>();
  const unlisted = new Map<string, string>();
  const write = (into: Map<string, string>, path: string, firstLine: (secret: string) => object): void => {
    const secret = `SECRET-${randomUUID()}`;
    mkdirSync(dirname(path), { recursive: true });
    writeFileSync(path, `${JSON.stringify(firstLine(secret))}\n${JSON.stringify({ text: secret })}\n`);
    into.set(path, secret);
  };
  const claude = (into: Map<string, string>, cwd: string, id: string): string => {
    const path = join(home, ".claude", "projects", claudeSlug(cwd), `${id}.jsonl`);
    write(into, path, (secret) => ({ type: "user", cwd, message: secret }));
    return path;
  };
  const codex = (into: Map<string, string>, cwd: string, id: string): void => {
    const path = join(home, ".codex", "sessions", "2026", "11", "23", `rollout-${id}.jsonl`);
    write(into, path, (secret) => ({ type: "session_meta", payload: { cwd, note: secret } }));
  };

  claude(listed, repo, "main-checkout");
  claude(listed, worktree, "linked-worktree");
  codex(listed, repo, "main-checkout");
  codex(listed, join(worktree, "subfolder"), "linked-worktree");
  claude(unlisted, otherProject, "other-project");
  claude(unlisted, siblingWithSharedPrefix, "sibling-with-shared-prefix");
  codex(unlisted, otherProject, "other-project");
  codex(unlisted, siblingWithSharedPrefix, "sibling-with-shared-prefix");

  const subagentPath = join(home, ".claude", "projects", claudeSlug(repo), "main-checkout", "subagents", "agent-1.jsonl");
  const subagentSecret = `SECRET-${randomUUID()}`;
  mkdirSync(dirname(subagentPath), { recursive: true });
  writeFileSync(subagentPath, `${JSON.stringify({ type: "user", message: subagentSecret })}\n`);
  return { home, repo, listed, unlisted, subagent: [subagentPath, subagentSecret] };
}

function runTranscripts(runtime: string, fixture: Fixture, ...flags: string[]) {
  const env = { PATH: process.env.PATH, HOME: fixture.home };
  const result = spawnSync(runtime, [SCRIPT, "--cwd", fixture.repo, ...flags], { env, encoding: "utf-8" });
  assert.equal(result.status, 0, result.stderr);
  const paths = result.stdout.split("\n").filter((line) => line !== "").map((line) => line.split("\t")[1]);
  return { paths, output: result.stdout + result.stderr };
}

for (const runtime of ["bun", "node"]) {
  const missing = spawnSync(runtime, ["--version"]).error !== undefined;
  test(`${runtime}: lists only this repository's transcripts and never prints their content`, { skip: missing && `${runtime} is not installed` }, () => {
    const root = realpathSync(mkdtempSync(join(tmpdir(), "transcripts-")));
    try {
      const fixture = buildFixture(root);
      const [subagentPath, subagentSecret] = fixture.subagent;
      const secrets = [...fixture.listed.values(), ...fixture.unlisted.values(), subagentSecret];

      const plain = runTranscripts(runtime, fixture);
      assert.deepEqual([...plain.paths].sort(), [...fixture.listed.keys()].sort());

      const withSubagents = runTranscripts(runtime, fixture, "--subagents");
      assert.deepEqual([...withSubagents.paths].sort(), [...fixture.listed.keys(), subagentPath].sort());

      for (const { output } of [plain, withSubagents]) {
        for (const secret of secrets) assert.ok(!output.includes(secret), `${runtime} printed transcript content`);
      }
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
}
