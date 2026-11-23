/**
 * Property: for every generated command line, the PR-body hook blocks if and
 * only if real bash runs a `gh` call that breaks the PR-body rules.
 *
 * Oracle: each command runs in bash with a fake `gh` (and fake `sudo` and
 * `time` that run their arguments) first on PATH. The fake records each argv. The rule on
 * one argv is the small `violates` table below. Bash, not the hook's parser,
 * decides which `gh` calls run and with what arguments.
 *
 * The generator only builds commands in which every command is reached
 * (`false || x`, never `true || x`): the hook cannot evaluate conditions, so
 * it treats every command it can see as run.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawn } from "node:child_process";
import { chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "../pr_body.ts";

const SCRIPT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "pr_body.ts");
const CASES = 300;
const SEED = 20261122;

/** The PR-body rules on one recorded `gh` argv, for the calls the generator makes. */
function violates(argv: string[]): boolean {
  const [group, action, ...rest] = argv;
  if (group === "pr" && (action === "create" || action === "new" || action === "edit")) {
    if (rest.some((a) => a === "--fill" || a.startsWith("--body=") || a === "--body" || /^-b/.test(a))) return true;
    const i = rest.indexOf("--body-file");
    if (i < 0) return action !== "edit";
    return rest[i + 1] !== "body.md";
  }
  if (group === "api") return /\/pulls(\/\d+)?$/.test(action) && rest.some((a) => a === "-f" || a === "-X");
  return false;
}

// Seeded PRNG (mulberry32) so a failure reproduces from the printed command.
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const singleQuote = (s: string): string => `'${s.replaceAll("'", `'\\''`)}'`;
const oneLine = (s: string): boolean => !s.includes("\n");

function generator(seed: number, fakeBin: string): () => string {
  const next = rng(seed);
  const pick = <T,>(xs: T[]): T => xs[Math.floor(next() * xs.length)];
  const ghCalls = [
    "gh pr create --body x",
    "gh pr create --body=x",
    "gh pr create -bx",
    "gh pr new --body x",
    "gh pr edit 12 --body x",
    "gh pr create --fill",
    "gh pr create",
    "gh pr create --body-file body.md",
    "gh pr create --body-file missing.md",
    "gh pr edit 12 --body-file body.md",
    "gh pr edit 12 --title t",
    "gh pr view 12",
    `${fakeBin}/gh pr create --body x`,
    "gh api repos/{owner}/{repo}/pulls -f title=t -f body=b",
    "gh api repos/{owner}/{repo}/pulls/12 -X PATCH -f body=b",
    "gh api repos/{owner}/{repo}/pulls",
    "gh api repos/{owner}/{repo}/pulls/12/comments -f body=b",
    `gh pr create --body "$(cat <<'EOF'\nSummary text.\nEOF\n)"`,
  ];
  // Each plain command succeeds even with xargs' extra argument, so `&&` always runs its right side.
  const plain = ["true", "echo hi", "echo ok >/dev/null 2>&1"];
  const atom = (): string => (next() < 0.7 ? pick(ghCalls) : pick(plain));

  // A simple command, optionally behind wrappers that run their arguments.
  const simple = (depth: number, shellLevel: boolean): string => {
    if (depth === 0 || next() < 0.4) return atom();
    const inner = simple(depth - 1, false);
    const wrappers = ["env ", "env FOO=1 ", "nohup ", "sudo "];
    if (shellLevel) wrappers.push("FOO=1 ", "command ", "time ", "XARGS", "EXEC");
    const w = pick(wrappers);
    if (w === "XARGS") return `echo 12 | xargs ${inner}`;
    if (w === "EXEC") return `(exec ${inner})`;
    return w + inner;
  };

  // The newline keeps `}` out of a trailing comment and off a heredoc delimiter line.
  // `( ` and `$( ` have a space: `((` and `$((` start arithmetic.
  const group = (x: string): string => `{ ${x}\n}`;

  const command = (depth: number): string => {
    if (depth === 0 || next() < 0.25) return simple(2, true);
    const a = command(depth - 1);
    const forms: (() => string)[] = [
      () => `${group(a)} && ${group(command(depth - 1))}`,
      () => `false || ${group(a)}`,
      () => `( ${a}\n); ${group(command(depth - 1))}`,
      () => `${a}\n${command(depth - 1)}`,
      // The right side reads all input first, so no SIGPIPE stops the left side.
      () => `${group(a)} | ${group(`cat >/dev/null; ${command(depth - 1)}`)}`,
      () => `${group(a)} & ${group(command(depth - 1))}\nwait`,
      () => `( ${a}\n)`,
      () => `cd . && ${group(a)}`,
      () => `if true; then ${a}\nfi`,
      () => `for i in 1; do ${a}\ndone`,
      () => `bash -c ${singleQuote(a)}`,
      () => `sh -c ${singleQuote(a)}`,
      () => `bash -e -c ${singleQuote(a)}`,
      () => `eval ${singleQuote(a)}`,
      () => `bash <<'RUN${depth}'\n${a}\nRUN${depth}`,
      // Data: bash runs none of these.
      () => `cat > note.md <<'NOTE${depth}'\nThen run \`${a}\` by hand.\nNOTE${depth}`,
      () => `cat > note.md <<NOTE${depth}\nThen run ${a} by hand.\nNOTE${depth}`,
    ];
    // bash 5.2 misparses some heredocs nested in $( ), so only heredoc-free commands go there.
    if (!a.includes("<<")) forms.push(() => `out=$( ${a}\n)`, () => `echo "$( ${a}\n)"`);
    if (!a.includes("'")) forms.push(() => `echo '${a}'`);
    if (!/["$`\\]/.test(a)) forms.push(() => `echo "note:\n${a}"`, () => `true # ${a}`.replaceAll("\n", " "));
    if (oneLine(a) && !/[`\\$]/.test(a)) {
      // An unquoted heredoc runs backticks, but not an escaped \$( ).
      forms.push(
        () => `cat > note.md <<NOTE${depth}\nThen run \`${a}\` by hand.\nNOTE${depth}`,
        () => `cat > note.md <<NOTE${depth}\nCost: \\$(${a})\nNOTE${depth}`,
        () => `out=\`${a}\``,
      );
    }
    return pick(forms)();
  };
  return () => command(3);
}

// Fixed cases from KP-667: the heredoc false positive and the nine missed forms.
const REGRESSIONS = [
  "cat > notes.md <<'EOF'\nThen run `gh pr create --draft` by hand.\nEOF",
  "bash -c 'gh pr create --body x'",
  "sh -c 'gh pr create --body x'",
  "eval 'gh pr create --body x'",
  "nohup gh pr create --body x",
  "echo 12 | xargs gh pr edit --body x",
  "sudo gh pr create --body x",
  "if true; then gh pr create --body x; fi",
  "gh pr new --body x",
  "gh api repos/{owner}/{repo}/pulls -f title=t -f body=b",
];

function run(cmd: string, args: string[], options: { cwd: string; env?: NodeJS.ProcessEnv; input: string }) {
  return new Promise<{ status: number | null; stderr: string }>((done) => {
    const child = spawn(cmd, args, { cwd: options.cwd, env: options.env });
    let stderr = "";
    child.stderr.on("data", (d) => (stderr += d));
    child.stdout.resume();
    child.on("close", (status) => done({ status, stderr }));
    child.stdin.end(options.input);
  });
}

async function bashRuns(command: string, root: string, fakeBin: string, index: number): Promise<string[][]> {
  const log = join(root, `gh-${index}.log`);
  writeFileSync(log, "");
  await run("/bin/bash", ["-c", `${command}\nwait`], {
    cwd: join(root, "work"),
    env: { PATH: `${fakeBin}:/usr/bin:/bin`, GH_LOG: log, HOME: root },
    input: "",
  });
  return readFileSync(log, "utf-8")
    .split("\x1e")
    .filter((record) => record !== "")
    .map((record) => record.split("\x1f").slice(0, -1));
}

test("the hook blocks a command exactly when bash runs a gh call that breaks the PR-body rules", { timeout: 120_000 }, async () => {
  const root = mkdtempSync(join(tmpdir(), "pr-body-property-"));
  try {
    const fakeBin = join(root, "bin");
    const work = join(root, "work");
    mkdirSync(fakeBin);
    mkdirSync(join(work, "slots"), { recursive: true });
    // One write per call, so calls in background jobs do not interleave in the log.
    writeFileSync(join(fakeBin, "gh"), `#!/bin/sh\nrecord=$(printf '%s\\037' "$@"; printf '\\036')\nprintf '%s' "$record" >> "$GH_LOG"\n`);
    chmodSync(join(fakeBin, "gh"), 0o755);
    // sudo would prompt, and dash (sh on Linux) has no `time` keyword: both just run their arguments.
    for (const runner of ["sudo", "time"]) {
      writeFileSync(join(fakeBin, runner), '#!/bin/sh\nexec "$@"\n');
      chmodSync(join(fakeBin, runner), 0o755);
    }
    for (const [slot, text] of Object.entries({ summary: "Each save rewrites the cache.", evidence: "Before: 4 s.", reversible: "yes", blast_radius: "local" })) {
      writeFileSync(join(work, "slots", `${slot}.md`), `${text}\n`);
    }
    const { body } = render(join(work, "slots"), null);
    assert.ok(body !== null);
    writeFileSync(join(work, "body.md"), body);

    const generate = generator(SEED, fakeBin);
    const corpus = [...REGRESSIONS, ...Array.from({ length: CASES }, generate)];
    const failures: string[] = [];
    let blocking = 0;
    let index = 0;
    const worker = async () => {
      while (index < corpus.length) {
        const i = index++;
        const command = corpus[i];
        const [calls, hook] = await Promise.all([
          bashRuns(command, root, fakeBin, i),
          run("bun", [SCRIPT, "hook"], { cwd: work, input: JSON.stringify({ tool_input: { command }, cwd: work }) }),
        ]);
        const expected = calls.some(violates);
        if (expected) blocking++;
        if (hook.status !== (expected ? 2 : 0)) {
          failures.push(
            `${JSON.stringify(command)}\n  bash ran: ${JSON.stringify(calls)}\n  hook exit ${hook.status}, want ${expected ? 2 : 0} ${hook.stderr.split("\n")[0]}`,
          );
        }
      }
    };
    await Promise.all(Array.from({ length: 8 }, worker));
    assert.ok(blocking > corpus.length / 4 && blocking < (corpus.length * 3) / 4, `unbalanced corpus: ${blocking}/${corpus.length} block`);
    assert.equal(failures.length, 0, `${failures.length}/${corpus.length} disagree with bash:\n${failures.slice(0, 12).join("\n")}`);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
