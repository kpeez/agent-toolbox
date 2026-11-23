import assert from "node:assert/strict";
import { test } from "node:test";
import { spawn } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { render } from "../pr_body.ts";

const CASES = 300;
const SEED = 20261122;
const GATE = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..", "..", "hooks", "pr-body-gate.sh");
const HOOK = ["sh", GATE];

function violatesSimplifiedRuleForGeneratedCalls(argv: string[]): boolean {
  const [group, action, ...rest] = argv;
  if (group === "pr" && (action === "create" || action === "new" || action === "edit")) {
    if (rest.some((a) => a === "--fill" || a.startsWith("--body=") || a === "--body" || /^-b/.test(a))) return true;
    const i = rest.indexOf("--body-file");
    if (i < 0) return action !== "edit";
    return rest[i + 1] !== "body.md";
  }
  if (group === "api" && /\/pulls(\/\d+)?$/.test(action)) {
    // Fields without -X make a POST, which creates a PR.
    if (!rest.includes("-X")) return rest.includes("-f");
    return rest.some((a) => /^(?:body|base)=/.test(a));
  }
  return false;
}

function mulberry32(seed: number): () => number {
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

function generator(seed: number, binDir: string): () => string {
  const next = mulberry32(seed);
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
    `${binDir}/gh pr create --body x`,
    "gh api repos/{owner}/{repo}/pulls -f title=t -f body=b",
    "gh api repos/{owner}/{repo}/pulls/12 -X PATCH -f body=b",
    "gh api repos/{owner}/{repo}/pulls/12 -X PATCH -f base=dev",
    "gh api repos/{owner}/{repo}/pulls/12 -X PATCH -f state=closed",
    "gh api repos/{owner}/{repo}/pulls",
    "gh api repos/{owner}/{repo}/pulls/12/comments -f body=b",
    `gh pr create --body "$(cat <<'EOF'\nSummary text.\nEOF\n)"`,
  ];
  const commandsSucceedingWithExtraArgument = ["true", "echo hi", "echo ok >/dev/null 2>&1"];
  const atom = (): string => (next() < 0.7 ? pick(ghCalls) : pick(commandsSucceedingWithExtraArgument));

  const simple = (depth: number, shellLevel: boolean): string => {
    if (depth === 0 || next() < 0.4) return atom();
    const inner = simple(depth - 1, false);
    const wrappers = ["env ", "env FOO=1 ", "nohup ", "sudo ", "timeout 60 ", "nice ", "nice -n 5 ", "ENV_SPLIT"];
    if (shellLevel) wrappers.push("FOO=1 ", "command ", "time ", "XARGS", "EXEC");
    const w = pick(wrappers);
    // env -S splits its string on its own rules, so give it only plain words.
    if (w === "ENV_SPLIT") return /^[^'"$\\`#\n]*$/.test(inner) ? `env -S '${inner}'` : `env ${inner}`;
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
      // `<<` in arithmetic is a shift, not a heredoc.
      () => `x=$(( 1 << 3 ))\n${a}`,
      () => `cat > note.md <<'NOTE${depth}'\nThen run \`${a}\` by hand.\nNOTE${depth}`,
      () => `cat > note.md <<NOTE${depth}\nThen run ${a} by hand.\nNOTE${depth}`,
    ];
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
  // `(( ))` is bash-only (dash reads `((` as two subshells), so it starts only a top-level line.
  return () => (next() < 0.15 ? "(( x = 1 << 3 ))\n" : "") + command(3);
}

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
  // Quote removal joins these into `gh`; the gate must still start the hook.
  "g''h pr create --body x",
  '"g"h pr create --body x',
  "g\\h pr create --body x",
  "g\\\nh pr create --body x",
];

function run(cmd: string, args: string[], options: { cwd: string; env?: NodeJS.ProcessEnv; input?: string }) {
  return new Promise<{ status: number | null; stderr: string }>((done) => {
    const child = spawn(cmd, args, { cwd: options.cwd, env: options.env, stdio: [options.input === undefined ? "ignore" : "pipe", "pipe", "pipe"] });
    let stderr = "";
    child.stderr?.on("data", (d) => (stderr += d));
    child.stdout?.resume();
    child.on("close", (status) => done({ status, stderr }));
    // A process that exits before it reads its input fails on its exit status, not on EPIPE.
    child.stdin?.on("error", () => {});
    child.stdin?.end(options.input);
  });
}

async function bashRuns(command: string, root: string, fakeBin: string, index: number): Promise<string[][]> {
  const log = join(root, `gh-${index}.log`);
  writeFileSync(log, "");
  await run("/bin/bash", ["-c", `${command}\nwait`], {
    cwd: join(root, "work"),
    env: { PATH: `${fakeBin}:/usr/bin:/bin`, GH_LOG: log, HOME: root },
  });
  return readFileSync(log, "utf-8")
    .split("\x1e")
    .filter((record) => record !== "")
    .map((record) => record.split("\x1f").slice(0, -1));
}

function otherShellCorpus(shell: "nu" | "fish"): string[] {
  const calls = [
    "gh pr create --body x",
    "gh pr new --body x",
    "gh pr edit 12 --body x",
    "gh pr create --fill",
    "gh pr create --body-file body.md",
    "gh pr edit 12 --title t",
    "gh api repos/o/r/pulls -f title=t",
    "gh api repos/o/r/pulls/12 -X PATCH -f state=closed",
    "echo hi",
  ];
  const forms =
    shell === "nu"
      ? [(a: string, b: string) => `${a}; ${b}`, (a: string) => `let url = (${a})`, (a: string) => `^${a}`, (a: string) => `echo '${a}'`, (a: string) => `# ${a}`]
      : [(a: string, b: string) => `${a}; and ${b}`, (a: string) => `set url (${a})`, (a: string) => `begin; ${a}; end`, (a: string) => `echo '${a}'`, (a: string) => `true # ${a}`];
  return calls.flatMap((a, i) => forms.map((form) => `${shell} -c ${singleQuote(form(a, calls[(i + 1) % calls.length]))}`));
}

async function agreement(corpus: string[], shells: string[] = []): Promise<{ failures: string[]; blocking: number }> {
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
    for (const shell of shells) symlinkSync(onPath(shell) as string, join(fakeBin, shell));
    const runtimeBin = join(root, "runtime");
    mkdirSync(runtimeBin);
    symlinkSync(process.execPath, join(runtimeBin, process.versions.bun ? "bun" : "node"));
    const envPathHoldingOnlyTestRuntime = { ...process.env, PATH: `${runtimeBin}:/usr/bin:/bin` };
    for (const [slot, text] of Object.entries({ summary: "Each save rewrites the cache.", evidence: "Before: 4 s.", reversible: "yes", blast_radius: "local" })) {
      writeFileSync(join(work, "slots", `${slot}.md`), `${text}\n`);
    }
    const { body } = render(join(work, "slots"), null);
    assert.ok(body !== null);
    writeFileSync(join(work, "body.md"), body);

    const failures: string[] = [];
    let blocking = 0;
    let index = 0;
    const worker = async () => {
      while (index < corpus.length) {
        const i = index++;
        const command = corpus[i].replaceAll("@FAKE_BIN@", fakeBin);
        const [calls, hook] = await Promise.all([
          bashRuns(command, root, fakeBin, i),
          run(HOOK[0], HOOK.slice(1), { cwd: work, env: envPathHoldingOnlyTestRuntime, input: JSON.stringify({ tool_input: { command }, cwd: work }) }),
        ]);
        const expected = calls.some(violatesSimplifiedRuleForGeneratedCalls);
        if (expected) blocking++;
        if (hook.status !== (expected ? 2 : 0)) {
          failures.push(
            `${JSON.stringify(command)}\n  bash ran: ${JSON.stringify(calls)}\n  hook exit ${hook.status}, want ${expected ? 2 : 0} ${hook.stderr.split("\n")[0]}`,
          );
        }
      }
    };
    await Promise.all(Array.from({ length: 8 }, worker));
    return { failures, blocking };
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
}

function onPath(name: string): string | undefined {
  return (process.env.PATH ?? "").split(delimiter).map((dir) => join(dir, name)).find((path) => existsSync(path));
}

test("the hook blocks a command exactly when bash runs a gh call that breaks the PR-body rules", { timeout: 120_000 }, async () => {
  const corpus = [...REGRESSIONS, ...Array.from({ length: CASES }, generator(SEED, "@FAKE_BIN@"))];
  const { failures, blocking } = await agreement(corpus);
  assert.ok(blocking > corpus.length / 4 && blocking < (corpus.length * 3) / 4, `unbalanced corpus: ${blocking}/${corpus.length} block`);
  assert.equal(failures.length, 0, `${failures.length}/${corpus.length} disagree with bash:\n${failures.slice(0, 12).join("\n")}`);
});

const missingShells = ["nu", "fish"].filter((shell) => onPath(shell) === undefined);
test(
  "the hook agrees with nu -c and fish -c on which gh calls they run",
  { timeout: 120_000, skip: missingShells.length > 0 ? `not on PATH: ${missingShells.join(", ")}` : false },
  async () => {
    const corpus = [...otherShellCorpus("nu"), ...otherShellCorpus("fish")];
    const { failures, blocking } = await agreement(corpus, ["nu", "fish"]);
    assert.ok(blocking > 0 && blocking < corpus.length, `unbalanced corpus: ${blocking}/${corpus.length} block`);
    assert.equal(failures.length, 0, `${failures.length}/${corpus.length} disagree:\n${failures.slice(0, 12).join("\n")}`);
  },
);
