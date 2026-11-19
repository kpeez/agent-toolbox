/**
 * Differential test: the hand-written lexer behind splitSegments must agree with
 * Python's shlex, which the PR-body hook used before the TypeScript port.
 *
 * The lexer decides which words the hook sees in a `gh pr create` call, so a
 * divergence can turn a block into an allow. A Python oracle (shlex_oracle.py)
 * splits a hand-written corpus plus a seeded fuzz corpus; every command must give
 * the same segments. When shlex raises on unbalanced quotes, both sides use the
 * same whitespace-split fallback, so a match there also proves both sides fail
 * on the same inputs.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { splitSegments } from "../pr_body.ts";

const ORACLE = resolve(dirname(fileURLToPath(import.meta.url)), "shlex_oracle.py");

interface OracleResult {
  error: boolean;
  segments: string[][];
}

const HAND_WRITTEN: string[] = [
  "gh pr create --title hi --body hello",
  `gh pr create --title "a b" --body 'c d'`,
  `gh pr create --title "say \\"hi\\"" --body 'it'"'"'s'`,
  `echo "a\\nb" 'a\\nb' a\\ b "\\$x" "\\q"`,
  `echo "unterminated`,
  `echo 'unterminated`,
  "echo trailing\\",
  `echo "a\\`,
  "a;b;;c",
  "a&&b||c|d&e",
  "a&&&b |&c ;;; d",
  "a>b 2>&1 c<d (e) `f`",
  "(a;b)&&{ c; }",
  "FOO=bar env BAR=baz gh pr create --base main",
  "/usr/local/bin/gh pr create -Bdevelop",
  "gh pr create --base=main --title x",
  "gh pr create --body-file body.md --title x",
  "gh pr create --body-file=/tmp/b.md",
  "cd x && gh pr create --body a; echo done",
  "git push | gh pr create --fill",
  "gh pr create\n--title x",
  "gh pr create \\\n  --title x \\\n  --body y",
  "echo a\r\necho b\r\n",
  "echo\ta\tb",
  "~/bin/gh pr create ~user *.md ?x [a-z]",
  "echo $HOME ${HOME} $(pwd) !! #not-a-comment a#b a@b,c:d",
  "echo café naïve ß Ÿ 日本語 emoji 😀 a😀b",
  "echo 'ünï' \"日本\" \\é",
  "echo ÿ× ÷ µ ª",
  `gh pr create --title "x" --body "$(cat <<'EOF'\nline one\n'quoted' and "double"\nEOF\n)"`,
  `gh pr create --title "x" --body "$(cat <<EOF\nuser asked for this\nEOF\n)"`,
  `gh pr create --body "$(cat <<'EOF'\nit's unbalanced\nEOF\n)"`,
  `gh pr create --body "$(cat <<'EOF'\nit's` + "\n" + `EOF` + "\n)\" && gh pr create --body x",
  `gh pr create --body "a" "b" 'c' d"e"f 'g'"h"`,
  `echo '' "" a''b ""`,
  `echo ""x '' ''`,
  "",
  " ",
  "\n",
  ";",
  "&&",
  "   gh   pr   create   ",
  "echo a b c",
  "echo  x y\u0085z",
  "echo \"a b\" 'c\u0085d'",
  "echo \"open x",
  "echo \"open \x0b x \x0c y",
  "echo \"open\x1cx\x1dy\x1ez",
];

// Seeded PRNG (mulberry32) so a failure reproduces from the printed index.
function rng(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Weighted alphabet: quotes, backslashes, punctuation, and whitespace dominate.
const ALPHABET: [string, number][] = [
  ['"', 8], ["'", 8], ["\\", 8], ["\\\n", 2], ["\n", 4], [" ", 8], ["\t", 2], ["\r", 2],
  [";", 3], ["&", 4], ["|", 3], ["(", 2], [")", 2], ["`", 2], ["<", 2], [">", 2],
  ["$", 2], ["{", 1], ["}", 1], ["#", 2], ["=", 2], ["-", 2], ["~", 1], ["!", 1],
  ["a", 6], ["b", 3], ["gh", 2], ["pr", 1], ["create", 1], ["--body", 1], ["0", 1], ["_", 1],
  ["é", 1], ["日", 1], ["😀", 1], [" ", 1], [" ", 1], ["\x0b", 1], ["\x1f", 1], ["﻿", 1],
];

function fuzzCorpus(count: number): string[] {
  const next = rng(20260719);
  const total = ALPHABET.reduce((sum, [, w]) => sum + w, 0);
  const pick = (): string => {
    let r = next() * total;
    for (const [s, w] of ALPHABET) {
      r -= w;
      if (r < 0) return s;
    }
    return "a";
  };
  const out: string[] = [];
  for (let i = 0; i < count; i++) {
    const length = 1 + Math.floor(next() * 24);
    let s = "";
    for (let j = 0; j < length; j++) s += pick();
    out.push(s);
  }
  return out;
}

const uv = spawnSync("uv", ["--version"], { encoding: "utf-8" });
const uvMissing = uv.error !== undefined || uv.status !== 0;

test(
  "splitSegments matches Python shlex on hand-written and fuzzed commands",
  { skip: uvMissing ? "uv is not on PATH; the Python shlex oracle cannot run" : false },
  () => {
    const corpus = [...HAND_WRITTEN, ...fuzzCorpus(2000)];
    const run = spawnSync("uv", ["run", "--script", ORACLE], {
      input: JSON.stringify(corpus),
      encoding: "utf-8",
      maxBuffer: 64 * 1024 * 1024,
    });
    assert.equal(run.status, 0, `oracle failed: ${run.stderr}`);
    const oracle: OracleResult[] = JSON.parse(run.stdout);
    assert.equal(oracle.length, corpus.length);

    const failures: string[] = [];
    let errorCases = 0;
    corpus.forEach((command, i) => {
      if (oracle[i].error) errorCases++;
      const actual = splitSegments(command);
      if (JSON.stringify(actual) === JSON.stringify(oracle[i].segments)) return;
      failures.push(
        `#${i} ${JSON.stringify(command)}\n  ts:     ${JSON.stringify(actual)}\n  python: ${JSON.stringify(oracle[i].segments)}`,
      );
    });
    assert.ok(errorCases >= 20, `corpus reaches the unbalanced-quote path only ${errorCases} times`);
    assert.equal(failures.length, 0, `${failures.length} divergences:\n${failures.slice(0, 10).join("\n")}`);
  },
);
