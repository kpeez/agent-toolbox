#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Model-check the plugin rollout (PluginRollout.tla) with TLC.

Exits 0 only when every run in RUNS gives its expected result: each rule holds
on today's protocol, each known finding still breaks, and each past bug and
mutant breaks the rule it targets. For a rule that breaks, prints TLC's
shortest path as a list of actions.

TLC and Java: TLA2TOOLS and JAVA from the environment, or the statechart
skill's pins through .github/scripts/statechart_tlc.py.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
ROOT = SKILL.parent.parent.parent
SPEC = SKILL / "PluginRollout.tla"
CHART = SKILL / "chart.cfg"

TODAY_DIFFS = (
    '{"editCore", "addExtra", "addExtraClaudeOnly", "removeExtra",'
    ' "removeExtraKeepEntry", "fileInExtra", "nameExtraSkill"}'
)
BASE = {
    "ClaudeDirs": '{"c1"}',
    "ActiveDir": '"c1"',
    "HermesDirs": '{"h1", "h2"}',
    "PRs": '{"pr1"}',
    "Diffs": TODAY_DIFFS,
    "Variant": '"today"',
}
TWO_CLAUDE_DIRS = {"ClaudeDirs": '{"c1", "c2"}'}
TWO_PRS = {"PRs": '{"pr1", "pr2"}', "HermesDirs": '{"h1"}'}

ALL_RULES = [
    "DocStepsReachEveryFolder",
    "NeverLoadsUncommittedEdits",
    "FoldersListed",
    "EntriesPointAtFolders",
    "NoCrossPluginNames",
]


@dataclass
class Run:
    name: str
    kind: str
    rules: list[str]
    overrides: dict[str, str] = field(default_factory=dict)
    config_file: Path | None = None

    @property
    def breaks(self) -> bool:
        return self.kind != "holds"


def holds(name: str, overrides: dict[str, str], without: set[str]) -> Run:
    return Run(name, "holds", [r for r in ALL_RULES if r not in without], overrides)


RUNS = [
    holds(
        "today, one PR at a time, one Claude Code folder, two Hermes profiles",
        {},
        set(),
    ),
    holds(
        "today, two Claude Code folders", TWO_CLAUDE_DIRS, {"DocStepsReachEveryFolder"}
    ),
    holds(
        "today, two PRs open at once", TWO_PRS, {"FoldersListed", "NoCrossPluginNames"}
    ),
    Run(
        "finding: the Claude Code update steps reach only the active config folder",
        "finding",
        ["DocStepsReachEveryFolder"],
        TWO_CLAUDE_DIRS,
    ),
    Run(
        "finding: two PRs pass checks on different bases and merge into an unlisted plugin folder",
        "finding",
        ["FoldersListed"],
        TWO_PRS,
    ),
    Run(
        "finding: two PRs pass checks on different bases and merge into a cross-plugin name",
        "finding",
        ["NoCrossPluginNames"],
        TWO_PRS,
    ),
    Run(
        "2352b4b, fixed by f02383d: a content change keeps the version, and the update skips it",
        "past bug",
        ["DocStepsReachEveryFolder"],
        {"Variant": '"versionKey"', "Diffs": '{"editCore", "editCoreBump"}'},
    ),
    Run(
        "2026-11-19, fixed by 94537ee: a Hermes profile loads an agent's edits from the checkout",
        "past bug",
        ["NeverLoadsUncommittedEdits"],
        {"Variant": '"externalDirs"'},
    ),
    Run(
        "7bbb754, fixed by 0f729df: a new plugin is listed in the Claude Code catalog only",
        "past bug",
        ["FoldersListed"],
        {"Variant": '"noCatalogCheck"', "Diffs": '{"editCore", "addExtraClaudeOnly"}'},
    ),
    Run(
        "before 3cb84a7: a plugin names another plugin's skill",
        "past bug",
        ["NoCrossPluginNames"],
        {"Variant": '"noIsolationCheck"'},
    ),
    Run(
        "mutant: the catalog check skips entries whose folder is gone",
        "mutant",
        ["EntriesPointAtFolders"],
        {"Variant": '"listedOnlyCheck"'},
    ),
    Run(
        "the chart config (chart.cfg)",
        "finding",
        ["DocStepsReachEveryFolder"],
        config_file=CHART,
    ),
    Run(
        "the chart config (chart.cfg)",
        "holds",
        [r for r in ALL_RULES if r != "DocStepsReachEveryFolder"],
        config_file=CHART,
    ),
]


def tlc() -> tuple[str, str]:
    jar, java = os.environ.get("TLA2TOOLS"), os.environ.get("JAVA")
    if jar:
        return jar, java or "java"
    out = subprocess.run(
        ["uv", "run", str(ROOT / ".github" / "scripts" / "statechart_tlc.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    found = dict(line.split("=", 1) for line in out.splitlines() if "=" in line)
    return found["TLA2TOOLS"], found["JAVA"]


def chart_constants() -> dict[str, str]:
    lines = CHART.read_text().splitlines()
    pairs = (
        line.split("=", 1) for line in lines if line.startswith("  ") and "=" in line
    )
    return {k.strip(): v.strip() for k, v in pairs}


def config(run: Run) -> str:
    consts = chart_constants() if run.config_file else BASE | run.overrides
    lines = ["CONSTANTS", *(f"  {k} = {v}" for k, v in consts.items())]
    lines += [
        "INIT Init",
        "NEXT Next",
        "CHECK_DEADLOCK FALSE",
        "INVARIANTS",
        *(f"  {r}" for r in run.rules),
    ]
    return "\n".join(lines) + "\n"


def fields(value: str) -> dict[str, str]:
    return dict(re.findall(r'(\w+) \|-> "?(\w+)"?', value))


def trace(out: str) -> str:
    steps, before = [], {}
    for block in re.split(r"^State \d+: ", out, flags=re.MULTILINE)[1:]:
        action = re.match(r"<(\w+)", block)[1]
        now = {
            k: fields(v)
            for k, v in re.findall(r"^/\\ (pr|diff|ran) = (.*)$", block, re.MULTILINE)
        }
        moved = [
            k for k, v in now.get("pr", {}).items() if before.get("pr", {}).get(k) != v
        ]
        ran = [
            k
            for k, v in now.get("ran", {}).items()
            if v == "TRUE" and before.get("ran", {}).get(k) != v
        ]
        if action == "PrOpens":
            action += f"({moved[0]}: {now['diff'][moved[0]]})"
        elif action == "ChecksRun":
            action += f"({moved[0]}: {now['pr'][moved[0]]})"
        elif action == "PrMerges":
            action += f"({moved[0]})"
        elif action in ("ClaudeUpdates", "HermesInstalls") and ran:
            action += f"({ran[0]})"
        steps.append(action)
        before = now
    return " -> ".join(steps)


def check(run: Run, index: int, work: Path, jar: str, java: str) -> tuple[bool, str]:
    folder = work / str(index)
    folder.mkdir()
    (folder / "run.cfg").write_text(config(run))
    shutil.copy(SPEC, folder / SPEC.name)
    r = subprocess.run(
        [
            java,
            "-XX:+UseParallelGC",
            # TLC writes its standard modules to the temp folder; a shared one races across runs.
            f"-Djava.io.tmpdir={folder}",
            "-cp",
            jar,
            "tlc2.TLC",
            "-workers",
            "1",
            "-deadlock",
            "-metadir",
            str(folder / "states"),
            "-config",
            "run.cfg",
            SPEC.name,
        ],
        check=False,
        cwd=folder,
        capture_output=True,
        text=True,
    )
    out = r.stdout + r.stderr
    broken = re.findall(r"Invariant (\w+) is violated", out)
    # The last match: TLC's Progress lines print running counts first.
    states = re.findall(r"([\d,]+) distinct states found", out)
    count = f"{int(states[-1].replace(',', '')):,}" if states else "?"
    if r.returncode not in (0, 12) or (r.returncode == 12) != bool(broken):
        return False, f"TLC failed (exit {r.returncode}):\n{out[-2000:]}"
    path = trace(out)
    if run.breaks:
        ok = broken == run.rules
        detail = (
            f"{run.rules[0]} breaks, path: {path}"
            if broken
            else f"{run.rules[0]} holds"
        )
    else:
        ok = not broken
        detail = (
            f"{len(run.rules)} rules hold, {count} states"
            if ok
            else f"{broken[0]} breaks, path: {path}"
        )
    return ok, detail


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--keep", action="store_true", help="keep the TLC configs and output folder"
    )
    args = parser.parse_args()
    jar, java = tlc()
    work = (
        ROOT / ".agents" / "scratch" / f"verify-plugin-rollout-{uuid.uuid4().hex[:8]}"
    )
    work.mkdir(parents=True)
    try:
        with ThreadPoolExecutor(max_workers=os.cpu_count() or 2) as pool:
            results = list(
                pool.map(
                    lambda ir: check(ir[1], ir[0], work, jar, java), enumerate(RUNS)
                )
            )
    finally:
        if args.keep:
            print(f"kept {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)
    failed = 0
    for run, (ok, detail) in zip(RUNS, results):
        failed += not ok
        print(f"{'PASS' if ok else 'FAIL'} [{run.kind}] {run.name}: {detail}")
    if failed:
        print(
            f"{failed} run(s) did not give the expected result. Read SKILL.md, 'When the check fails'."
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
