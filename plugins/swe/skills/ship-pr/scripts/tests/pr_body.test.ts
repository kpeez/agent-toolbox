/**
 * Tests for pr_body.ts hook command matching, gh-stack enforcement, and attribution checks.
 *
 * Ported 1:1 from the Python unittest suite. The hook cases spawn `bun pr_body.ts hook`
 * with PreToolUse stdin JSON; the smoke case spawns `node pr_body.ts check`,
 * which proves the erasable syntax and node: APIs run without bun.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render, slotErrors } from "../pr_body.ts";

const SCRIPT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "pr_body.ts");
const TEMPLATE = resolve(dirname(SCRIPT), "..", "templates", "pr-body.md");

function git(cwd: string, ...args: string[]): string {
  const result = spawnSync("git", args, { cwd, encoding: "utf-8" });
  assert.equal(result.status, 0, `git ${args.join(" ")} failed: ${result.stderr}`);
  return result.stdout.trim();
}

function initRepo(root: string, originHead: string | null = "main", ghStack = false): string {
  const repo = join(root, "repo");
  mkdirSync(repo);
  git(repo, "init", "-b", "main");
  git(repo, "config", "user.email", "test@example.com");
  git(repo, "config", "user.name", "Test");
  writeFileSync(join(repo, "README.md"), "hello\n", "utf-8");
  git(repo, "add", "README.md");
  git(repo, "commit", "-m", "initial");
  if (originHead !== null) {
    const headSha = git(repo, "rev-parse", "HEAD");
    git(repo, "update-ref", `refs/remotes/origin/${originHead}`, headSha);
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", `refs/remotes/origin/${originHead}`);
  }
  if (ghStack) writeFileSync(join(repo, ".git", "gh-stack"), "", "utf-8");
  return repo;
}

function renderValidBody(folder: string): string {
  const slots = join(folder, "slots");
  mkdirSync(slots, { recursive: true });
  writeFileSync(join(slots, "summary.md"), "Each save rewrites the whole cache.\n", "utf-8");
  writeFileSync(join(slots, "evidence.md"), "Before: 4 s. After: 0.2 s.\n", "utf-8");
  writeFileSync(join(slots, "reversible.md"), "yes\n", "utf-8");
  writeFileSync(join(slots, "blast_radius.md"), "local\n", "utf-8");
  const { body, errors } = render(slots, null);
  assert.ok(body !== null && errors.length === 0, errors.join("\n"));
  const bodyPath = join(folder, "body.md");
  writeFileSync(bodyPath, body, "utf-8");
  return bodyPath;
}

function runHook(command: string, cwd: string): { status: number | null; stdout: string; stderr: string } {
  const event = { tool_input: { command }, cwd };
  const result = spawnSync("bun", [SCRIPT, "hook"], { input: JSON.stringify(event), encoding: "utf-8" });
  return { status: result.status, stdout: result.stdout, stderr: result.stderr };
}

function withTemp(run: (root: string) => void): void {
  const root = mkdtempSync(join(tmpdir(), "pr-body-"));
  try {
    run(root);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

test("ignores mentions in arguments and other commands", () => {
  withTemp((root) => {
    const body = renderValidBody(root);
    for (const cmd of [
      'rg -l -i "gh pr create" docs',
      'echo "gh pr create --body inline"',
      'git commit -m "gh pr create --base feature"',
      'gh pr edit 12 --title "New title"',
      `gh pr edit 12 --body-file ${basename(body)}`,
      "gh stack link feat-a feat-b",
      "gh stack submit --auto",
    ]) {
      const res = runHook(cmd, root);
      assert.equal(res.status, 0, `${cmd}: ${res.stderr}`);
    }
  });
});

test("matches real invocations across shell separators", () => {
  withTemp((root) => {
    renderValidBody(root);
    for (const cmd of [
      'gh pr create --body "inline"',
      'cd . && gh pr create --body "inline"',
      'true || gh pr create --body "inline"',
      'echo ok; gh pr create --body "inline"',
      'echo ok\ngh pr create --body "inline"',
      'gh pr create --body "inline" | cat',
      'FOO=1 gh pr create --body "inline"',
      'gh pr edit 12 --body "inline"',
      'url=$(gh pr create --body "inline")',
      'url=`gh pr create --body "inline"`',
      'time gh pr create --body "inline"',
      '(cd . && gh pr create --body "inline")',
      'env gh pr create --body "inline"',
      '{ gh pr create --body "inline"; }',
      '/usr/local/bin/gh pr create --body "inline"',
      'gh pr create --body "inline" &',
      'gh pr create -b"inline"',
    ]) {
      const res = runHook(cmd, root);
      assert.equal(res.status, 2, `expected block for ${JSON.stringify(cmd)}, got ${res.status}`);
    }
  });
});

test("newline inside quotes does not split segment", () => {
  withTemp((root) => {
    const res = runHook('echo "line1\ngh pr create --body inline"', root);
    assert.equal(res.status, 0, res.stderr);
  });
});

test("allows non-trunk base without gh-stack file", () => {
  withTemp((root) => {
    const repo = initRepo(root, "main", false);
    const body = renderValidBody(repo);
    const res = runHook(`gh pr create --draft --base feature-a --body-file ${basename(body)}`, repo);
    assert.equal(res.status, 0, res.stderr);
  });
});

test("blocks non-trunk base with gh-stack file", () => {
  withTemp((root) => {
    const repo = initRepo(root, "main", true);
    const body = renderValidBody(repo);
    for (const flag of ["--base feature-a", "--base=feature-a", "-B feature-a", "-B=feature-a", "-Bfeature-a"]) {
      const res = runHook(`gh pr create --draft ${flag} --body-file ${basename(body)}`, repo);
      assert.equal(res.status, 2, flag);
      assert.ok(res.stderr.includes("gh stack link"), res.stderr);
      assert.ok(res.stderr.includes("gh stack submit"), res.stderr);
    }
  });
});

test("allows trunk and omitted base with gh-stack file", () => {
  withTemp((root) => {
    const repo = initRepo(root, "main", true);
    const body = renderValidBody(repo);
    for (const args of [
      `--draft --base main --body-file ${basename(body)}`,
      `--draft -B main --body-file ${basename(body)}`,
      `--draft --body-file ${basename(body)}`,
      `--draft -F${basename(body)}`,
      "gh stack link feat-a feat-b",
      "gh stack submit --auto",
    ]) {
      const cmd = args.startsWith("gh ") ? args : `gh pr create ${args}`;
      const start = performance.now();
      const res = runHook(cmd, repo);
      const elapsed = (performance.now() - start) / 1000;
      assert.equal(res.status, 0, `${cmd}: ${res.stderr}`);
      assert.ok(elapsed < 1.0, `${cmd} took ${elapsed}s`);
    }
  });
});

test("blocks edit retarget to non-trunk with gh-stack file", () => {
  withTemp((root) => {
    const repo = initRepo(root, "main", true);
    const blocked = runHook("gh pr edit 12 --base feature-a", repo);
    assert.equal(blocked.status, 2);
    assert.ok(blocked.stderr.includes("gh stack link"), blocked.stderr);
    const ok = runHook("gh pr edit 12 --base main", repo);
    assert.equal(ok.status, 0, ok.stderr);
  });
});

test("line continuations are checked as one command", () => {
  withTemp((root) => {
    const repo = initRepo(root, "main", true);
    const body = renderValidBody(repo);
    const retarget = runHook("gh pr edit 12 \\\n  --base feature-a", repo);
    assert.equal(retarget.status, 2, retarget.stderr);
    const inline = runHook("gh pr edit 12 \\\n  --body 'x'", repo);
    assert.equal(inline.status, 2, inline.stderr);
    const valid = runHook(`gh pr create \\\n  --base main \\\n  --body-file ${basename(body)}`, repo);
    assert.equal(valid.status, 0, valid.stderr);
  });
});

test("falls back to main and master without origin head", () => {
  withTemp((root) => {
    const repo = initRepo(root, null, true);
    const body = renderValidBody(repo);
    for (const trunk of ["main", "master"]) {
      const res = runHook(`gh pr create --draft --base ${trunk} --body-file ${basename(body)}`, repo);
      assert.equal(res.status, 0, res.stderr);
    }
    const blocked = runHook(`gh pr create --draft --base develop --body-file ${basename(body)}`, repo);
    assert.equal(blocked.status, 2);
  });
});

test("respects custom origin head trunk", () => {
  withTemp((root) => {
    const repo = initRepo(root, "trunk", true);
    const body = renderValidBody(repo);
    const ok = runHook(`gh pr create --draft --base trunk --body-file ${basename(body)}`, repo);
    assert.equal(ok.status, 0, ok.stderr);
    const blocked = runHook(`gh pr create --draft --base main --body-file ${basename(body)}`, repo);
    assert.equal(blocked.status, 2);
  });
});

test("linked worktree reads common dir gh-stack", () => {
  withTemp((root) => {
    const repo = initRepo(root, "main", true);
    const worktree = join(root, "wt");
    git(repo, "worktree", "add", "-b", "feat-a", worktree);
    const body = renderValidBody(worktree);
    const blocked = runHook(`gh pr create --draft --base feat-base --body-file ${basename(body)}`, worktree);
    assert.equal(blocked.status, 2);
    assert.ok(blocked.stderr.includes("gh stack link"), blocked.stderr);
    const ok = runHook(`gh pr create --draft --base main --body-file ${basename(body)}`, worktree);
    assert.equal(ok.status, 0, ok.stderr);
  });
});

test("allows non-requester capitalized verbs", () => {
  for (const text of [
    "Pyright says the return type is wrong.",
    "Ruff prefers the shorter form.",
    "Upstream decided to drop Python 3.12.",
    "Each save rewrites the whole cache.",
  ]) {
    assert.deepEqual(slotErrors("summary", text), [], text);
  }
});

test("flags requester attribution", () => {
  for (const text of ["the user asked for this", "Dana asked for this.", "As requested, the flag is gone.", "you decided to drop it"]) {
    const errors = slotErrors("summary", text);
    assert.ok(errors.length > 0, `expected attribution error for ${JSON.stringify(text)}`);
  }
});

test("hook blocks an unrendered body with an unfilled slot", () => {
  withTemp((root) => {
    // The template with one slot left empty: check cannot match it. A raw
    // template with {slot} placeholders still matches (the braces are content).
    const unrendered = readFileSync(TEMPLATE, "utf-8").replace("{summary}", "");
    writeFileSync(join(root, "unrendered.md"), unrendered, "utf-8");
    const res = runHook("gh pr create --body-file unrendered.md", root);
    assert.equal(res.status, 2, res.stderr);
    assert.ok(res.stderr.includes("PR body blocked by ship-pr"), res.stderr);
  });
});

test("hook passes a rendered body", () => {
  withTemp((root) => {
    const body = renderValidBody(root);
    const res = runHook(`gh pr create --body-file ${basename(body)}`, root);
    assert.equal(res.status, 0, res.stderr);
  });
});

test("hook passes a non-PR Bash command", () => {
  withTemp((root) => {
    const res = runHook("ls -la && echo done | cat", root);
    assert.equal(res.status, 0, res.stderr);
  });
});

test("hook blocks --body-file -", () => {
  withTemp((root) => {
    const res = runHook("gh pr create --body-file -", root);
    assert.equal(res.status, 2, res.stderr);
    assert.ok(res.stderr.includes("reads stdin"), res.stderr);
  });
});

test("hook blocks a missing body file", () => {
  withTemp((root) => {
    const res = runHook("gh pr create --body-file nope.md", root);
    assert.equal(res.status, 2, res.stderr);
    assert.ok(res.stderr.includes("does not exist yet"), res.stderr);
  });
});

test("node fallback: check a rendered file", () => {
  withTemp((root) => {
    const body = renderValidBody(root);
    const result = spawnSync("node", [SCRIPT, "check", body], { encoding: "utf-8" });
    assert.equal(result.status, 0, result.stderr);
    assert.ok(result.stdout.includes("pr_body: ok"), result.stdout);
  });
});

test("render accepts Closes, Fixes, and Part of links, and the hook passes each", () => {
  withTemp((root) => {
    const slots = join(root, "slots");
    renderValidBody(root);
    for (const link of ["Closes", "Fixes", "Part of"].map((word) => `${word} ABC-123`)) {
      const { body, errors } = render(slots, link);
      assert.ok(body !== null && errors.length === 0, errors.join("\n"));
      assert.ok(body.endsWith(`\n\n${link}\n`));
      writeFileSync(join(root, "linked.md"), body, "utf-8");
      const res = runHook("gh pr create --body-file linked.md", root);
      assert.equal(res.status, 0, res.stderr);
    }
    assert.ok(render(slots, "Resolves ABC-123").errors.length > 0);
  });
});
