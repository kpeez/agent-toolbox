#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Model-check the rex-agents mirror block lifecycle (RexMirror.tla) with TLC.

Exits 0 only when every run in RUNS gives its expected result: each rule holds
on the current code, each known finding still breaks, and each past bug and
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
SPEC = SKILL / "RexMirror.tla"
CHART = SKILL / "chart.cfg"

BASE = {
    "Mirrors": '{"m1"}',
    "Codes": "{0, 1}",
    "Kinds": '{"plain", "exec"}',
    "KillFrom": '"start"',
    "DelayZero": "FALSE",
    "LayerCanFail": "TRUE",
    "ReplyCanTimeOut": "FALSE",
    "EndOn": "TRUE",
    "EndFaults": "TRUE",
    "WaiterOn": "TRUE",
    "Watched": '"m1"',
    "Variant": '"fixed"',
}
# Two mirrors at delay 0, with no refused layer: a timer and a fallback for each would
# put the run above 10 million states.
TWO = {
    "Mirrors": '{"m1", "m2"}',
    "Kinds": '{"plain"}',
    "WaiterOn": "FALSE",
    "DelayZero": "TRUE",
    "LayerCanFail": "FALSE",
}

ALL_RULES = [
    "ExitLineWritten",
    "ReportsCommandStatus",
    "OneBlockPerMirror",
    "NoLostRow",
    "SettledBlockCloses",
    "EndPassClosesSettledRows",
    "NeverCloseWorking",
    "WaiterStartedOpenSeesOutcome",
    "LateWaiterSeesOutcome",
]
WAITER_RULES = {"WaiterStartedOpenSeesOutcome", "LateWaiterSeesOutcome"}


@dataclass
class Run:
    name: str
    kind: str  # "holds", "finding", "past bug", "past race", or "mutant"
    rules: list[str]
    overrides: dict[str, str] = field(default_factory=dict)
    config_file: Path | None = None  # a checked-in config, used as is

    @property
    def breaks(self) -> bool:
        return self.kind != "holds"


def holds(name: str, overrides: dict[str, str], without: set[str]) -> Run:
    return Run(name, "holds", [r for r in ALL_RULES if r not in without], overrides)


RUNS = [
    # The current code.
    holds(
        "current code, delay 0, one mirror, a stop at any step, late replies",
        {"DelayZero": "TRUE", "ReplyCanTimeOut": "TRUE"},
        {"LateWaiterSeesOutcome"},
    ),
    holds(
        "current code, delay above 0, one mirror, a stop at any step, late replies",
        {"ReplyCanTimeOut": "TRUE"},
        {"LateWaiterSeesOutcome"},
    ),
    holds(
        "current code, two mirrors",
        TWO,
        WAITER_RULES,
    ),
    # Findings in the current code. Each is replayed against the real code (SKILL.md).
    Run(
        "finding: a waiter that starts after the close gets 'not found'",
        "finding",
        ["LateWaiterSeesOutcome"],
    ),
    # Past bugs: the floating open as first written.
    Run(
        "the first floating open: at delay 0, a stop during the open leaves the block working",
        "past bug",
        ["ExitLineWritten"],
        {"Variant": '"floatAsWritten"', "DelayZero": "TRUE"},
    ),
    Run(
        "the first floating open: a new_layer reply after its client died opens a second block",
        "past bug",
        ["OneBlockPerMirror"],
        {"Variant": '"floatAsWritten"', "ReplyCanTimeOut": "TRUE"},
    ),
    Run(
        "the first floating open: of two blocks, one viewer crashes and leaves a settled block open",
        "past bug",
        ["SettledBlockCloses"],
        {"Variant": '"floatAsWritten"', "ReplyCanTimeOut": "TRUE"},
    ),
    Run(
        "the first floating open: a late reply leaves a block with no exit line, working forever",
        "past bug",
        ["ExitLineWritten"],
        {"Variant": '"floatAsWritten"', "ReplyCanTimeOut": "TRUE"},
    ),
    Run(
        "the first floating open: a late reply leaves a viewer that crashes before a waiter sees the status",
        "past bug",
        ["WaiterStartedOpenSeesOutcome"],
        {"Variant": '"floatAsWritten"', "ReplyCanTimeOut": "TRUE"},
    ),
    # Other past bugs: each variant is the code before its fix.
    Run(
        "the rewriting session_end: it loses a row that remember writes during the pass",
        "past bug",
        ["NoLostRow"],
        TWO | {"Variant": '"endPassRewrites"', "EndFaults": "FALSE"},
    ),
    Run(
        "the rewriting session_end: it drops the row of a block whose close failed",
        "past bug",
        ["NoLostRow"],
        {"Variant": '"endPassRewrites"'},
    ),
    Run(
        "2a8e0e6: the EXIT-trap wrapper loses the marker",
        "past bug",
        ["ReportsCommandStatus"],
        {"Variant": '"trapWrapper"', "Kinds": '{"exec"}'},
    ),
    Run(
        "d53f272: a mirror with no signal handlers leaves the block working",
        "past bug",
        ["ExitLineWritten"],
        {"Variant": '"noSignalHandlers"', "KillFrom": '"reading"'},
    ),
    Run(
        "d53f272: session_end aborts on one unreadable row",
        "past bug",
        ["EndPassClosesSettledRows"],
        TWO | {"Variant": '"endPassAborts"'},
    ),
    Run(
        "9338e63: the viewer never closes its block",
        "past bug",
        ["SettledBlockCloses"],
        {"Variant": '"noViewerClose"'},
    ),
    Run(
        "9338e63: session_end keeps error blocks",
        "past bug",
        ["EndPassClosesSettledRows"],
        {"Variant": '"endPassKeepsError"'},
    ),
    Run(
        "KP-678: remember creates its row file empty, and session_end skips a row it reads empty",
        "past race",
        ["EndPassClosesSettledRows"],
        {"Variant": '"rowNotAtomic"'},
    ),
    # The statechart's config must still parse, and its rules hold.
    Run(
        "the chart config (chart.cfg)",
        "holds",
        ["ExitLineWritten", "ReportsCommandStatus", "SettledBlockCloses", "NeverCloseWorking"],
        config_file=CHART,
    ),
    # Mutants for the rules that no past bug broke.
    Run(
        "mutant: the viewer closes before it reports the status",
        "mutant",
        ["NeverCloseWorking"],
        {"Variant": '"closeBeforeStatus"'},
    ),
    Run(
        "mutant: the viewer closes before it reports the status",
        "mutant",
        ["WaiterStartedOpenSeesOutcome"],
        {"Variant": '"closeBeforeStatus"'},
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


def config(run: Run) -> str:
    consts = BASE | run.overrides
    lines = ["CONSTANTS", *(f"  {k} = {v}" for k, v in consts.items())]
    lines += [
        "INIT Init",
        "NEXT Next",
        "CHECK_DEADLOCK FALSE",
        "INVARIANTS",
        *(f"  {r}" for r in run.rules),
    ]
    return "\n".join(lines) + "\n"


def check(run: Run, index: int, work: Path, jar: str, java: str) -> tuple[bool, str]:
    folder = work / str(index)
    folder.mkdir()
    (folder / "run.cfg").write_text(
        run.config_file.read_text() if run.config_file else config(run)
    )
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
    path = " -> ".join(re.findall(r"^State \d+: <(\w+)", out, re.MULTILINE))
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
    work = ROOT / ".agents" / "scratch" / f"verify-rex-mirror-{uuid.uuid4().hex[:8]}"
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
