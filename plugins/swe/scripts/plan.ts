/**
 * Check a plan folder and render the page the user answers.
 *
 * plan.json is the only source of state. Long text lives in the Markdown files
 * it names. render: check, then write plan.html. answer: read a copy block from
 * stdin, record each answer and note in plan.json, then render.
 */

import { readFileSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT = realpathSync(fileURLToPath(import.meta.url));
const SLUG = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const NOTE_SEPARATOR = " | note: ";
const NO_ANSWER = "(no answer)";
const BOXES = ["unit", "live", "perf"] as const;

type Box = { done: boolean; evidence: string | null; fields: [string, string | null][] };
type Decision = {
  id: string;
  question: string;
  options: string[];
  recommended: number;
  answer: string | null;
  note: string | null;
};
type Pr = {
  id: string;
  depends_on: string[];
  files: string[];
  change: string;
  result: string;
  detail: string | null;
  review_gated: boolean;
  verify: Record<(typeof BOXES)[number], Box>;
};
type Plan = { title: string; goal: string; decisions: Decision[]; prs: Pr[] };

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

class Reader {
  errors: string[] = [];

  fail(path: string, expected: string): void {
    this.errors.push(`plan.json: ${path}: expected ${expected}`);
  }

  record(v: unknown, path: string): Record<string, unknown> {
    if (isRecord(v)) return v;
    this.fail(path, "an object");
    return {};
  }

  array(v: unknown, path: string): unknown[] {
    if (Array.isArray(v)) return v;
    this.fail(path, "an array");
    return [];
  }

  str(o: Record<string, unknown>, key: string, path: string): string {
    const v = o[key];
    if (typeof v === "string") return v;
    this.fail(`${path}.${key}`, "a string");
    return "";
  }

  strOrNull(o: Record<string, unknown>, key: string, path: string): string | null {
    const v = o[key];
    if (v === null || typeof v === "string") return v;
    this.fail(`${path}.${key}`, "a string or null");
    return null;
  }

  bool(o: Record<string, unknown>, key: string, path: string): boolean {
    const v = o[key];
    if (typeof v === "boolean") return v;
    this.fail(`${path}.${key}`, "true or false");
    return false;
  }

  int(o: Record<string, unknown>, key: string, path: string): number {
    const v = o[key];
    if (typeof v === "number" && Number.isInteger(v)) return v;
    this.fail(`${path}.${key}`, "an integer");
    return 0;
  }

  strings(o: Record<string, unknown>, key: string, path: string): string[] {
    const items = this.array(o[key], `${path}.${key}`);
    return items.map((item, i) => {
      if (typeof item === "string") return item;
      this.fail(`${path}.${key}[${i}]`, "a string");
      return "";
    });
  }

  box(v: unknown, kind: (typeof BOXES)[number], path: string): Box {
    const o = this.record(v, path);
    const done = this.bool(o, "done", path);
    const evidence = this.strOrNull(o, "evidence", path);
    const text = (key: string) => this.str(o, key, path);
    const fields: [string, string | null][] =
      kind === "unit"
        ? [["how", text("how")]]
        : kind === "live"
          ? [["scenario", text("scenario")], ["pass", text("pass")]]
          : [
              ["metric", text("metric")],
              ["probe", text("probe")],
              ["baseline", this.strOrNull(o, "baseline", path)],
              ["fail at", text("fail_at")],
            ];
    return { done, evidence, fields };
  }
}

export function parsePlan(raw: unknown): { plan: Plan | null; errors: string[] } {
  const r = new Reader();
  const root = r.record(raw, "plan");
  const title = r.str(root, "title", "plan");
  const goal = r.str(root, "goal", "plan");
  const decisions = r.array(root.decisions, "decisions").map((v, i): Decision => {
    const path = `decisions[${i}]`;
    const o = r.record(v, path);
    return {
      id: r.str(o, "id", path),
      question: r.str(o, "question", path),
      options: r.strings(o, "options", path),
      recommended: r.int(o, "recommended", path),
      answer: r.strOrNull(o, "answer", path),
      note: r.strOrNull(o, "note", path),
    };
  });
  const prs = r.array(root.prs, "prs").map((v, i): Pr => {
    const path = `prs[${i}]`;
    const o = r.record(v, path);
    const verify = r.record(o.verify, `${path}.verify`);
    return {
      id: r.str(o, "id", path),
      depends_on: r.strings(o, "depends_on", path),
      files: r.strings(o, "files", path),
      change: r.str(o, "change", path),
      result: r.str(o, "result", path),
      detail: r.strOrNull(o, "detail", path),
      review_gated: r.bool(o, "review_gated", path),
      verify: {
        unit: r.box(verify.unit, "unit", `${path}.verify.unit`),
        live: r.box(verify.live, "live", `${path}.verify.live`),
        perf: r.box(verify.perf, "perf", `${path}.verify.perf`),
      },
    };
  });
  if (r.errors.length > 0) return { plan: null, errors: r.errors };
  return { plan: { title, goal, decisions, prs }, errors: [] };
}

function idErrors(kind: string, id: string): string[] {
  if (SLUG.test(id) && /[a-z]{3}/.test(id)) return [];
  return [`${kind} id "${id}" must be a lowercase slug with a run of at least three letters, such as storage-format`];
}

function pathErrors(folder: string, label: string, rel: string): string[] {
  const segments = rel.split(/[/\\]/);
  if (isAbsolute(rel) || rel.startsWith("\\") || segments.includes("..")) {
    return [`${label} path "${rel}" must be relative and have no ".." segment`];
  }
  if (!rel.endsWith(".md")) return [`${label} path "${rel}" must end in .md`];
  const full = join(folder, rel);
  if (!isFile(full)) return [`${label} file "${rel}" does not exist in the plan folder`];
  const inside = relative(realpathSync(folder), realpathSync(full));
  if (inside.startsWith("..") || isAbsolute(inside)) return [`${label} path "${rel}" leaves the plan folder`];
  return [];
}

function findCycles(prs: Pr[]): string[][] {
  const deps = new Map(prs.map((p) => [p.id, p.depends_on]));
  const state = new Map<string, "open" | "done">();
  const cycles: string[][] = [];
  const visit = (id: string, stack: string[]): void => {
    if (state.get(id) === "open") {
      cycles.push([...stack.slice(stack.indexOf(id)), id]);
      return;
    }
    if (state.get(id) === "done" || !deps.has(id)) return;
    state.set(id, "open");
    for (const dep of deps.get(id) ?? []) visit(dep, [...stack, id]);
    state.set(id, "done");
  };
  for (const p of prs) visit(p.id, []);
  return cycles;
}

export function checkPlan(folder: string, plan: Plan): string[] {
  const errors: string[] = [];
  const seenDecisions = new Set<string>();
  for (const d of plan.decisions) {
    errors.push(...idErrors("decision", d.id));
    if (seenDecisions.has(d.id)) errors.push(`decision id "${d.id}" is used twice`);
    seenDecisions.add(d.id);
    if (d.options.length < 2) errors.push(`decision "${d.id}" needs at least two options`);
    if (d.recommended < 0 || d.recommended >= d.options.length) {
      errors.push(`decision "${d.id}": recommended ${d.recommended} is not an option index`);
    }
    if (d.answer !== null && !d.options.includes(d.answer)) {
      errors.push(`decision "${d.id}": answer "${d.answer}" is not one of its options`);
    }
  }
  const prIds = new Set<string>();
  for (const p of plan.prs) {
    errors.push(...idErrors("PR", p.id));
    if (prIds.has(p.id)) errors.push(`PR id "${p.id}" is used twice`);
    prIds.add(p.id);
  }
  for (const p of plan.prs) {
    for (const dep of p.depends_on) {
      if (!prIds.has(dep)) errors.push(`PR "${p.id}" depends on unknown PR "${dep}"`);
    }
  }
  for (const cycle of findCycles(plan.prs)) errors.push(`dependency cycle: ${cycle.join(" -> ")}`);
  errors.push(...pathErrors(folder, "goal", plan.goal));
  for (const p of plan.prs) {
    if (p.detail !== null) errors.push(...pathErrors(folder, `PR "${p.id}" detail`, p.detail));
    for (const kind of BOXES) {
      const box = p.verify[kind];
      if (box.done && (box.evidence === null || box.evidence.trim() === "")) {
        errors.push(`PR "${p.id}" ${kind} box is done but has no evidence`);
      }
    }
  }
  return errors;
}

/** Landing order: each PR after its dependencies, ties in plan order. Needs an acyclic plan. */
export function landingOrder(prs: Pr[]): Pr[] {
  const placed = new Set<string>();
  const order: Pr[] = [];
  while (order.length < prs.length) {
    const next = prs.find((p) => !placed.has(p.id) && p.depends_on.every((d) => placed.has(d)));
    if (!next) break;
    placed.add(next.id);
    order.push(next);
  }
  return order;
}

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

const CSS = String.raw`:root { color-scheme: light dark; --bg: #f6f4ee; --card: #fff; --ink: #1c1b18; --dim: #605b50; --line: #d9d3c4; --accent: #2147d6; --soft: #e5eaff; }
@media (prefers-color-scheme: dark) { :root { --bg: #11110f; --card: #1a1a17; --ink: #efece4; --dim: #aca597; --line: #3b3a33; --accent: #7d97ff; --soft: #1b2347; } }
* { box-sizing: border-box; }
body { margin: 0 auto; max-width: 680px; padding: 16px 16px 48px; background: var(--bg); color: var(--ink); font: 16px/1.5 -apple-system, system-ui, sans-serif; }
h1 { font-size: 24px; line-height: 1.2; margin: 8px 0 12px; }
h2 { font-size: 18px; margin: 28px 0 8px; }
h3 { font-size: 16px; margin: 0 0 6px; }
code, pre { font: 14px ui-monospace, Menlo, monospace; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px; margin: 8px 0; }
.dim { color: var(--dim); }
section.pr { border: 1px solid var(--line); border-radius: 14px; background: var(--card); margin: 12px 0; padding: 12px 14px; }
section.pr ul { margin: 6px 0; padding-left: 20px; }
fieldset.decision { border: 1px solid var(--line); border-radius: 14px; background: var(--card); margin: 12px 0; padding: 12px 14px 14px; }
legend { font-weight: 600; padding: 0 6px; }
label.opt { display: flex; gap: 10px; align-items: flex-start; min-height: 44px; padding: 10px; margin: 6px 0; border: 1px solid var(--line); border-radius: 10px; }
label.opt:has(input:checked) { border-color: var(--accent); background: var(--soft); }
label.rec::after { content: "recommended"; margin-left: auto; padding-left: 8px; font-size: 12px; color: var(--accent); white-space: nowrap; }
input[type=radio] { margin-top: 5px; accent-color: var(--accent); }
textarea { width: 100%; margin-top: 6px; font: inherit; font-size: 16px; color: var(--ink); background: var(--bg); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
button { min-height: 44px; padding: 0 20px; font: inherit; font-weight: 600; color: #fff; background: var(--accent); border: 0; border-radius: 999px; }
@media (prefers-color-scheme: dark) { button { color: #0b1030; } }`;

const JS = String.raw`const out = document.getElementById("out");
function build() {
  out.textContent = [...document.querySelectorAll(".decision")].map(d => {
    const pick = d.querySelector("input:checked");
    const note = d.querySelector("textarea").value.trim().replace(/\s+/g, " ");
    return pick ? d.id + ": " + pick.value + (note ? " | note: " + note : "")
                : d.id + ": (no answer)" + (note ? " | note: " + note : "");
  }).join("\n");
}
document.addEventListener("input", build);
document.getElementById("copy").onclick = async e => {
  const done = t => { e.target.textContent = t; setTimeout(() => e.target.textContent = "Copy answers", 1500); };
  try { await navigator.clipboard.writeText(out.textContent); done("Copied"); }
  catch { getSelection().selectAllChildren(out); done("Selected: copy it"); }
};
build();`;

function decisionHtml(d: Decision): string {
  const id = esc(d.id);
  const options = d.options
    .map((o, i) => {
      const checked = d.answer === o ? " checked" : "";
      return `  <label class="opt${i === d.recommended ? " rec" : ""}"><input type="radio" name="${id}" value="${esc(o)}"${checked}> ${esc(o)}</label>`;
    })
    .join("\n");
  return `<fieldset class="decision" id="${id}">
  <legend>${id}: ${esc(d.question)}</legend>
${options}
  <textarea rows="2" placeholder="Optional note" aria-label="Note for ${id}">${esc(d.note ?? "")}</textarea>
</fieldset>`;
}

function boxHtml(kind: string, box: Box): string {
  const fields = box.fields.map(([k, v]) => `${esc(k)}: ${v === null ? "none" : esc(v)}`).join("; ");
  const evidence = box.evidence === null ? "" : `; evidence: ${esc(box.evidence)}`;
  return `<li>${box.done ? "☑" : "☐"} ${kind}: ${fields}${evidence}</li>`;
}

function prHtml(p: Pr, detail: string | null): string {
  const id = esc(p.id);
  return `<section class="pr" id="pr-${id}">
<h3>${id}${p.review_gated ? " (review-gated)" : ""}</h3>
<ul>
<li>depends on: ${p.depends_on.length > 0 ? esc(p.depends_on.join(", ")) : "trunk"}</li>
<li>files: ${esc(p.files.join(", "))}</li>
<li>change: ${esc(p.change)}</li>
<li>result: ${esc(p.result)}</li>
${BOXES.map((k) => boxHtml(k, p.verify[k])).join("\n")}
</ul>
${detail === null ? "" : `<pre>${esc(detail)}</pre>`}
</section>`;
}

export function renderPage(folder: string, plan: Plan): string {
  const read = (rel: string) => readFileSync(join(folder, rel), "utf-8");
  const order = landingOrder(plan.prs)
    .map((p) => {
      const after = p.depends_on.length > 0 ? p.depends_on.join(", ") : "trunk";
      return `<li>${esc(p.id)}${p.review_gated ? " (review-gated)" : ""} <span class="dim">after: ${esc(after)}</span></li>`;
    })
    .join("\n");
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${esc(plan.title)}</title>
<style>
${CSS}
</style>
</head>
<body>
<h1>${esc(plan.title)}</h1>
<pre class="goal">${esc(read(plan.goal))}</pre>

<h2>Landing order</h2>
<ol>
${order}
</ol>

<h2>Decisions</h2>
${plan.decisions.map(decisionHtml).join("\n")}

<h2>Your answers</h2>
<pre id="out"></pre>
<button id="copy" type="button">Copy answers</button>

<h2>PRs</h2>
${plan.prs.map((p) => prHtml(p, p.detail === null ? null : read(p.detail))).join("\n")}

<script>
${JS}
</script>
</body>
</html>
`;
}

type Recorded = { answer: string | null; note: string | null };

/** Parse a copy block against the plan's decisions. Returns errors and nothing else on failure. */
export function parseAnswers(plan: Plan, block: string): { recorded: Map<string, Recorded>; errors: string[] } {
  const recorded = new Map<string, Recorded>();
  const errors: string[] = [];
  const byId = new Map(plan.decisions.map((d) => [d.id, d]));
  const lines = block.split("\n").map((l) => l.trim()).filter((l) => l !== "");
  if (lines.length === 0) errors.push("no answer lines on standard input");
  for (const line of lines) {
    const cut = line.indexOf(": ");
    if (cut < 0) {
      errors.push(`line "${line}" is not "<decision id>: <answer>"`);
      continue;
    }
    const id = line.slice(0, cut);
    const rest = line.slice(cut + 2);
    const decision = byId.get(id);
    if (!decision) {
      errors.push(`unknown decision id "${id}"`);
      continue;
    }
    const options = [...decision.options].sort((a, b) => b.length - a.length);
    const hit = [...options, NO_ANSWER].find((o) => rest === o || rest.startsWith(o + NOTE_SEPARATOR));
    if (hit === undefined) {
      errors.push(`decision "${id}": "${rest}" matches none of its options`);
      continue;
    }
    const note = rest === hit ? "" : rest.slice(hit.length + NOTE_SEPARATOR.length);
    const answer = decision.options.includes(hit) ? hit : null;
    recorded.set(id, { answer, note: note === "" ? null : note });
  }
  return { recorded, errors };
}

const USAGE = "usage: plan.ts render <folder> | plan.ts answer <folder>  (answer reads a copy block on stdin)\n";

function loadPlan(folder: string): { plan: Plan | null; raw: unknown; errors: string[] } {
  const file = join(folder, "plan.json");
  if (!isFile(file)) return { plan: null, raw: null, errors: [`plan.json: not found in ${folder}`] };
  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(file, "utf-8"));
  } catch (e) {
    return { plan: null, raw: null, errors: [`plan.json: not valid JSON (${(e as Error).message})`] };
  }
  const parsed = parsePlan(raw);
  if (parsed.plan === null) return { ...parsed, raw };
  return { plan: parsed.plan, raw, errors: checkPlan(folder, parsed.plan) };
}

function report(errors: string[]): number {
  for (const error of errors) process.stderr.write(`plan: ${error}\n`);
  return 1;
}

export function main(argv: string[] = process.argv.slice(2)): number {
  const [cmd, dir, ...extra] = argv;
  if ((cmd !== "render" && cmd !== "answer") || dir === undefined || extra.length > 0) {
    process.stderr.write(USAGE);
    return 2;
  }
  const folder = resolve(dir);
  const loaded = loadPlan(folder);
  if (loaded.plan === null || loaded.errors.length > 0) return report(loaded.errors);
  let plan = loaded.plan;
  if (cmd === "answer") {
    const { recorded, errors } = parseAnswers(plan, readFileSync(0, "utf-8"));
    if (errors.length > 0) return report(errors);
    // Write the raw JSON back, so the file keeps the shape its author wrote.
    const rawDecisions = (loaded.raw as { decisions: Record<string, unknown>[] }).decisions;
    plan.decisions.forEach((d, i) => {
      const hit = recorded.get(d.id);
      if (hit) Object.assign(rawDecisions[i], hit);
    });
    writeFileSync(join(folder, "plan.json"), JSON.stringify(loaded.raw, null, 2) + "\n", "utf-8");
    plan = parsePlan(loaded.raw).plan ?? plan;
  }
  writeFileSync(join(folder, "plan.html"), renderPage(folder, plan), "utf-8");
  process.stdout.write(`plan: ok -> ${join(folder, "plan.html")}\n`);
  return 0;
}

function invokedDirectly(): boolean {
  const entry = process.argv[1];
  if (!entry) return false;
  try {
    return realpathSync(resolve(entry)) === SCRIPT;
  } catch {
    return false;
  }
}

if (invokedDirectly()) process.exitCode = main();
