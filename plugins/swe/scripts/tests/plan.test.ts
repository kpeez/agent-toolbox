/**
 * Tests for plan.ts: the checks, the page, and the copy-block round trip.
 *
 * Every case spawns the script on a plan folder built in a temp dir and asserts
 * exit codes, stderr lines, and file contents. The node case proves the script
 * runs without bun.
 */

import assert from "node:assert/strict";
import { test } from "node:test";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "plan.ts");

type Json = Record<string, any>;

function box(extra: Json = {}): Json {
  return { done: false, evidence: null, ...extra };
}

function pr(id: string, extra: Json = {}): Json {
  return {
    id,
    depends_on: [],
    files: ["a.ts"],
    change: "change text",
    result: "result text",
    detail: null,
    review_gated: false,
    verify: {
      unit: box({ how: "unit how" }),
      live: box({ scenario: "live scenario", pass: "live pass" }),
      perf: box({ metric: "m", probe: "p", baseline: null, fail_at: "2 s" }),
    },
    ...extra,
  };
}

function decision(id: string, extra: Json = {}): Json {
  return {
    id,
    question: `question of ${id}`,
    options: ["first option", "second option"],
    recommended: 0,
    answer: null,
    note: null,
    ...extra,
  };
}

function basePlan(): Json {
  return {
    title: "Sample plan",
    goal: "goal.md",
    decisions: [decision("storage-format"), decision("md-render")],
    prs: [pr("plan-script"), pr("plan-docs", { depends_on: ["plan-script"], review_gated: true })],
  };
}

function makeFolder(plan: Json, files: Record<string, string> = {}): string {
  const dir = mkdtempSync(join(tmpdir(), "plan-test-"));
  writeFileSync(join(dir, "plan.json"), JSON.stringify(plan, null, 2) + "\n", "utf-8");
  for (const [name, text] of Object.entries({ "goal.md": "The goal.\n", ...files })) {
    mkdirSync(dirname(join(dir, name)), { recursive: true });
    writeFileSync(join(dir, name), text, "utf-8");
  }
  return dir;
}

function run(args: string[], input = "", runtime: string = process.execPath) {
  return spawnSync(runtime, [SCRIPT, ...args], { input, encoding: "utf-8" });
}

function withFolder(plan: Json, files: Record<string, string>, body: (dir: string) => void): void {
  const dir = makeFolder(plan, files);
  try {
    body(dir);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function assertRejected(plan: Json, message: RegExp, files: Record<string, string> = {}): void {
  withFolder(plan, files, (dir) => {
    const result = run(["render", dir]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stderr, message);
    assert.equal(existsSync(join(dir, "plan.html")), false);
  });
}

test("a clean plan renders a page with every decision fieldset and the landing order", () => {
  withFolder(basePlan(), {}, (dir) => {
    const result = run(["render", dir]);
    assert.equal(result.status, 0, result.stderr);
    const page = readFileSync(join(dir, "plan.html"), "utf-8");
    assert.match(page, /<fieldset class="decision" id="storage-format">/);
    assert.match(page, /<fieldset class="decision" id="md-render">/);
    assert.match(page, /<label class="opt rec"><input type="radio" name="md-render" value="first option">/);
    assert.match(page, /plan-script <span class="dim">after: trunk<\/span>/);
    assert.match(page, /plan-docs \(review-gated\) <span class="dim">after: plan-script<\/span>/);
    assert.ok(page.indexOf("plan-script <span") < page.indexOf("plan-docs (review-gated) <span"));
  });
});

test("a decision id with no run of three letters is rejected", () => {
  const plan = basePlan();
  plan.decisions[0].id = "d1";
  assertRejected(plan, /decision id "d1"/);
});

test("a PR id with no run of three letters is rejected", () => {
  const plan = basePlan();
  plan.prs[0].id = "x-2";
  plan.prs[1].depends_on = [];
  assertRejected(plan, /PR id "x-2"/);
});

test("a decision id used twice is rejected", () => {
  const plan = basePlan();
  plan.decisions[1].id = "storage-format";
  assertRejected(plan, /decision id "storage-format" is used twice/);
});

test("a decision with one option is rejected", () => {
  const plan = basePlan();
  plan.decisions[0].options = ["only"];
  assertRejected(plan, /needs at least two options/);
});

test("an out-of-range recommended index is rejected", () => {
  const plan = basePlan();
  plan.decisions[0].recommended = 2;
  assertRejected(plan, /recommended 2 is not an option index/);
});

test("a recorded answer that is not an option is rejected", () => {
  const plan = basePlan();
  plan.decisions[0].answer = "third option";
  assertRejected(plan, /answer "third option" is not one of its options/);
});

test("a dependency on an unknown PR is rejected", () => {
  const plan = basePlan();
  plan.prs[1].depends_on = ["ghost-pr"];
  assertRejected(plan, /depends on unknown PR "ghost-pr"/);
});

test("a dependency cycle is rejected and its path is printed", () => {
  const plan = basePlan();
  plan.prs[0].depends_on = ["plan-docs"];
  assertRejected(plan, /dependency cycle: plan-script -> plan-docs -> plan-script/);
});

test("a goal path with a .. segment is rejected", () => {
  const plan = basePlan();
  plan.goal = "../goal.md";
  assertRejected(plan, /must be relative and have no "\.\." segment/);
});

test("a detail path that is not Markdown is rejected", () => {
  const plan = basePlan();
  plan.prs[0].detail = "prs/detail.txt";
  assertRejected(plan, /must end in \.md/, { "prs/detail.txt": "x" });
});

test("a detail file that does not exist is rejected", () => {
  const plan = basePlan();
  plan.prs[0].detail = "prs/missing.md";
  assertRejected(plan, /file "prs\/missing\.md" does not exist/);
});

test("a done box with empty evidence is rejected", () => {
  const plan = basePlan();
  plan.prs[0].verify.unit = box({ how: "h", done: true, evidence: "  " });
  assertRejected(plan, /PR "plan-script" unit box is done but has no evidence/);
});

test("a missing or wrongly typed field is an error line, not a crash", () => {
  const plan = basePlan();
  delete plan.title;
  plan.decisions[0].recommended = "0";
  assertRejected(plan, /plan\.json: plan\.title: expected a string[\s\S]*decisions\[0\]\.recommended: expected an integer/);
});

test("every error is printed on its own line", () => {
  const plan = basePlan();
  plan.decisions[0].id = "d1";
  plan.prs[1].depends_on = ["ghost-pr"];
  withFolder(plan, {}, (dir) => {
    const lines = run(["render", dir]).stderr.trim().split("\n");
    assert.equal(lines.length, 2);
  });
});

test("a script tag in a Markdown file appears escaped in the page", () => {
  const plan = basePlan();
  plan.prs[0].detail = "prs/plan-script.md";
  withFolder(plan, { "goal.md": "<script>alert(1)</script> & more", "prs/plan-script.md": "<b>bold</b>" }, (dir) => {
    assert.equal(run(["render", dir]).status, 0);
    const page = readFileSync(join(dir, "plan.html"), "utf-8");
    assert.ok(page.includes("&lt;script&gt;alert(1)&lt;/script&gt; &amp; more"));
    assert.ok(page.includes("&lt;b&gt;bold&lt;/b&gt;"));
    assert.equal(page.includes("<script>alert(1)"), false);
  });
});

test("the answer round trip keeps a pipe in an option and in a note", () => {
  const plan = basePlan();
  plan.decisions[0].options = ["JSON | rendered HTML", "JSON"];
  withFolder(plan, {}, (dir) => {
    const block = "storage-format: JSON | rendered HTML | note: keep a | pipe here\n\nmd-render: (no answer) | note: undecided\n";
    const result = run(["answer", dir], block);
    assert.equal(result.status, 0, result.stderr);
    const saved = JSON.parse(readFileSync(join(dir, "plan.json"), "utf-8"));
    assert.equal(saved.decisions[0].answer, "JSON | rendered HTML");
    assert.equal(saved.decisions[0].note, "keep a | pipe here");
    assert.equal(saved.decisions[1].answer, null);
    assert.equal(saved.decisions[1].note, "undecided");
    assert.equal(saved.prs[1].verify.perf.fail_at, "2 s");
    const page = readFileSync(join(dir, "plan.html"), "utf-8");
    assert.match(page, /value="JSON \| rendered HTML" checked>/);
    assert.match(page, /aria-label="Note for md-render">undecided<\/textarea>/);
  });
});

test("an answer line with no answer and no note clears the decision", () => {
  const plan = basePlan();
  plan.decisions[0].answer = "first option";
  plan.decisions[0].note = "old";
  withFolder(plan, {}, (dir) => {
    assert.equal(run(["answer", dir], "storage-format: (no answer)\n").status, 0);
    const saved = JSON.parse(readFileSync(join(dir, "plan.json"), "utf-8"));
    assert.equal(saved.decisions[0].answer, null);
    assert.equal(saved.decisions[0].note, null);
  });
});

test("an unknown decision id leaves plan.json byte-identical", () => {
  withFolder(basePlan(), {}, (dir) => {
    const before = readFileSync(join(dir, "plan.json"));
    const result = run(["answer", dir], "md-render: first option\nghost-decision: first option\n");
    assert.equal(result.status, 1);
    assert.match(result.stderr, /unknown decision id "ghost-decision"/);
    assert.deepEqual(readFileSync(join(dir, "plan.json")), before);
    assert.equal(existsSync(join(dir, "plan.html")), false);
  });
});

test("option text that matches no option is an error and changes nothing", () => {
  withFolder(basePlan(), {}, (dir) => {
    const before = readFileSync(join(dir, "plan.json"));
    const result = run(["answer", dir], "md-render: third option\n");
    assert.equal(result.status, 1);
    assert.match(result.stderr, /matches none of its options/);
    assert.deepEqual(readFileSync(join(dir, "plan.json")), before);
  });
});

test("an unknown command prints usage and exits 2", () => {
  const result = run(["frobnicate", "."]);
  assert.equal(result.status, 2);
  assert.match(result.stderr, /usage: plan\.ts/);
});

test("the script runs under node without bun", () => {
  withFolder(basePlan(), {}, (dir) => {
    const result = run(["render", dir], "", "node");
    assert.equal(result.status, 0, result.stderr);
    assert.ok(existsSync(join(dir, "plan.html")));
  });
});

test("the longest matching option wins when one option extends another", () => {
  const plan = basePlan();
  plan.decisions[0].options = ["use A", "use A | note: B"];
  withFolder(plan, {}, (dir) => {
    assert.equal(run(["answer", dir], "storage-format: use A | note: B\n").status, 0);
    const saved = JSON.parse(readFileSync(join(dir, "plan.json"), "utf-8"));
    assert.equal(saved.decisions[0].answer, "use A | note: B");
    assert.equal(saved.decisions[0].note, null);
  });
});

test("an empty block is an error and changes nothing", () => {
  withFolder(basePlan(), {}, (dir) => {
    const before = readFileSync(join(dir, "plan.json"));
    const result = run(["answer", dir], "\n  \n");
    assert.equal(result.status, 1);
    assert.match(result.stderr, /plan: no answer lines on standard input/);
    assert.deepEqual(readFileSync(join(dir, "plan.json")), before);
    assert.equal(existsSync(join(dir, "plan.html")), false);
  });
});

test("indentation and trailing spaces on a block line are ignored", () => {
  withFolder(basePlan(), {}, (dir) => {
    const result = run(["answer", dir], "  storage-format: second option   \r\n\tmd-render: first option | note: ok \n");
    assert.equal(result.status, 0, result.stderr);
    const saved = JSON.parse(readFileSync(join(dir, "plan.json"), "utf-8"));
    assert.equal(saved.decisions[0].answer, "second option");
    assert.equal(saved.decisions[1].answer, "first option");
    assert.equal(saved.decisions[1].note, "ok");
  });
});
