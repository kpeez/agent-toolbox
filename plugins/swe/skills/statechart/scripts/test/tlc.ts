import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { PINNED_FLAGS } from "../run.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const jar = process.env.TLA2TOOLS;
export const skip = !jar && "set TLA2TOOLS to the path of tla2tools.jar to run TLC";

const RULES = /^(INVARIANTS?|PROPERTY|PROPERTIES|CHECK_DEADLOCK)$/;

const spawnText = (
  file: string,
  args: string[],
  options: { cwd?: string; env?: NodeJS.ProcessEnv },
) =>
  new Promise<{ status: number | null; stdout: string; stderr: string }>((resolve) =>
    execFile(
      file,
      args,
      { ...options, encoding: "utf8", maxBuffer: 1 << 30 },
      (error, stdout, stderr) =>
        resolve({
          status: !error ? 0 : typeof error.code === "number" ? error.code : null,
          stdout,
          stderr,
        }),
    ),
  );

const exitClass = (status: number | null) =>
  status === 0 ? 0 : status === 11 || status === 12 || status === 13 ? 1 : 2;

const stepsIn = (text: string) =>
  Math.max((text.match(/^State \d+: (?!Stuttering$)/gm)?.length ?? 0) - 1, 0) +
  (text.match(/^Back to state \d+: </gm)?.length ?? 0);

function listed(cfg: string, sections: RegExp) {
  const names: string[] = [];
  let section = "";
  for (const line of cfg.split("\n")) {
    section = line.match(/^[A-Z_]+/)?.[0] ?? section;
    if (sections.test(section))
      for (const word of line.trim().split(/\s+/)) if (word && word !== section) names.push(word);
  }
  return names;
}

const properties = (cfg: string) => listed(cfg, /^PROPERT(Y|IES)$/);

const deadlockName = (cfg: string) =>
  listed(cfg, /^(INVARIANTS?|PROPERTY|PROPERTIES)$/).includes("NoDeadlock")
    ? "CHECK_DEADLOCK"
    : "NoDeadlock";

async function tlc(dir: string, module: string, cfg: string) {
  const tmp = fs.mkdtempSync(path.join(dir, "alone-"));
  const file = `${tmp}.cfg`;
  fs.writeFileSync(file, cfg);
  const r = await spawnText(
    process.env.JAVA ?? "java",
    [
      `-Djava.io.tmpdir=${tmp}`,
      "-cp",
      jar ?? "",
      "tlc2.TLC",
      ...PINNED_FLAGS,
      "-config",
      file,
      "-metadir",
      `${tmp}-meta`,
      module,
    ],
    { cwd: dir },
  );
  const out = r.stdout + r.stderr;
  const temporal = properties(cfg);
  const broke =
    out.match(/^Error: (?:Invariant|Action property|Property) (\S+) is violated/m)?.[1] ??
    (/^Error: Deadlock reached\./m.test(out) ? deadlockName(cfg) : undefined) ??
    (/^Error: Temporal properties were violated\./m.test(out) && temporal.length === 1
      ? temporal[0]
      : undefined);
  return { status: r.status, out, broke, steps: stepsIn(out) };
}

function alone(cfg: string, rule: string) {
  const lines: string[] = [];
  let section = "";
  for (const line of cfg.split("\n")) {
    section = line.match(/^[A-Z_]+/)?.[0] ?? section;
    if (!RULES.test(section)) lines.push(line);
  }
  if (rule !== deadlockName(cfg))
    lines.push(
      `${properties(cfg).includes(rule) ? "PROPERTY" : "INVARIANT"} ${rule}`,
      "CHECK_DEADLOCK FALSE",
    );
  return `${lines.join("\n")}\n`;
}

export type Verdict = {
  status: number | null;
  distinct: number;
  breaks: Map<string, number>;
  holds: string[];
  unchecked: string[];
  chart: string;
  report: string;
};

export async function agrees(
  module: string,
  files: { [name: string]: string[] },
  cfg: string,
  {
    view,
    command = [process.execPath, path.join(here, "../statechart.ts")],
    env = {},
  }: { view?: string; command?: string[]; env?: NodeJS.ProcessEnv } = {},
): Promise<Verdict> {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "statechart-plain-"));
  try {
    for (const [name, lines] of Object.entries(files))
      fs.writeFileSync(path.join(dir, `${name}.tla`), `${lines.join("\n")}\n`);
    fs.writeFileSync(path.join(dir, `${module}.cfg`), cfg);
    const out = path.join(dir, "out");
    const [file, ...entry] = command;
    const [cli, plain] = await Promise.all([
      spawnText(
        file,
        [
          ...entry,
          path.join(dir, `${module}.tla`),
          ...(view ? ["--view", view] : []),
          "--out",
          out,
        ],
        { env: { ...process.env, ...env } },
      ),
      tlc(dir, module, cfg),
    ]);
    const report = fs.existsSync(out) ? fs.readFileSync(path.join(out, "report.md"), "utf8") : "";
    const shown = `${cli.stderr}${report}`;
    assert.equal(
      cli.status,
      exitClass(plain.status),
      `TLC says:\n${plain.out}\nThe command says:\n${shown}`,
    );
    assert.doesNotMatch(shown, /Chart\w*Mark/);
    if (cli.status !== 2) assert.equal(cli.stderr, "");
    if (!report) assert.match(cli.stderr, /TLC could not check/);
    if (cli.status === 2) {
      const error = plain.out.match(/^Error: .*$/m)?.[0];
      assert.ok(
        error && shown.includes(error),
        `TLC says:\n${plain.out}\nThe command says:\n${shown}`,
      );
    }

    for (const name of fs.existsSync(out) ? fs.readdirSync(out) : []) {
      const text = fs.readFileSync(path.join(out, name), "utf8");
      assert.doesNotMatch(text, /@!@!@/, name);
      if (/^tlc-.+\.out$/.test(name)) assert.match(text, /^TLC2 Version /, name);
    }
    const breaks = new Map<string, number>();
    const bounded = new Set<string>();
    for (const [, rule, body] of report.matchAll(/^## (\S+) breaks\n(.*)$/gm)) {
      const said = body.match(/has (\d+) steps?:/)?.[1];
      const file = body.match(/ is in (tlc-\S+\.out)\./)?.[1];
      if (!file) {
        breaks.set(rule, Number(said));
        continue;
      }
      const text = fs.readFileSync(path.join(out, file), "utf8");
      if (said) assert.equal(Number(said), stepsIn(text), rule);
      if (/^Semantic processing of module ChartBound$/m.test(text)) bounded.add(rule);
      breaks.set(rule, stepsIn(text));
    }
    const list = (title: string) =>
      report
        .match(new RegExp(`^## ${title}\\n(.*)$`, "m"))?.[1]
        .split(", ")
        .sort() ?? [];
    const holds = list("Rules that hold");
    const unchecked = list("Rules not checked");
    const chartFile = path.join(out, "chart.mmd");
    const chart = fs.existsSync(chartFile) ? fs.readFileSync(chartFile, "utf8") : "";
    const named = [...listed(cfg, RULES), deadlockName(cfg)];
    if (plain.broke && named.includes(plain.broke))
      assert.equal(breaks.get(plain.broke), plain.steps, shown);
    else if (plain.broke) assert.ok([...breaks.values()].includes(plain.steps), shown);
    const [held, broken] = await Promise.all([
      Promise.all(holds.map((rule) => tlc(dir, module, alone(cfg, rule)))),
      Promise.all([...breaks.keys()].map((rule) => tlc(dir, module, alone(cfg, rule)))),
    ]);
    holds.forEach((rule, i) =>
      assert.equal(held[i].status, 0, `${rule} holds in the report, but TLC says:\n${held[i].out}`),
    );
    [...breaks].forEach(([rule, steps], i) => {
      const r = broken[i];
      assert.ok(r.broke, `${rule} breaks in the report, but TLC says:\n${r.out}`);
      if (!bounded.has(rule)) assert.equal(steps, r.steps, rule);
    });
    const distinct = Number(
      plain.out.match(/^\d+ states generated, (\d+) distinct states found/m)?.[1],
    );
    return { status: cli.status, distinct, breaks, holds, unchecked, chart, report };
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
}
