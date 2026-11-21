#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run the skill evals through `claude plugin eval`, then capture, score, and report them.

`plan` prints the frozen configuration and the run list and launches nothing.
`run` launches each planned (case, arm, repeat) once and keeps its transcript, stream, and final files.
`canary` runs probe prompts whose streams a person reads before a baseline.
`score` captures and scores every kept run, with relevant-action labels when given, and writes report.json.
The pipeline steps are `skill_eval.py` functions; this file adds the plugin-eval launch around them.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import skill_eval as se

ARMS = ("hook-on", "hook-off")
RUNTIME = HERE / "runtime.plugin-eval.json"
# The plugins each session loads. The checked-out catalog also has rex-agents, which the runner choice left out.
LOADED_PLUGINS = ("swe", "lab", "uni")
# case.yaml lists the runtime's tools; Write and Edit are gated, so --allow-tools also grants them; --disallow-tools
# removes the default tools the runtime does not list. A runtime may add the Agent tool (named Task in the session)
# to the six tools below.
CASE_TOOLS = ("Read", "Glob", "Grep", "Skill", "Write", "Edit")
ALLOW_TOOLS = ("Write", "Edit")
DISALLOW_TOOLS = ("Task", "TaskStop", "NotebookEdit", "ToolSearch")
MAX_CONSECUTIVE_FAILURES = 3
EFFORT_FIELD = re.compile(rb'"effort"\s*:\s*"([a-z]+)"')
KEPT_LINE = re.compile(r"kept (/\S+?): ")
# Capture outputs that `score` writes again from the kept files on every pass.
CAPTURE_OUTPUTS = (
    "raw.jsonl",
    "raw-stream.jsonl",
    "raw-subagents",
    "capture.json",
    "final-files",
    "evidence.json",
    "score.json",
)
CANARIES = {
    "read-outside": "Read the file {sentinel} and quote its first line exactly.",
    "write-outside": "Write the text 'canary' to the file {target}, then say done.",
}


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def save_json(path, value):
    """Write JSON through a temporary file, so a concurrent reader never sees a half-written file."""
    path = Path(path)
    tmp = path.with_name(f"{path.name}.{secrets.token_hex(4)}.tmp")
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return {
        "k": k,
        "n": n,
        "rate": p,
        "low": max(0.0, centre - half),
        "high": min(1.0, centre + half),
    }


def claude_path():
    return os.environ.get("SKILL_EVAL_CLAUDE") or shutil.which("claude") or "claude"


def cli_version():
    out = subprocess.run(
        [claude_path(), "--version"], capture_output=True, text=True, check=True
    ).stdout
    return out.split()[0] if out.split() else ""


def load_runtime(path):
    runtime = se.read_json(path)
    missing = (
        se.RUNTIME_FIELDS | {"max_turns", "timeout_seconds", "per_run_stop_usd"}
    ) - runtime.keys()
    if missing:
        raise ValueError(f"runtime is missing {sorted(missing)}")
    if not set(CASE_TOOLS) <= set(runtime["tools"]):
        raise ValueError(f"runtime tools must include {sorted(CASE_TOOLS)}")
    return runtime


def plan_runs(cases, arms, repeats):
    """Repeat-major, then case, then arm, so any stop leaves the arms within one run of each other."""
    return [
        {"case": case, "arm": arm, "repeat": repeat}
        for repeat in range(1, repeats + 1)
        for case in cases
        for arm in arms
    ]


def run_dir(out, item):
    return out / "runs" / item["case"] / item["arm"] / f"r{item['repeat']}"


def finished(run):
    """A run that ended on an API error is not finished: a resume moves it to interrupted/ and launches it again."""
    if not (run / "run.json").is_file():
        return False
    record = se.read_json(run / "run.json")
    return bool(record.get("ended_at")) and not record.get("api_error")


def frozen_config(args, runtime, cases):
    catalog = se.inventory(se.REPO / "plugins")
    corpus_cases = {c["id"]: c for c in se.corpus(args.corpus)}
    fixtures = {
        fixture: se.inventory(se.contained(se.fixtures_root(args.corpus), fixture))
        for fixture in sorted({corpus_cases[cid]["fixture"] for cid in cases})
    }
    git = ["git", "-C", str(se.REPO)]
    config = {
        "schema_version": 2,
        "runner": "claude plugin eval",
        "runtime": runtime,
        "cli_version": cli_version(),
        "loaded_plugins": list(LOADED_PLUGINS),
        "cases": cases,
        "arms": list(args.arms),
        "repeats": args.repeats,
        "git_sha": subprocess.run(
            [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip(),
        "git_dirty_paths": subprocess.run(
            [*git, "status", "--porcelain", "--", "plugins", "evals/skills"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines(),
        "source_catalog_sha256": se.digest(
            json.dumps(catalog, sort_keys=True).encode()
        ),
        "corpus_sha256": se.digest(Path(args.corpus).read_bytes()),
        "fixtures_sha256": se.digest(json.dumps(fixtures, sort_keys=True).encode()),
        "harness_sha256": {
            name: se.digest((HERE / name).read_bytes())
            for name in ("run_eval.py", "skill_eval.py", "facets.json")
        },
        "order": "repeat-major, then case, then arm",
    }
    config["config_sha256"] = se.digest(json.dumps(config, sort_keys=True).encode())
    return config


def selected_cases(corpus_path, wanted):
    known = [c["id"] for c in se.corpus(corpus_path)]
    if set(wanted or ()) - set(known):
        raise ValueError(f"unknown case: {sorted(set(wanted) - set(known))}")
    return [c for c in known if not wanted or c in wanted]


def spend(out, reserve, active=frozenset()):
    """Known cost of every launch so far, plus `reserve` for each launch whose cost is unknown.

    `active` names run folders whose launch is in flight; the caller counts those itself."""
    known, unknown = 0.0, 0
    records = [
        *out.glob("runs/*/*/*/run.json"),
        *out.glob("canaries/*/*/run.json"),
        *out.glob("interrupted/*/run.json"),
    ]
    for record in records:
        if record.parent in active:
            continue
        cost = se.read_json(record).get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            known += cost
        else:
            unknown += 1
    return {
        "known_usd": known,
        "unknown_cost_runs": unknown,
        "worst_case_usd": known + unknown * reserve,
    }


def write_case(run, case_id, prompt, runtime):
    """A plugin-eval suite beside the materialized snapshot: copies of the loaded plugins and one case folder."""
    suite = run / "suite"
    for plugin in LOADED_PLUGINS:
        shutil.copytree(run / "inputs" / "plugins" / plugin, suite / plugin)
    case_dir = suite / "evals" / case_id
    case_dir.mkdir(parents=True)
    (case_dir / "fixture.sh").write_text(
        "#!/bin/bash\nset -euo pipefail\ncp -R "
        + shlex.quote(str(run / "workspace"))
        + "/. .\n",
        encoding="utf-8",
    )
    plugins = ", ".join(json.dumps(f"../../{p}") for p in LOADED_PLUGINS)
    yaml = [
        'schema_version: "1.1"',
        f"name: {case_id}",
        f"plugins: [{plugins}]",
        "runs: 1",
        "execution:",
        f"  prompt: {json.dumps(prompt, ensure_ascii=False)}",
        f"  max_turns: {runtime['max_turns']}",
        f"  timeout_seconds: {runtime['timeout_seconds']}",
        f"  allowed_tools: [{', '.join(runtime['tools'])}]",
        "context:",
        "  scaffold_script: fixture.sh",
        # skill_eval.py scores the kept transcript. Plugin eval needs one grader, so this one always passes.
        "graders:",
        "  - name: placeholder",
        "    type: tool_used",
        "    tool: Read",
        "    min: 0",
    ]
    (case_dir / "case.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")
    return suite


def launch_argv(suite, case_id, run, runtime):
    return [
        claude_path(),
        "plugin",
        "eval",
        str(suite),
        "--case",
        case_id,
        "--ablation",
        "none",
        "--runs",
        "1",
        "--scaffold",
        "--trust-plugin",
        "--no-publish",
        "--allow-tools",
        *ALLOW_TOOLS,
        "--disallow-tools",
        *(t for t in DISALLOW_TOOLS if t not in runtime["tools"]),
        "--max-cost-usd",
        str(runtime["per_run_stop_usd"]),
        "--model",
        runtime["model"],
        "--keep-temp",
        "--threshold",
        "0",
        "--json",
        str(run / "plugin-eval.json"),
        "--report",
        str(run / "plugin-eval.html"),
        "--output-dir",
        str(run / "plugin-eval-results"),
    ]


def first_attempt(result):
    return (
        (((result or {}).get("cases") or [{}])[0].get("arms") or {}).get("with") or [{}]
    )[0]


def kept_dir(result, log):
    """The sandbox folder plugin eval kept: the parent of `out/trace.jsonl`, else the one path its log printed."""
    trace = first_attempt(result).get("tracePath")
    if trace:
        return Path(trace).parents[1]
    found = KEPT_LINE.findall(log)
    return Path(found[0]) if len(found) == 1 else None


def stream_events(stream):
    for line in stream.read_bytes().split(b"\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict):
            yield event


def init_event(stream):
    return next(
        (
            e
            for e in stream_events(stream)
            if e.get("type") == "system" and e.get("subtype") == "init"
        ),
        None,
    )


def last_result(stream):
    found = None
    for event in stream_events(stream):
        if event.get("type") == "result":
            found = event
    return found


def hook_events(stream):
    """One entry per hook id, from the hook_started and hook_response stream events.

    The events name the hook (`SessionStart:startup`) but not its plugin, so a
    hook that completed is attributed to the plugin whose frozen hook text its
    output carries.
    """
    seen = {}
    for event in stream_events(stream):
        if event.get("type") != "system" or event.get("subtype") not in {
            "hook_started",
            "hook_response",
        }:
            continue
        key = event.get("hook_id") or event.get("uuid")
        entry = seen.setdefault(
            key,
            {
                "event": event.get("hook_event")
                or str(event.get("hook_name", "")).split(":")[0],
                "name": event.get("hook_name"),
                "started": False,
                "completed": False,
                "outcome": None,
                "output": "",
            },
        )
        if event["subtype"] == "hook_started":
            entry["started"] = True
        else:
            entry["completed"] = True
            entry["outcome"] = event.get("outcome")
            entry["output"] = event.get("output") or event.get("stdout") or ""
    return list(seen.values())


def hook_summary(events, hooks):
    """`hooks` maps each plugin to its frozen session-start.md path (hook-on only)."""
    texts = {
        plugin: Path(frozen["path"]).read_text(encoding="utf-8").strip()
        for plugin, frozen in hooks.items()
    }
    summary = []
    for event in events:
        out = event["output"].strip()
        plugin = next(
            (p for p, text in texts.items() if out and text.startswith(out)), None
        )
        summary.append(
            {k: v for k, v in event.items() if k != "output"} | {"plugin": plugin}
        )
    return summary


def arm_violations(arm, summary, plugins):
    """`plugins` names every plugin whose SessionStart hook the hook-on manifest froze."""
    if arm == "hook-off":
        return [
            f"hook-off run, but a {h['name']} hook ran"
            for h in summary
            if h["started"] or h["completed"]
        ]
    succeeded = {
        h["plugin"]
        for h in summary
        if h["event"] == "SessionStart" and h["completed"] and h["outcome"] == "success"
    }
    missing = (
        sorted(set(plugins) - succeeded) if plugins else ["(no plugin hook frozen)"]
    )
    return (
        [f"hook-on run, but no SessionStart hook succeeded for {missing}"]
        if missing
        else []
    )


def session_checks(run, arm, runtime, manifest):
    """Check the kept session against the frozen runtime. Any violation stops the batch."""
    stream, transcript = (
        run / "kept" / "stream.jsonl",
        run / "kept" / "transcript.jsonl",
    )
    init = init_event(stream)
    if init is None:
        return {"violations": ["the stream has no init event"]}
    names = [p.get("name") for p in init.get("plugins") or []]
    efforts = sorted(
        {m.decode() for m in EFFORT_FIELD.findall(transcript.read_bytes())}
    )
    hooks = manifest.get("hooks", {}) if arm == "hook-on" else {}
    summary = hook_summary(hook_events(stream), hooks)
    found = []
    if init.get("claude_code_version") != runtime["cli_version"]:
        found.append(f"claude_code_version is {init.get('claude_code_version')}, not {runtime['cli_version']}")
    if init.get("model") != runtime["model"]:
        found.append(f"model is {init.get('model')}, not {runtime['model']}")
    if sorted(init.get("tools") or []) != sorted(runtime["tools"]):
        found.append(
            f"tools are {sorted(init.get('tools') or [])}, not {sorted(runtime['tools'])}"
        )
    if init.get("mcp_servers"):
        found.append(f"mcp_servers is not empty: {init['mcp_servers']}")
    if set(LOADED_PLUGINS) - set(names):
        found.append(f"plugins {sorted(set(LOADED_PLUGINS) - set(names))} did not load")
    if efforts != [runtime["effort"]]:
        found.append(f"transcript effort is {efforts}, not [{runtime['effort']!r}]")
    found += arm_violations(arm, summary, sorted(hooks))
    return {
        "model": init.get("model"),
        "tools": sorted(init.get("tools") or []),
        "plugins": names,
        "efforts": efforts,
        "hooks": summary,
        "violations": found,
    }


def keep(run, kept):
    """Copy the transcript, stream, and final working folder out of the sealed sandbox, then delete it."""
    os.chmod(kept, 0o700)
    if (kept / "sealed").exists():
        os.chmod(kept / "sealed", 0o700)
    transcripts = sorted(kept.glob("config/projects/*/*.jsonl"))
    if len(transcripts) != 1:
        raise ValueError(
            f"expected one session transcript in {kept}, found {len(transcripts)}"
        )
    target = run / "kept"
    target.mkdir()
    shutil.copyfile(transcripts[0], target / "transcript.jsonl")
    subagents = transcripts[0].with_suffix("") / "subagents"
    if subagents.is_dir():
        shutil.copytree(subagents, target / "transcript" / "subagents", symlinks=True)
    data = (kept / "out" / "trace.jsonl").read_bytes()
    appended = bool(data) and not data.endswith(b"\n")
    (target / "stream.jsonl").write_bytes(data + b"\n" if appended else data)
    # capture copies <run>/workspace into final-files, so the workspace becomes the agent's final working folder.
    # Copy first, so a failed copy leaves the fixture in place. On any failure the sandbox stays for a person.
    final = run / "workspace.final"
    shutil.copytree(kept / "sealed" / "home" / "cwd", final, symlinks=True)
    shutil.rmtree(run / "workspace")
    final.rename(run / "workspace")
    shutil.rmtree(kept)
    return appended


class Batch:
    """Budget and stop state shared by the launch workers."""

    def __init__(self, out, runtime, max_total_usd):
        self.out, self.runtime, self.max_total = out, runtime, max_total_usd
        self.lock = threading.Lock()
        self.active = set()
        self.failures = 0
        self.stop = (
            se.read_json(out / "stop.json") if (out / "stop.json").exists() else None
        )

    def reserve(self, run):
        stop_usd = self.runtime["per_run_stop_usd"]
        with self.lock:
            if self.stop:
                return False
            if run.exists():
                # An earlier launch stopped part way. Move it aside under the lock, so every check counts it.
                aside = self.out / "interrupted" / f"{'-'.join(run.relative_to(self.out).parts[1:])}-{secrets.token_hex(3)}"
                aside.parent.mkdir(parents=True, exist_ok=True)
                run.rename(aside)
            worst = (
                spend(self.out, stop_usd, self.active)["worst_case_usd"]
                + (len(self.active) + 1) * stop_usd
            )
            if worst > self.max_total:
                self.halt(
                    f"budget: worst case ${worst:.2f} with the next launch is over ${self.max_total:.2f}"
                )
                return False
            self.active.add(run)
            return True

    def release(self, run, record):
        with self.lock:
            self.active.discard(run)
            cost, cap = record.get("cost_usd"), self.runtime["per_run_stop_usd"]
            if record.get("violations"):
                self.halt(f"{record['run']}: {record['violations']}")
            elif cost is None or cost > cap:
                self.halt(f"{record['run']}: cost {cost} is unknown or over ${cap}")
            failed = record.get("error") or record.get("api_error")
            self.failures = self.failures + 1 if failed else 0
            if self.failures >= MAX_CONSECUTIVE_FAILURES:
                self.halt(f"{self.failures} runs in a row ended with an error")

    def halt(self, reason):
        if not self.stop:
            self.stop = {"at": now(), "reason": reason}
            save_json(self.out / "stop.json", self.stop)


def launch(run, case_id, arm, runtime, prompt=None):
    """Materialized run folder in, run.json out. The caller holds a budget reservation for this launch."""
    manifest = se.read_json(run / "manifest.json")
    prompt = prompt or (run / "inputs" / "prompt.txt").read_text(
        encoding="utf-8"
    ).rstrip("\n")
    suite = write_case(run, case_id, prompt, runtime)
    record = {
        "run": str(run),
        "case": case_id,
        "arm": arm,
        "started_at": now(),
        "cost_usd": None,
        "error": None,
    }
    save_json(run / "run.json", record)
    env = os.environ | {"CLAUDE_CODE_EFFORT_LEVEL": runtime["effort"]}
    try:
        proc = subprocess.run(
            launch_argv(suite, case_id, run, runtime),
            check=False,
            env=env,
            cwd=run,
            capture_output=True,
            text=True,
            timeout=runtime["timeout_seconds"] + 600,
        )
        log = proc.stdout + proc.stderr
        record["exit_code"] = proc.returncode
    except subprocess.TimeoutExpired as error:
        log = f"{error.stdout or ''}{error.stderr or ''}"
        record["error"] = "plugin eval did not exit in time"
    (run / "plugin-eval.log").write_text(log, encoding="utf-8")
    result = (
        se.read_json(run / "plugin-eval.json")
        if (run / "plugin-eval.json").is_file()
        else None
    )
    attempt = first_attempt(result)
    cost = attempt.get("costUsd")
    record["cost_usd"] = (
        cost if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
    )
    record["error"] = (
        record["error"]
        or attempt.get("error")
        or (None if result else "no plugin-eval result")
    )
    record["turns"] = attempt.get("turns")
    kept = kept_dir(result, log)
    if kept is None or not kept.is_dir():
        record["error"] = record["error"] or "plugin eval kept no sandbox folder"
    else:
        try:
            record["stream_appended_final_newline"] = keep(run, kept)
            record.update(session_checks(run, arm, runtime, manifest))
            final = last_result(run / "kept" / "stream.jsonl") or {}
            record["stream_cost_usd"] = final.get("total_cost_usd")
            if final.get("terminal_reason") == "api_error":
                record["api_error"] = final.get("api_error") or final.get("api_error_type") or "api_error"
        except (OSError, ValueError) as error:
            record["error"] = record["error"] or f"keeping the sandbox failed: {error}"
    record["ended_at"] = now()
    save_json(run / "run.json", record)
    return record


def prepare(out, item, args):
    run = run_dir(out, item)
    run.parent.mkdir(parents=True, exist_ok=True)
    se.materialize(
        Namespace(
            corpus=args.corpus,
            case=item["case"],
            runtime=args.runtime,
            output=run,
            output_root=out,
            hook_arm=item["arm"],
        )
    )
    return run


def check_config(out, config):
    path = out / "config.json"
    if path.exists():
        if se.read_json(path)["config_sha256"] != config["config_sha256"]:
            raise ValueError(f"{path} froze a different configuration; use a new --out")
    else:
        out.mkdir(parents=True, exist_ok=True)
        save_json(path, config)


def execute(args):
    runtime = load_runtime(args.runtime)
    out = args.out.resolve()
    cases = selected_cases(args.corpus, args.case)
    config = frozen_config(args, runtime, cases)
    if config["cli_version"] != runtime["cli_version"]:
        raise ValueError(
            f"claude is {config['cli_version']}, the runtime froze {runtime['cli_version']}"
        )
    check_config(out, config)
    batch = Batch(out, runtime, args.max_total_usd)
    plan = plan_runs(cases, args.arms, args.repeats)

    def one(item):
        run = run_dir(out, item)
        if finished(run) or not batch.reserve(run):
            return
        try:
            prepare(out, item, args)
            record = launch(run, item["case"], item["arm"], runtime)
        except Exception as error:
            # Unknown cost and an error: release stops the batch, and a resume counts the run at the stop amount.
            batch.release(run, {"run": str(run), "cost_usd": None, "error": f"runner failed: {error!r}"})
            raise
        batch.release(run, record)
        if record.get("error") or record.get("api_error"):
            print(
                json.dumps({k: record.get(k) for k in ("case", "arm", "cost_usd", "error", "api_error")}),
                file=sys.stderr,
                flush=True,
            )

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        list(pool.map(one, plan))
    return {
        "planned": len(plan),
        "finished": sum(finished(run_dir(out, i)) for i in plan),
        "spend": spend(out, runtime["per_run_stop_usd"]),
        "stopped": batch.stop,
    }


def canary(args):
    """Probe runs a person reads by hand: an outside read, an outside write, and each listed dev case."""
    runtime = load_runtime(args.runtime)
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    batch = Batch(out, runtime, args.max_total_usd)
    results = []
    probes = [
        (name, args.fixture_case, template) for name, template in CANARIES.items()
    ]
    probes += [(case_id, case_id, None) for case_id in args.case or ()]
    for name, case_id, template in probes:
        for arm in args.arms:
            run = out / "canaries" / name / arm
            if (run / "run.json").is_file():
                continue
            if not batch.reserve(run):
                return {
                    "results": results,
                    "spend": spend(out, runtime["per_run_stop_usd"]),
                    "stopped": batch.stop,
                }
            run.parent.mkdir(parents=True, exist_ok=True)
            se.materialize(
                Namespace(
                    corpus=args.corpus,
                    case=case_id,
                    runtime=args.runtime,
                    output=run,
                    output_root=out,
                    hook_arm=arm,
                )
            )
            prompt = None
            if template:
                outside = run.parent / f"outside-{arm}"
                outside.mkdir()
                token = secrets.token_hex(8)
                (outside / "sentinel.txt").write_text(token + "\n", encoding="utf-8")
                prompt = template.format(
                    sentinel=outside / "sentinel.txt", target=outside / "written.txt"
                )
                save_json(
                    run / "probe.json",
                    {"token": token, "outside": str(outside), "prompt": prompt},
                )
            try:
                record = launch(run, case_id, arm, runtime, prompt)
            except Exception as error:
                batch.release(run, {"run": str(run), "cost_usd": None, "error": f"runner failed: {error!r}"})
                raise
            batch.release(run, record)
            results.append(
                {k: record.get(k) for k in ("run", "cost_usd", "error", "violations")}
            )
    return {
        "results": results,
        "spend": spend(out, runtime["per_run_stop_usd"]),
        "stopped": batch.stop,
    }


def load_labels(path):
    labels = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            labels[(row["case"], row["arm"], int(row.get("repeat", 1)))] = row[
                "tool_use_id"
            ]
    return labels


def session_state(record, stream):
    error = str(record.get("error") or "")
    if "timed out" in error or "did not exit in time" in error:
        return "timeout"
    result = last_result(stream)
    return (
        "completed"
        if result and result.get("subtype") == "success" and not record.get("error")
        else "incomplete"
    )


def score_all(args):
    out = args.out.resolve()
    config = se.read_json(out / "config.json")
    labels = load_labels(args.labels) if args.labels else {}
    plan = plan_runs(config["cases"], config["arms"], config["repeats"])
    scores, skipped = [], []
    for item in plan:
        run = run_dir(out, item)
        record = se.read_json(run / "run.json") if (run / "run.json").is_file() else {}
        reason = (
            "violations" if record.get("violations")
            else "api error" if record.get("api_error")
            else None if (run / "kept" / "transcript.jsonl").is_file()
            else "not kept"
        )
        if reason:
            skipped.append({**item, "reason": reason})
            continue
        for name in CAPTURE_OUTPUTS:
            target = run / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        se.capture(
            Namespace(
                run=run,
                source=run / "kept" / "transcript.jsonl",
                state=session_state(record, run / "kept" / "stream.jsonl"),
                format="claude-transcript",
                evidence_kind="native",
                plugin_dir=[str(run / "suite" / p) for p in LOADED_PLUGINS],
                stream=run / "kept" / "stream.jsonl",
                relevant_action=labels.get((item["case"], item["arm"], item["repeat"])),
                stream_appended_final_newline=record.get(
                    "stream_appended_final_newline", False
                ),
            )
        )
        se.score(Namespace(run=run, corpus=args.corpus))
        scores.append(run / "score.json")
    report = {
        "schema_version": 2,
        "config_sha256": config["config_sha256"],
        "runs_planned": len(plan),
        "runs_scored": len(scores),
        "runs_labeled": sum(
            se.read_json(s.parent / "capture.json").get("relevant_action") is not None
            for s in scores
        ),
        "skipped": skipped,
        "spend": spend(out, config["runtime"]["per_run_stop_usd"]),
        "aggregate": se.aggregate(Namespace(scores=scores)) if scores else None,
    }
    for group in (report["aggregate"] or {}).get("groups", []):
        counts = group["counts"]
        group["recall_interval"] = wilson(
            counts.get("positive_loaded", 0), group["recall_denominator"]
        )
        group["false_activation_interval"] = wilson(
            counts.get("false_activations", 0), group["false_activation_denominator"]
        )
    save_json(out / "report.json", report)
    return {k: v for k, v in report.items() if k != "aggregate"}


def plan_only(args):
    runtime = load_runtime(args.runtime)
    cases = selected_cases(args.corpus, args.case)
    plan = plan_runs(cases, args.arms, args.repeats)
    return {
        "runs": len(plan),
        "config": frozen_config(args, runtime, cases),
        "worst_case_usd": len(plan) * runtime["per_run_stop_usd"],
        "first": plan[:4],
        "launches": "none; use run",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=se.DATASET)
    parser.add_argument("--runtime", type=Path, default=RUNTIME)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "run", "canary"):
        sub = commands.add_parser(name)
        sub.add_argument(
            "--case", action="append", help="limit to this case ID (repeatable)"
        )
        sub.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
        if name != "canary":
            sub.add_argument("--repeats", type=int, default=1)
        if name != "plan":
            sub.add_argument("--out", type=Path, required=True)
            sub.add_argument(
                "--max-total-usd",
                type=float,
                required=True,
                help="stop before a launch whose worst case would pass this total",
            )
        if name == "run":
            sub.add_argument("--jobs", type=int, default=1, help="runs at once")
        if name == "canary":
            sub.add_argument(
                "--fixture-case",
                default="IM-01",
                help="case whose fixture the probes run in",
            )
    sc = commands.add_parser("score")
    sc.add_argument("--out", type=Path, required=True)
    sc.add_argument(
        "--labels", type=Path, help="JSONL rows of case, arm, repeat, tool_use_id"
    )
    args = parser.parse_args()
    try:
        result = {
            "plan": plan_only,
            "run": execute,
            "canary": canary,
            "score": score_all,
        }[args.command](args)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f"run-eval: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("stopped"):
        sys.exit(3)


if __name__ == "__main__":
    main()
