#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Native runner for the skill activation evals: materialize, headless claude, capture, score, aggregate.

Dry run by default. `--canaries` and `--execute` launch a model and need an approval record in the runtime file.
`--execute` also needs a passed canary record.
The pipeline steps are `skill_eval.py` functions; this file only orders them and adds the launch.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from argparse import Namespace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import skill_eval as se

ARMS = ("hook-on", "hook-off")
PLACEHOLDER = "UNAPPROVED"
OUTPUT_ROOT = se.REPO / "artifacts" / "skill-evals"
ENV_ALLOWED = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "ANTHROPIC_API_KEY",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "NO_PROXY",
    "SSL_CERT_FILE",
    "NODE_EXTRA_CA_CERTS",
)
SHELL_TOOLS = {"Bash", "PowerShell"}
NETWORK_TOOLS = {"WebFetch", "WebSearch"}
LIMITS = ("read", "write", "network")
MAX_CONSECUTIVE_FAILURES = 3
EFFECTIVE_FIELDS = (
    "model",
    "permissionMode",
    "claude_code_version",
    "skills",
    "tools",
    "mcp_servers",
    "plugins",
)
INTERRUPTS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
READ_TOOLS = ("Read", "Glob", "Grep")
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")
CEILING_BUDGET_USD = 0.02
CEILING_TURNS = 40
# Confirmed against the live Claude CLI by the budget-ceiling canary.
BUDGET_STOP_SUBTYPE = "error_max_budget_usd"
CANARIES = (
    ("read-outside", "hook-off"),
    ("write-outside", "hook-off"),
    ("network", "hook-off"),
    ("playbook-read", "hook-off"),
    ("hook-on", "hook-on"),
    ("hook-off", "hook-off"),
    ("budget-ceiling", "hook-off"),
)
LIVE_STEPS = [
    "--canaries: every file-read tool (Read, Glob, Grep) must fail to read a sentinel outside the fixture; a Write "
    "to a new path outside the fixture must be refused; no network tool; a plugin "
    "playbook must read under --restricted; the hook-on stream must show every plugin's SessionStart hook and the "
    "hook-off stream none; each of those canaries must cost no more than the per-run budget; a run with a "
    f"${CEILING_BUDGET_USD} budget and a {CEILING_TURNS}-turn task must stop within "
    "max_concurrent_requests * max_request_usd above that budget",
    "--execute refuses until canaries.json holds a pass for every canary under the same frozen configuration",
    "first canary with an init event: freeze it as effective-session.json; every later canary and run must match it",
    "every canary and run: a Write, Edit, or NotebookEdit outside the workspace and plugin snapshot, a Read of a "
    "file there that returned, a Glob or Grep result that names a path there, or any shell or web call that was "
    "not refused writes isolation-violation.json before run.json records it, and stops the pilot",
]


class FrozenInputChanged(Exception):
    """Raised before launch when a frozen input changed after the pilot was built."""


class Interrupted(Exception):
    """`started` is true when a child existed and its process group was killed before this was raised.

    `timed_out` is true when that child had already outlived its timeout.
    """

    def __init__(self, signum, started=False, timed_out=False):
        super().__init__(signal.Signals(signum).name)
        self.signum = signum
        self.started = started
        self.timed_out = timed_out


def claude_path():
    return shutil.which("claude")


def base_tool(name):
    return name.split("(")[0]


def tool_names(runtime):
    return (
        {base_tool(t) for t in runtime["tools"]}
        if isinstance(runtime.get("tools"), list)
        else set()
    )


def launch_env(config_home):
    env = {k: os.environ[k] for k in ENV_ALLOWED if k in os.environ}
    env["CLAUDE_CONFIG_DIR"] = str(config_home)
    return env


def claude_argv(runtime, prompt, sid, plugin_dirs, mcp_config, add_dir):
    argv = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-hook-events",
        "--session-id",
        sid,
        "--model",
        runtime["model"],
        "--effort",
        runtime["effort"],
        "--setting-sources",
        runtime["setting_sources"],
        "--strict-mcp-config",
        "--mcp-config",
        str(mcp_config),
        "--tools",
        ",".join(runtime["tools"]),
        "--allowedTools",
        ",".join(runtime["allowed_tools"]),
        "--permission-mode",
        runtime["permission_mode"],
        "--permission-prompts",
        runtime["permission_prompts"],
        "--max-budget-usd",
        str(runtime["max_budget_usd_per_run"]),
    ]
    if runtime["restricted"]:
        argv += ["--restricted", "--add-dir", str(add_dir)]
    for plugin in plugin_dirs:
        argv += ["--plugin-dir", str(plugin)]
    return argv


def parse_help(text):
    """Map each flag on an option line of `claude --help` to that option's text."""
    options, current = {}, None
    for line in text.splitlines():
        match = re.match(r"^  (?:-\w, )?((?:--[\w-]+(?:, )?)+)", line)
        if match:
            current = [flag for flag in re.findall(r"--[\w-]+", match.group(1))]
            for flag in current:
                options[flag] = line
        elif current and line.startswith("   "):
            for flag in current:
                options[flag] += "\n" + line
        else:
            current = None
    return options


def help_choices(options, flag):
    text = options.get(flag, "")
    found = re.search(r"\((choices: [^)]*)\)", text) or re.search(r"\(([^)]*)\)", text)
    return (
        set(re.findall(r"[A-Za-z][\w-]*", found.group(1))) - {"choices", "default"}
        if found
        else set()
    )


WORST_REQUEST_FIELDS = (
    "context_tokens",
    "output_tokens",
    "usd_per_mtok_input_max",
    "usd_per_mtok_output",
)


def _positive_number(value):
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and value > 0
    )


def _cost_bound_ready(runtime):
    wr = runtime.get("worst_request")
    mcr = runtime.get("max_concurrent_requests")
    return (
        isinstance(wr, dict)
        and all(_positive_number(wr.get(k)) for k in WORST_REQUEST_FIELDS)
        and isinstance(mcr, int)
        and not isinstance(mcr, bool)
        and mcr >= 1
    )


def runtime_problems(runtime):
    problems = [
        f"missing {k}"
        for k in sorted(
            se.RUNTIME_FIELDS
            | {
                "allowed_tools",
                "permission_mode",
                "permission_prompts",
                "restricted",
                "setting_sources",
                "max_budget_usd_per_run",
                "worst_request",
                "max_concurrent_requests",
                "timeout_seconds",
                "confinement",
            }
        )
        if runtime.get(k) is None
    ]
    if problems:
        return problems
    if not isinstance(runtime["tools"], list) or not isinstance(
        runtime["allowed_tools"], list
    ):
        problems.append(
            "tools and allowed_tools must be explicit lists, never 'default'"
        )
    if not isinstance(runtime["restricted"], bool):
        problems.append("restricted must be a boolean")
    for key in ("max_budget_usd_per_run", "timeout_seconds"):
        if not _positive_number(runtime[key]):
            problems.append(f"{key} must be a positive number")
    wr = runtime["worst_request"]
    if not isinstance(wr, dict):
        problems.append("worst_request must be an object")
    else:
        for key in WORST_REQUEST_FIELDS:
            if not _positive_number(wr.get(key)):
                problems.append(f"worst_request.{key} must be a positive number")
    mcr = runtime["max_concurrent_requests"]
    if isinstance(mcr, bool) or not isinstance(mcr, int) or mcr < 1:
        problems.append("max_concurrent_requests must be an integer of at least 1")
    else:
        all_tools = set()
        for key in ("tools", "allowed_tools"):
            if isinstance(runtime.get(key), list):
                all_tools |= {base_tool(t) for t in runtime[key]}
        if "Agent" in all_tools and mcr == 1:
            problems.append(
                "max_concurrent_requests must be > 1 when Agent is in tools or allowed_tools"
            )
    confinement = runtime["confinement"]
    if (
        not isinstance(confinement, dict)
        or set(confinement) != set(LIMITS)
        or not set(confinement.values()) <= {"confined", "unconfined"}
    ):
        problems.append(
            "confinement must set read, write, and network to confined or unconfined"
        )
    return problems


def confinement_checks(runtime):
    tools = tool_names(runtime)
    mcp = any(t.startswith("mcp__") for t in tools)
    breakers = {
        "read": (
            "code-running tool or MCP tool"
            if (tools & SHELL_TOOLS or mcp)
            else None
            if runtime["restricted"]
            else "restricted is false"
        ),
        "write": (
            "code-running tool or MCP tool"
            if (tools & SHELL_TOOLS or mcp)
            else None
            if runtime["restricted"]
            else "restricted is false"
        ),
        "network": "code-running, network, or MCP tool"
        if (tools & (SHELL_TOOLS | NETWORK_TOOLS) or mcp)
        else None,
    }
    checks = []
    for limit in LIMITS:
        if runtime["confinement"][limit] == "unconfined":
            checks.append(
                check(
                    f"confine-{limit}",
                    "accepted_unconfined",
                    "the runtime accepts this limit as unconfined; the manifest records it",
                )
            )
        elif breakers[limit]:
            checks.append(
                check(
                    f"confine-{limit}",
                    "fail",
                    f"no claude flag confines this with {breakers[limit]} present; "
                    "remove the tool or set the limit to unconfined",
                )
            )
        else:
            checks.append(
                check(
                    f"confine-{limit}",
                    "pending_live",
                    "declared by the tool set and --restricted; the live canary proves it",
                )
            )
    return checks


def max_request_usd(runtime):
    wr = runtime["worst_request"]
    return (
        wr["context_tokens"] * wr["usd_per_mtok_input_max"]
        + wr["output_tokens"] * wr["usd_per_mtok_output"]
    ) / 1_000_000


def overshoot_bound(runtime):
    return runtime["max_concurrent_requests"] * max_request_usd(runtime)


def reservation(runtime, budget=None):
    """What one launch can cost the cap: its budget plus max_concurrent_requests in-flight requests."""
    base = runtime["max_budget_usd_per_run"] if budget is None else budget
    return base + overshoot_bound(runtime)


def check(name, status, detail):
    return {"check": name, "status": status, "detail": detail}


def cli(args, env, timeout=60):
    return subprocess.run(
        ["claude", *args],
        check=False,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def preflight(runtime, backup_dir):
    """Checks that need no model call. A `fail` blocks --execute and --canaries. Writes nothing."""
    checks = []
    problems = runtime_problems(runtime)
    checks.append(
        check(
            "runtime-complete",
            "fail" if problems else "pass",
            "; ".join(problems) or "all fields set",
        )
    )
    if problems:
        return checks
    approved = runtime.get("approval") and PLACEHOLDER not in (
        runtime["model"],
        runtime["effort"],
    )
    checks.append(
        check(
            "approval-recorded",
            "pass" if approved else "fail",
            "approval, model, and effort are set"
            if approved
            else f"the runtime has no approval record, or model or effort is {PLACEHOLDER}",
        )
    )
    if not claude_path():
        return checks + [
            check("claude-on-path", "fail", "no claude executable on PATH")
        ]
    with tempfile.TemporaryDirectory() as home:
        env = launch_env(home)
        version = cli(["--version"], env).stdout.strip()
        checks.append(
            check(
                "cli-version",
                "pass" if version == runtime["cli_version"] else "fail",
                f"installed {version!r}, frozen {runtime['cli_version']!r}",
            )
        )
        options = parse_help(cli(["--help"], env).stdout)
        sample = claude_argv(runtime, "x", "x", ["x"], "x", "x")
        absent = sorted({t for t in sample if t.startswith("--")} - options.keys())
        checks.append(
            check(
                "flags-in-help",
                "fail" if absent else "pass",
                f"claude --help does not define {absent}"
                if absent
                else "every flag the runner passes is defined",
            )
        )
        for flag, key in (
            ("--effort", "effort"),
            ("--permission-mode", "permission_mode"),
            ("--permission-prompts", "permission_prompts"),
        ):
            choices = help_choices(options, flag)
            checks.append(
                check(
                    f"{key}-allowed",
                    "pass" if runtime[key] in choices else "fail",
                    f"{runtime[key]!r} in {sorted(choices)}",
                )
            )
        listed = cli(["plugin", "list", "--json"], env)
        try:
            plugins = json.loads(listed.stdout)
        except ValueError:
            plugins = None
        checks.append(
            check(
                "config-home-isolated",
                "pass" if plugins == [] else "fail",
                "a fresh CLAUDE_CONFIG_DIR lists no installed plugin"
                if plugins == []
                else "a fresh CLAUDE_CONFIG_DIR still lists plugins or the output is not JSON",
            )
        )
        try:
            auth = json.loads(cli(["auth", "status", "--json"], env).stdout)
        except ValueError:
            auth = {}
        honored = (
            auth.get("configDirectory") == str(Path(home).resolve())
            or auth.get("configDirectory") == home
        )
        checks.append(
            check(
                "auth-in-isolated-home",
                "pass" if auth.get("loggedIn") and honored else "fail",
                f"authMethod={auth.get('authMethod')} apiKeySource={auth.get('apiKeySource')} "
                f"configDirectory honored={honored}; the isolated home needs ANTHROPIC_API_KEY",
            )
        )
    checks += confinement_checks(runtime)
    if backup_dir is not None:
        anchor = backup_dir.absolute()
        while not anchor.exists() and anchor != anchor.parent:
            anchor = anchor.parent
        try:
            writable = (
                anchor.is_dir()
                and os.access(anchor, os.W_OK)
                and not backup_dir.resolve().is_relative_to(se.REPO)
            )
        except OSError:
            writable = False
        checks.append(
            check(
                "backup-dir",
                "pass" if writable else "fail",
                "writable (or creatable) and outside the repository"
                if writable
                else "not writable or inside the repository",
            )
        )
    return checks


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


def run_id(pilot_id, case, arm, repeat):
    return "r-" + se.digest(f"{pilot_id}|{case}|{arm}|{repeat}".encode())[:10]


def plan_runs(pilot_id, cases, arms, repeats):
    """Repeat-major, then case, then arm, so any stop leaves the arms within one run of each other."""
    return [
        {
            "rid": run_id(pilot_id, case, arm, repeat),
            "case": case,
            "arm": arm,
            "repeat": repeat,
        }
        for repeat in range(1, repeats + 1)
        for case in cases
        for arm in arms
    ]


def selected_cases(corpus_path, wanted):
    cases = se.corpus(corpus_path)
    known = {c["id"] for c in cases}
    if set(wanted or ()) - known:
        raise ValueError(f"unknown case: {sorted(set(wanted) - known)}")
    usable = [c["id"] for c in cases]
    chosen = [c for c in usable if not wanted or c in wanted]
    if not chosen:
        raise ValueError("no usable case selected")
    return chosen, []


def build_pilot(args, runtime, cases):
    bound_ready = _cost_bound_ready(runtime)
    req_usd = max_request_usd(runtime) if bound_ready else None
    per_launch = (
        reservation(runtime)
        if bound_ready and _positive_number(runtime.get("max_budget_usd_per_run"))
        else None
    )
    stopping = {
        "max_cost_usd": args.max_cost_usd,
        "per_run_budget_usd": runtime.get("max_budget_usd_per_run"),
        "worst_request": runtime.get("worst_request"),
        "max_concurrent_requests": runtime.get("max_concurrent_requests"),
        "max_request_usd": req_usd,
        "per_launch_reservation_usd": per_launch,
        "budget_assumption": (
            "the CLI checks the budget before each model request, so one run overshoots "
            "by at most max_concurrent_requests in-flight requests"
        ),
        "launch_only_if": (
            "known spend, plus the reservation for each run with unknown cost, plus the next run's "
            "reservation, stays within max_cost_usd; a reservation is the per-run budget plus "
            "max_concurrent_requests * max_request_usd"
        ),
        "max_consecutive_failed_runs": MAX_CONSECUTIVE_FAILURES,
        "stop_on": [
            "cost cap",
            "consecutive failures",
            "effective session drifts from the first run's",
            "isolation violation in the init event or an arm violation in the hook events",
            "run cost exceeds its budget plus max_concurrent_requests * max_request_usd",
        ],
        "order": "repeat-major, then case, then arm",
    }
    catalog = se.inventory(se.REPO / "plugins")
    corpus_cases = {c["id"]: c for c in se.corpus(args.corpus)}
    fixtures = {
        fixture: se.inventory(se.contained(se.HERE / "fixtures", fixture))
        for fixture in sorted({corpus_cases[cid]["fixture"] for cid in cases})
    }
    pilot = {
        "schema_version": 1,
        "pilot_id": args.pilot_id,
        "cases": cases,
        "arms": list(args.arms),
        "repeats": args.repeats,
        "runtime": runtime,
        "stopping_rule": stopping,
        "claude_version": runtime.get("cli_version"),
        "source_catalog_sha256": se.digest(
            json.dumps(catalog, sort_keys=True).encode()
        ),
        "source_catalog_files": len(catalog),
        "corpus_sha256": se.digest(Path(args.corpus).read_bytes()),
        "fixture_sha256": {
            fixture: se.digest(json.dumps(files, sort_keys=True).encode())
            for fixture, files in fixtures.items()
        },
        "fixtures_sha256": se.digest(json.dumps(fixtures, sort_keys=True).encode()),
        "harness_sha256": {
            name: se.digest((HERE / name).read_bytes())
            for name in ("run_eval.py", "skill_eval.py", "facets.json")
        },
        "unlabeled": "relevant_action is not labeled; evidence stays partial and misses stay unavailable until a labeler runs",
    }
    pilot["config_sha256"] = se.digest(json.dumps(pilot, sort_keys=True).encode())
    return pilot


def spend(root, reserve, ceiling_reserve=None):
    known, unknown, unknown_usd = 0.0, 0, 0.0
    for record in [*root.glob("runs/*/run.json"), *root.glob("canaries/*/run.json")]:
        cost = (se.read_json(record).get("usage") or {}).get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            known += cost
        else:
            unknown += 1
            is_ceiling = (
                record.parent.parent.name == "canaries"
                and record.parent.name == "budget-ceiling"
            )
            unknown_usd += (
                ceiling_reserve
                if is_ceiling and ceiling_reserve is not None
                else reserve
            )
    return {
        "known_usd": known,
        "unknown_cost_runs": unknown,
        "worst_case_usd": known + unknown_usd,
    }


def run_state(run):
    if (run / "score.json").is_file():
        return "scored"
    record = run / "run.json"
    if not record.is_file():
        return "absent" if not run.exists() else "never_launched"
    data = se.read_json(record)
    if data.get("outcome") in {"unscorable", "aborted"}:
        return data["outcome"]
    return "launched_unfinished" if data.get("ended_at") else "aborted"


def last_event(stream, kind):
    found = None
    for line in stream.read_bytes().split(b"\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if isinstance(event, dict) and event.get("type") == kind:
            found = event
    return found


def init_event(stream):
    for line in stream.read_bytes().split(b"\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if (
            isinstance(event, dict)
            and event.get("type") == "system"
            and event.get("subtype") == "init"
        ):
            return event
    return None


def hook_events(stream):
    """One entry per hook id, from the hook_started and hook_response stream events.

    The events name the hook (`SessionStart:startup`) but not its plugin, so a
    hook that completed is attributed to the plugin whose frozen hook text its
    output carries.
    """
    seen = {}
    for line in stream.read_bytes().split(b"\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if (
            not isinstance(event, dict)
            or event.get("type") != "system"
            or event.get("subtype") not in {"hook_started", "hook_response"}
        ):
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
        summary.append({k: v for k, v in event.items() if k != "output"} | {"plugin": plugin})
    return summary


def arm_violations(arm, summary, plugins):
    """`plugins` names every plugin whose SessionStart hook the hook-on manifest froze."""
    if arm == "hook-off":
        return [
            f"arm violation: hook-off run, but a {h['name']} hook ran"
            for h in summary
            if h["started"] or h["completed"]
        ]
    succeeded = {
        h["plugin"]
        for h in summary
        if h["event"] == "SessionStart"
        and h["completed"]
        and h["outcome"] == "success"
    }
    missing = sorted(set(plugins) - succeeded) if plugins else ["(no plugin hook frozen)"]
    return (
        [
            f"arm violation: hook-on run, but no SessionStart hook started and succeeded for {missing}"
            f" (hook events seen: {[(h['name'], h['outcome'], h['plugin']) for h in summary]})"
        ]
        if missing
        else []
    )


def usage_of(result):
    if result is None:
        return {
            "cost_usd": None,
            "num_turns": None,
            "duration_ms": None,
            "usage": None,
            "terminal_reason": None,
        }
    cost = result.get("total_cost_usd")
    return {
        "cost_usd": cost
        if isinstance(cost, (int, float)) and not isinstance(cost, bool)
        else None,
        "num_turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
        "usage": result.get("usage"),
        "terminal_reason": result.get("terminal_reason"),
    }


def violations(init, runtime, home):
    found = []
    if init.get("mcp_servers"):
        found.append(f"mcp_servers is not empty: {init['mcp_servers']}")
    tools = {base_tool(t) for t in init.get("tools", [])}
    for limit, banned in (
        ("read", SHELL_TOOLS),
        ("write", SHELL_TOOLS),
        ("network", SHELL_TOOLS | NETWORK_TOOLS),
    ):
        if runtime["confinement"][limit] == "confined" and tools & banned:
            found.append(
                f"{limit} is confined but the session has {sorted(tools & banned)}"
            )
    if (
        any(t.startswith("mcp__") for t in tools)
        and "confined" in runtime["confinement"].values()
    ):
        found.append("the session has an MCP tool")
    memory = (init.get("memory_paths") or {}).get("auto")
    if memory is not None and not Path(memory).resolve().is_relative_to(
        Path(home).resolve()
    ):
        found.append(f"auto-memory path {memory} is outside the run's config home")
    return found


def effective(init):
    return {k: init.get(k) for k in EFFECTIVE_FIELDS} | {
        "skills": sorted(init.get("skills") or []),
        "tools": sorted(init.get("tools") or []),
        "plugins": sorted(
            (p.get("name"), p.get("version")) for p in init.get("plugins") or []
        ),
    }


def kill_group(proc):
    """Kill the child's whole process group and reap it. Interrupts stay blocked until the group is gone."""
    signal.pthread_sigmask(signal.SIG_BLOCK, INTERRUPTS)
    try:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
    finally:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, INTERRUPTS)


def launch(argv, env, cwd, timeout, stdout, stderr):
    """Run claude in its own process group. An interrupt kills the whole group, then raises Interrupted.

    Interrupts are blocked from before the fork until `Popen` has returned, so a signal cannot arrive
    while a child exists that `proc` does not name. Only the first interrupt raises; later ones are
    ignored, so a second signal cannot skip the kill. The child restores the signal mask before exec,
    because a forked child keeps the blocked mask.
    """
    fired = []

    def interrupt(signum, _frame):
        if not fired:
            fired.append(signum)
            raise Interrupted(signum)

    previous = {s: signal.signal(s, interrupt) for s in INTERRUPTS}
    proc = None
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            signal.pthread_sigmask(signal.SIG_BLOCK, INTERRUPTS)
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=cwd,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=out,
                    stderr=err,
                    start_new_session=True,
                    preexec_fn=lambda: signal.pthread_sigmask(
                        signal.SIG_UNBLOCK, INTERRUPTS
                    ),
                )
            finally:
                signal.pthread_sigmask(signal.SIG_UNBLOCK, INTERRUPTS)
            return proc.wait(timeout=timeout), False
    except (subprocess.TimeoutExpired, Interrupted) as event:
        timed_out = isinstance(event, subprocess.TimeoutExpired)
        stop = None if timed_out else event
        try:
            if proc is not None:
                kill_group(proc)
        except Interrupted as late:
            stop = late
        if stop is None:
            return None, True
        stop.started = proc is not None
        stop.timed_out = timed_out
        raise stop
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def finish_run(ctx, run, record):
    """Capture and score retained bytes. Never relaunches."""
    sid = record["launch"]["session_id"]
    stream = run / "launch" / "stream.jsonl"
    manifest = se.read_json(run / "manifest.json")
    try:
        if not (run / "capture.json").exists():
            found = list((run / "claude-home" / "projects").glob(f"*/{sid}.jsonl"))
            if len(found) != 1:
                raise ValueError(
                    f"expected one transcript for session {sid}, found {len(found)}"
                )
            result = last_event(stream, "result")
            state = (
                "timeout"
                if record["timed_out"]
                else "completed"
                if record["exit_code"] == 0
                and result
                and result.get("subtype") == "success"
                else "incomplete"
            )
            plugins = sorted({s.split(":")[0] for s in manifest["skills"]})
            se.capture(
                Namespace(
                    run=run,
                    source=found[0],
                    state=state,
                    format="claude-transcript",
                    evidence_kind="native",
                    stream=stream,
                    relevant_action=None,
                    plugin_dir=[str(run / "inputs" / "plugins" / p) for p in plugins],
                )
            )
            record["capture_state"] = state
        se.score(Namespace(run=run, corpus=ctx["corpus"]))
        record["outcome"] = "scored"
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        StopIteration,
        subprocess.CalledProcessError,
    ) as error:
        record["outcome"] = "unscorable"
        record["error"] = str(error)
    se.save_json(run / "run.json", record)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _check_frozen_inputs(ctx, run, item, manifest):
    catalog = se.digest(
        json.dumps(manifest["source_catalog_files"], sort_keys=True).encode()
    )
    mismatch = None
    if manifest["corpus_sha256"] != ctx["pilot"]["corpus_sha256"]:
        mismatch = "corpus changed since the pilot was frozen"
    else:
        fixture = next(
            c["fixture"] for c in se.corpus(ctx["corpus"]) if c["id"] == item["case"]
        )
        fixture_digest = se.digest(
            json.dumps(manifest["fixture_files"], sort_keys=True).encode()
        )
        if fixture_digest != ctx["pilot"]["fixture_sha256"][fixture]:
            mismatch = f"fixture {fixture} changed since the pilot was frozen"
        elif catalog != ctx["pilot"]["source_catalog_sha256"]:
            mismatch = "plugins/ changed since the pilot was frozen"
        else:
            for name in ("run_eval.py", "skill_eval.py", "facets.json"):
                if (
                    se.digest((HERE / name).read_bytes())
                    != ctx["pilot"]["harness_sha256"][name]
                ):
                    mismatch = f"harness file {name} changed since the pilot was frozen"
                    break
    if mismatch:
        shutil.rmtree(run)
        raise FrozenInputChanged(mismatch)


def launch_run(
    ctx,
    run,
    item,
    prompt=None,
    budget=None,
    ignore_arm_violations=False,
    secret=None,
    absent=None,
):
    """Materialize `run` and launch claude once. A failure after the launch records the run as aborted.

    `budget` replaces the runtime's per-run budget on the command line and in the bound the cost must keep.
    `secret` and `absent` are passed to `escapes`."""
    se.materialize(
        Namespace(
            case=item["case"],
            corpus=ctx["corpus"],
            runtime=ctx["runtime_path"],
            output=run,
            hook_arm=item["arm"],
            output_root=ctx["output_root"],
        )
    )
    manifest = se.read_json(run / "manifest.json")
    _check_frozen_inputs(ctx, run, item, manifest)
    record = {"schema_version": 1, **item}
    home, sid = run / "claude-home", str(uuid.uuid5(uuid.NAMESPACE_URL, item["rid"]))
    home.mkdir()
    (run / "launch").mkdir()
    plugins = [
        run / "inputs" / "plugins" / p
        for p in sorted({s.split(":")[0] for s in manifest["skills"]})
    ]
    prompt_ref = "inputs/prompt.txt"
    if prompt is None:
        prompt = (run / prompt_ref).read_text(encoding="utf-8")
    else:
        prompt_ref = "launch/prompt.txt"
        (run / prompt_ref).write_text(prompt, encoding="utf-8")
    argv = claude_argv(
        ctx["runtime"]
        | ({"max_budget_usd_per_run": budget} if budget is not None else {}),
        prompt,
        sid,
        plugins,
        ctx["mcp_config"],
        run / "inputs" / "plugins",
    )
    env = launch_env(home)
    record["launch"] = {
        "argv": argv[:2] + [f"<prompt in {prompt_ref}>"] + argv[3:],
        "env_keys": sorted(env),
        "cwd": str(run / "workspace"),
        "session_id": sid,
    }
    record["started_at"] = now()
    se.save_json(run / "run.json", record)
    began = time.monotonic()
    stream = run / "launch" / "stream.jsonl"
    try:
        code, timed_out = launch(
            argv,
            env,
            run / "workspace",
            ctx["runtime"]["timeout_seconds"],
            stream,
            run / "launch" / "stderr.txt",
        )
    except Interrupted as stop:
        record.update(
            ended_at=now(),
            exit_code=None,
            timed_out=stop.timed_out,
            duration_s=round(time.monotonic() - began, 3),
            outcome="aborted",
            error=f"interrupted by {stop}; the child's process group was killed"
            if stop.started
            else f"interrupted by {stop} before the child started",
        )
        se.save_json(run / "run.json", record)
        raise
    record.update(
        ended_at=now(),
        exit_code=code,
        timed_out=timed_out,
        duration_s=round(time.monotonic() - began, 3),
    )
    try:
        # Cost and its bound come first, so a later failure still leaves the cost in run.json.
        record["usage"] = usage_of(last_event(stream, "result"))
        cost = record["usage"]["cost_usd"]
        bound_total = reservation(ctx["runtime"], budget=budget)
        if cost is not None and round(cost, 9) > round(bound_total, 9):
            launch_budget = (
                ctx["runtime"]["max_budget_usd_per_run"] if budget is None else budget
            )
            bdetail = (
                f"run {run.name} ({run / 'run.json'}) cost {cost} exceeds budget+bound "
                f"{bound_total} (budget {launch_budget} + bound {overshoot_bound(ctx['runtime'])})"
            )
            _record_marker(
                ctx["root"], "budget-assumption-broken.json", run, bdetail
            )
        found_violations = escapes(stream, run, secret, absent)
        if found_violations:
            record["violations"] = found_violations
            record_isolation_violation(ctx["root"], run, "; ".join(found_violations))
        init = init_event(stream)
        hooks = hook_summary(
            hook_events(stream),
            manifest.get("hooks", {}) if item["arm"] == "hook-on" else {},
        )
        found_violations += (
            violations(init, ctx["runtime"], home)
            if init
            else ["no init event in the stream, so isolation was not checked"]
        ) + arm_violations(item["arm"], hooks, list(manifest.get("hooks", {})))
        record.update(
            stdout_sha256=se.digest(stream.read_bytes()),
            stderr_sha256=se.digest((run / "launch" / "stderr.txt").read_bytes()),
            effective_session=effective(init) if init else None,
            hook_events=hooks,
            violations=found_violations,
        )
        marker_violations = (
            [v for v in found_violations if not v.startswith("arm violation:")]
            if ignore_arm_violations
            else found_violations
        )
        if marker_violations:
            record_isolation_violation(ctx["root"], run, "; ".join(marker_violations))
    except (ValueError, KeyError, TypeError, OSError) as error:
        record.update(outcome="aborted", error=f"after the launch: {error}")
    se.save_json(run / "run.json", record)
    return record


def run_one(ctx, item):
    run = ctx["root"] / "runs" / item["rid"]
    if run_state(run) == "never_launched":
        shutil.rmtree(run)
    if run.exists():
        record = se.read_json(run / "run.json")
        finish_run(ctx, run, record)
        return record, False
    record = launch_run(ctx, run, item)
    if record.get("outcome") != "aborted":
        finish_run(ctx, run, record)
    return record, True


def drift(ctx, record):
    if not record.get("effective_session"):
        return None
    frozen = ctx["root"] / "effective-session.json"
    if not frozen.exists():
        se.save_json(frozen, record["effective_session"])
        return None
    expected = se.read_json(frozen)
    now = json.loads(json.dumps(record["effective_session"]))
    return (
        None
        if now == expected
        else "effective session differs from effective-session.json"
    )


def _record_marker(root, filename, run, detail):
    path = root / filename
    se.save_json(
        path,
        {
            "schema_version": 1,
            "run": str(run),
            "run_record": str(run / "run.json"),
            "detail": detail,
            "recorded_at": now(),
        },
    )
    return path


def record_isolation_violation(root, run, detail):
    return _record_marker(root, "isolation-violation.json", run, detail)


def violation_blocker(root):
    path = root / "isolation-violation.json"
    if not path.is_file():
        return None
    data = se.read_json(path)
    return (
        f"isolation violation recorded in {path} (inspect {data.get('run_record') or data.get('run')}): "
        f"{data.get('detail')}; remove {path} by hand to resume"
    )


def budget_blocker(root):
    path = root / "budget-assumption-broken.json"
    if not path.is_file():
        return None
    data = se.read_json(path)
    return (
        f"budget assumption broken recorded in {path} (inspect {data.get('run_record') or data.get('run')}): "
        f"{data.get('detail')}"
    )


def may_launch(ctx, failures, budget=None):
    blocked = violation_blocker(ctx["root"]) or budget_blocker(ctx["root"])
    if blocked:
        return blocked
    reserve = reservation(ctx["runtime"], budget=budget)
    default_reserve = reservation(ctx["runtime"])
    ceiling_reserve = reservation(ctx["runtime"], budget=CEILING_BUDGET_USD)
    spent = spend(ctx["root"], default_reserve, ceiling_reserve)
    if round(spent["worst_case_usd"] + reserve, 9) > ctx["pilot"]["stopping_rule"]["max_cost_usd"]:
        return f"cost cap: worst-case spend {spent['worst_case_usd']:.4f} plus the next run's reservation {reserve} exceeds the cap"
    if failures >= MAX_CONSECUTIVE_FAILURES:
        return f"{failures} consecutive failed runs"
    return None


def settle_aborted(run):
    """A launched run without a recorded end is final. Record that once; never launch it again."""
    record = se.read_json(run / "run.json")
    if "outcome" not in record:
        se.save_json(
            run / "run.json",
            record
            | {
                "outcome": "aborted",
                "error": "the runner stopped after the launch and recorded no end",
            },
        )


def execute(ctx):
    stop, failures, skipped, launched = None, 0, 0, 0
    for item in ctx["plan"]:
        run = ctx["root"] / "runs" / item["rid"]
        state = run_state(run)
        if state == "aborted":
            settle_aborted(run)
        if state in {"scored", "unscorable", "aborted"}:
            skipped += 1
            continue
        stop = may_launch(ctx, failures)
        if stop:
            break
        try:
            record, started = run_one(ctx, item)
        except Interrupted as interrupt:
            return f"interrupted by {interrupt}", launched + 1, skipped
        except FrozenInputChanged as err:
            stop = str(err)
            break
        launched += started
        failed = record.get("outcome") != "scored" or record.get("exit_code") != 0
        failures = failures + 1 if failed else 0
        if record.get("violations"):
            detail = "; ".join(record["violations"])
            vpath = ctx["root"] / "isolation-violation.json"
            stop = f"isolation violation: {detail} (recorded in {vpath}; inspect {run / 'run.json'})"
        else:
            stop = drift(ctx, record)
        bpath = ctx["root"] / "budget-assumption-broken.json"
        cost = (record.get("usage") or {}).get("cost_usd")
        bound_total = reservation(ctx["runtime"])
        if (
            isinstance(cost, (int, float))
            and not isinstance(cost, bool)
            and round(cost, 9) > round(bound_total, 9)
        ):
            bdetail = se.read_json(bpath).get("detail") if bpath.is_file() else None
            if not bdetail:
                bdetail = (
                    f"run {run.name} ({run / 'run.json'}) cost {cost} exceeds budget+bound "
                    f"{bound_total} (budget {ctx['runtime']['max_budget_usd_per_run']} + "
                    f"bound {overshoot_bound(ctx['runtime'])})"
                )
            budget_stop = f"budget assumption broken: {bdetail} (recorded in {bpath})"
            stop = f"{stop}; {budget_stop}" if stop else budget_stop
        if ctx["backup_dir"]:
            shutil.copytree(
                run,
                ctx["backup_dir"] / ctx["pilot"]["pilot_id"] / "runs" / run.name,
                dirs_exist_ok=True,
            )
        if stop:
            break
    return stop, launched, skipped


def stream_calls(stream):
    """(tool_use block, its tool_result block or None) for each tool call in the stream."""
    uses, results = [], {}
    for line in stream.read_bytes().split(b"\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message") if isinstance(event, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                uses.append((block.get("id"), block))
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                tid = block.get("tool_use_id")
                if isinstance(tid, str) and tid:
                    results[tid] = block
    return [(use, results.get(key) if isinstance(key, str) and key else None) for key, use in uses]


def result_text(result):
    content = (result or {}).get("content")
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return str(content or "")


def outside_run(path, run):
    """Does `path` resolve outside the run's workspace and plugin snapshot? A relative path is under the workspace."""
    try:
        p = Path(os.path.expanduser(path))
        resolved = (p if p.is_absolute() else run / "workspace" / p).resolve()
        allowed = ((run / "workspace").resolve(), (run / "inputs" / "plugins").resolve())
    except (ValueError, OSError, RuntimeError):
        return True
    return not any(resolved.is_relative_to(base) for base in allowed)


def escapes(stream, run, secret=None, absent=None):
    """Proof in the stream that a launch reached outside its run, whatever the prompt asked. One line per escape.

    A call counts unless its tool_result is an error. A call that changes something (a write, a shell or
    web call) counts with no tool_result too, since nothing shows it was refused. `secret` must not appear
    in the stream, and the file `absent` must not exist after the run.
    """
    found = []
    for use, result in stream_calls(stream):
        if result is not None and result.get("is_error"):
            continue
        tool = base_tool(str(use.get("name", "")))
        inp = use.get("input") if isinstance(use.get("input"), dict) else {}
        path = inp.get("file_path") or inp.get("notebook_path")
        if tool in SHELL_TOOLS | NETWORK_TOOLS:
            found.append(f"escape: a {tool} call was not refused")
        elif tool in WRITE_TOOLS and isinstance(path, str) and path and outside_run(path, run):
            found.append(f"escape: a {tool} of {path} outside the run was not refused")
        elif tool == "Read" and result is not None and isinstance(path, str) and path and outside_run(path, run):
            found.append(f"escape: a Read of {path} outside the run returned")
        elif tool in ("Glob", "Grep") and result is not None:
            named = [
                line.strip().split(":")[0]
                for line in result_text(result).splitlines()
                if line.strip().startswith("/")
            ]
            outside = [p for p in named if outside_run(p, run)]
            if outside:
                found.append(f"escape: a {tool} result names {outside[:3]} outside the run")
    if secret and secret.encode() in stream.read_bytes():
        found.append("escape: the sentinel text appears in the stream")
    if absent is not None and absent.exists():
        found.append(f"escape: {absent} exists after the run")
    return found


def canary_setup(name, ctx, run):
    """The canary's prompt and the file it targets (None when it targets none)."""
    outside = ctx["root"] / "canaries" / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    playbook = run / "inputs" / "plugins" / "swe" / "skills" / "swe-mode" / "playbooks" / "fix-bug.md"
    if name == "read-outside":
        target = outside / f"sentinel-{uuid.uuid4().hex[:8]}.txt"
        target.write_text(f"CANARY-{uuid.uuid4().hex}\n")
        asks = {
            "Read": f"Use the Read tool on PATH={target}.",
            "Glob": f"Use the Glob tool with pattern {outside}/sentinel-*.txt.",
            "Grep": f"Use the Grep tool with pattern CANARY- and path {outside}.",
        }
        probes = " ".join(asks[t] for t in READ_TOOLS if t in tool_names(ctx["runtime"]))
        return f"CANARY read-outside: {probes} Make one call per tool and report what each returned. Use no other tool.", target
    if name == "write-outside":
        target = outside / "write-target.txt"
        target.unlink(missing_ok=True)
        return (
            f"CANARY write-outside: Use the Write tool to create PATH={target} with the content canary. "
            "Use no other tool.",
            target,
        )
    if name == "network":
        return "CANARY network: Fetch https://example.com with a web tool and report its title. If you have no web tool, say so.", None
    if name == "playbook-read":
        return f"CANARY playbook-read: Use the Read tool on PATH={playbook} and report its first heading. Use no other tool.", playbook
    if name == "budget-ceiling":
        return (
            f"CANARY budget-ceiling: Use the Read tool on PATH={playbook}. Make one Read call per turn, never two "
            f"in one turn, and make {CEILING_TURNS} such calls in a row. Then reply done.",
            playbook,
        )
    return "CANARY hook: reply with the word ok.", None


def glob_regex(pattern):
    """A glob as a regex that keeps to folders, as Glob does.

    `*`, `?`, and `[...]` never match `/`; a whole `**` segment matches zero or more folders."""
    parts = pattern.split("/")
    out = []
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        if part == "**":
            out.append(".*" if last else "(?:[^/]*/)*")
            continue
        i = 0
        while i < len(part):
            c = part[i]
            close = -1
            if c == "[":
                j = i + 1 + (part[i + 1 : i + 2] in ("!", "^"))
                close = part.find("]", j + (part[j : j + 1] == "]"))
            if c == "*":
                out.append("[^/]*")
            elif c == "?":
                out.append("[^/]")
            elif close > 0:
                body = part[i + 1 : close]
                negate = body[:1] in ("!", "^")
                body = "".join(
                    "\\" + ch if ch in "\\[]^&~|" else ch for ch in body[negate:]
                )
                out.append(f"[^/{body}]" if negate else f"(?!/)[{body}]")
                i = close
            else:
                out.append(re.escape(c))
            i += 1
        if not last:
            out.append("/")
    return re.compile("".join(out))


def matches_canary_target(use, target):
    if target is None:
        return False
    tool = base_tool(use.get("name", ""))
    inp = use.get("input")
    if not isinstance(inp, dict):
        return False
    target_norm = os.path.normpath(str(target))
    if tool in ("Read", "Write"):
        fp = inp.get("file_path")
        return isinstance(fp, str) and os.path.normpath(fp) == target_norm
    if tool == "Glob":
        pattern = inp.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return False
        if not os.path.isabs(pattern):
            base = inp.get("path")
            if not isinstance(base, str) or not base:
                return False
            pattern = os.path.join(base, pattern)
        return glob_regex(os.path.normpath(pattern)).fullmatch(target_norm) is not None
    if tool == "Grep":
        gpath = inp.get("path")
        return isinstance(gpath, str) and os.path.normpath(gpath) in {
            target_norm,
            os.path.normpath(str(target.parent)),
        }
    return False


def canary_verdict(name, stream, record, target):
    """Judge a canary from its stream. Returns (passed, detail). `escapes` in launch_run owns escape detection."""
    calls = stream_calls(stream)
    tools = {base_tool(t) for t in record["effective_session"]["tools"]}
    touching = [
        (use, result)
        for use, result in calls
        if matches_canary_target(use, target)
    ]
    refused = lambda pairs: all(r and r.get("is_error") for _, r in pairs)
    if name == "read-outside":
        secret = target.read_text().strip()
        leaked = secret.encode() in stream.read_bytes()
        probes = sorted(tools & set(READ_TOOLS))

        def got(result):
            text = result_text(result)
            return not result.get("is_error") and (
                target.name in text or secret in text
            )

        by_tool = {
            tool: [r for u, r in touching if base_tool(u.get("name", "")) == tool]
            for tool in probes
        }
        silent = sorted(t for t, results in by_tool.items() if not results)
        missing = sorted(
            t for t, results in by_tool.items() if any(r is None for r in results)
        )
        read = sorted(
            t
            for t, results in by_tool.items()
            if any(r is not None and got(r) for r in results)
        )
        return (
            bool(probes) and not silent and not missing and not read and not leaked,
            f"file-read tools in the session={probes}, never tried against the sentinel outside the fixture={silent}, "
            f"missing tool_result={missing}, returned its file name or content={read}, sentinel text in the stream={leaked}",
        )
    if name == "write-outside":
        attempts = [
            (u, r)
            for u, r in touching
            if base_tool(u.get("name", "")) == "Write"
        ]
        return (
            bool(attempts) and refused(attempts) and not target.exists(),
            f"{len(attempts)} Write call(s) to a new path outside the fixture, "
            f"all refused={refused(attempts)}, new file absent={not target.exists()}",
        )
    if name == "network":
        banned = sorted(tools & (SHELL_TOOLS | NETWORK_TOOLS))
        used = [
            u.get("name")
            for u, r in calls
            if base_tool(u.get("name", "")) in SHELL_TOOLS | NETWORK_TOOLS
            and not (r and r.get("is_error"))
        ]
        return (
            not banned and not used,
            f"shell or network tools in the session={banned}, such calls that succeeded={used}",
        )
    if name == "playbook-read":
        reads = [
            (u, r)
            for u, r in touching
            if base_tool(u.get("name", "")) == "Read"
            and r
            and not r.get("is_error")
            and result_text(r).strip()
        ]
        return (
            bool(reads),
            f"{len(reads)} successful Read call(s) on the plugin playbook under --restricted",
        )
    return True, "no arm violation in the hook events"


def ceiling_verdict(stream, record, target, runtime):
    """Did a run with a tiny budget and a long task stop, and how far past the budget did its cost go?"""
    reads = [
        u
        for u, _ in stream_calls(stream)
        if base_tool(u.get("name", "")) == "Read" and matches_canary_target(u, target)
    ]
    subtype = (last_event(stream, "result") or {}).get("subtype")
    cost = (record.get("usage") or {}).get("cost_usd")
    overshoot = None if cost is None else round(cost - CEILING_BUDGET_USD, 6)
    bound = overshoot_bound(runtime)
    stopped = (
        len(reads) < CEILING_TURNS
        and subtype == BUDGET_STOP_SUBTYPE
        and overshoot is not None
        and overshoot >= 0
    )
    within = stopped and round(overshoot, 9) <= round(bound, 9)
    return within, {
        "stopped": stopped,
        "tool_calls": len(reads),
        "tool_calls_asked": CEILING_TURNS,
        "stop_subtype": subtype,
        "overshoot_usd": overshoot,
        "overshoot_bound_usd": bound,
        "within_bound": within,
    }, (
        f"budget {CEILING_BUDGET_USD}: {len(reads)} of {CEILING_TURNS} Read calls, result subtype {subtype!r}, "
        f"cost {cost}, overshoot {overshoot}, bound {bound}; "
        f"stopped by the budget={stopped}"
    )


def run_canary(ctx, name, arm):
    run = ctx["root"] / "canaries" / name
    done = run / "canary.json"
    if done.is_file():
        return se.read_json(done)
    result = {"canary": name, "arm": arm}
    if (run / "run.json").is_file():
        result |= {
            "passed": False,
            "detail": "launched earlier and never judged; a launched run is never launched again",
        }
    else:
        if run.exists():
            shutil.rmtree(run)
        prompt, target = canary_setup(name, ctx, run)
        ceiling = name == "budget-ceiling"
        item = {"rid": f"canary-{name}", "case": ctx["plan"][0]["case"], "arm": arm}
        record = launch_run(
            ctx,
            run,
            item,
            prompt,
            budget=CEILING_BUDGET_USD if ceiling else None,
            ignore_arm_violations=True,
            secret=target.read_text().strip() if name == "read-outside" else None,
            absent=target if name == "write-outside" else None,
        )
        budget = CEILING_BUDGET_USD if ceiling else ctx["runtime"]["max_budget_usd_per_run"]
        cost = (record.get("usage") or {}).get("cost_usd")
        within = False if ceiling else cost is not None and cost <= budget
        problems, detail, extra = [], "", {}
        iso = [
            v
            for v in record.get("violations") or []
            if not v.startswith("arm violation:")
        ]
        if iso:
            extra["isolation_violation"] = "; ".join(iso)
            extra["isolation_violation_record"] = str(
                ctx["root"] / "isolation-violation.json"
            )
        if record.get("outcome") == "aborted":
            problems.append(f"run aborted: {record['error']}")
        elif not record.get("effective_session"):
            problems.append(
                "; ".join(record.get("violations") or ["no init event in the stream"])
            )
        else:
            problems += record["violations"] + [
                d for d in [drift(ctx, record)] if d
            ]
            if ceiling:
                passed, ceiling_extra, detail = ceiling_verdict(
                    run / "launch" / "stream.jsonl", record, target, ctx["runtime"]
                )
                extra |= ceiling_extra
                within = passed
            else:
                passed, detail = canary_verdict(
                    name, run / "launch" / "stream.jsonl", record, target
                )
            if not passed:
                problems.append(detail)
        if not ceiling and not within:
            problems.append(
                f"cost {cost} is not known and within the per-run budget {budget}"
            )
        result |= extra | {
            "passed": not problems,
            "detail": "; ".join(problems) or detail,
            "cost_usd": cost,
            "budget_usd": budget,
            "within_budget": within,
            "target": str(target) if target else None,
            "exit_code": record.get("exit_code"),
        }
    se.save_json(done, result)
    return result


def run_canaries(ctx):
    results, stop = {}, None
    for name, arm in CANARIES:
        run = ctx["root"] / "canaries" / name
        done = run / "canary.json"
        if not done.is_file() and not (run / "run.json").is_file():
            budget = CEILING_BUDGET_USD if name == "budget-ceiling" else None
            stop = may_launch(ctx, 0, budget=budget)
            if stop:
                break
        try:
            result = run_canary(ctx, name, arm)
        except FrozenInputChanged as err:
            stop = str(err)
            break
        results[name] = result
        if result.get("isolation_violation"):
            vpath = result.get("isolation_violation_record") or str(
                ctx["root"] / "isolation-violation.json"
            )
            stop = (
                f"isolation violation in canary {name}: {result['isolation_violation']} "
                f"(recorded in {vpath}; inspect {run / 'run.json'})"
            )
            break
    summary = {
        "schema_version": 1,
        "config_sha256": ctx["pilot"]["config_sha256"],
        "recorded_at": now(),
        "stopped": stop,
        "canaries": results,
    }
    se.save_json(ctx["root"] / "canaries.json", summary)
    return summary


def canary_blockers(root, pilot):
    path = root / "canaries.json"
    if not path.is_file():
        return ["canaries: no canary record; run --canaries first"]
    record = se.read_json(path)
    if record.get("config_sha256") != pilot["config_sha256"]:
        return ["canaries: the record belongs to a different frozen configuration"]
    failed = [
        name
        for name, _ in CANARIES
        if not (record.get("canaries", {}).get(name) or {}).get("passed")
    ]
    return [f"canaries: not passed or not run: {failed}"] if failed else []


def report(ctx, stop):
    root, plan = ctx["root"], ctx["plan"]
    scores = sorted(root.glob("runs/*/score.json"))
    states = {}
    for item in plan:
        states.setdefault(run_state(root / "runs" / item["rid"]), []).append(
            item["rid"]
        )
    result = {
        "schema_version": 1,
        "pilot_id": ctx["pilot"]["pilot_id"],
        "stopped": stop,
        "runs_planned": len(plan),
        "run_states": {k: len(v) for k, v in sorted(states.items())},
        "cost": spend(
            root,
            reservation(ctx["runtime"]),
            reservation(ctx["runtime"], budget=CEILING_BUDGET_USD),
        ),
        "aggregate": se.aggregate(Namespace(scores=scores)) if scores else None,
    }
    for group in (result["aggregate"] or {}).get("groups", []):
        counts = group["counts"]
        group["recall_interval"] = wilson(
            counts.get("positive_loaded", 0), group["recall_denominator"]
        )
        group["false_activation_interval"] = wilson(
            counts.get("false_activations", 0), group["false_activation_denominator"]
        )
    se.save_json(root / "report.json", result)
    return result


def dry_plan(args, runtime, cases, excluded, pilot, checks, plan):
    blockers = [c["check"] for c in checks if c["status"] == "fail"]
    if args.max_cost_usd is None:
        blockers.append("max-cost-usd-not-set")
    if not args.pilot_id_given:
        blockers.append("pilot-id-not-set")
    root = args.output_root / args.pilot_id
    if args.pilot_id_given and canary_blockers(root, pilot):
        blockers.append("canaries-not-passed")
    if args.pilot_id_given and violation_blocker(root):
        blockers.append("isolation-violation")
    if args.pilot_id_given and budget_blocker(root):
        blockers.append("budget-assumption-broken")
    states = [run_state(root / "runs" / r["rid"]) for r in plan]
    budget = (
        reservation(runtime)
        if _cost_bound_ready(runtime) and _positive_number(runtime.get("max_budget_usd_per_run"))
        else 0
    )
    todo = sum(s not in {"scored", "unscorable", "aborted"} for s in states)
    shown = plan if args.list_runs else plan[:6]
    sample = (
        claude_argv(
            runtime,
            "<prompt>",
            "<session-id>",
            ["<run>/inputs/plugins/<plugin>"],
            "<mcp-empty.json>",
            "<run>/inputs/plugins",
        )
        if not runtime_problems(runtime)
        else None
    )
    return {
        "mode": "dry-run: no model is launched",
        "pilot": pilot,
        "excluded_cases": excluded,
        "runs": {
            "planned": len(plan),
            "to_launch": todo,
            "already_finished": len(plan) - todo,
            "worst_case_cost_usd": todo * budget,
            "shown": shown,
        },
        "argv_template": sample,
        "env_keys_passed": list(ENV_ALLOWED) + ["CLAUDE_CONFIG_DIR"],
        "preflight": checks,
        "ready_to_execute": not blockers,
        "blockers": blockers,
        "live_steps_pending_approval": LIVE_STEPS,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=HERE / "runtime.native.json")
    parser.add_argument("--corpus", type=Path, default=se.HERE / "cases.json")
    parser.add_argument(
        "--case",
        action="append",
        help="case id; repeat for more; default is every usable case",
    )
    parser.add_argument("--arms", nargs="+", choices=ARMS, default=list(ARMS))
    parser.add_argument("--repeats", type=int, default=10, help="runs per case and arm")
    parser.add_argument(
        "--pilot-id",
        help="output folder name under --output-root; needed to execute or run canaries",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=OUTPUT_ROOT,
        help="folder that holds the pilot folders; default artifacts/skill-evals",
    )
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        help="hard cap on worst-case spend; needed to execute",
    )
    parser.add_argument(
        "--backup-dir", type=Path, help="copy each finished run and the report here"
    )
    parser.add_argument(
        "--list-runs", action="store_true", help="dry run: print every planned run"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--canaries",
        action="store_true",
        help="launch the model for the live canaries only, and record the result in the pilot folder",
    )
    mode.add_argument(
        "--execute",
        action="store_true",
        help="launch the model for the pilot; needs a passed canary record. Default is a dry run",
    )
    args = parser.parse_args()
    args.output_root = args.output_root.resolve()
    args.pilot_id_given = args.pilot_id is not None
    args.pilot_id = args.pilot_id or "dry-run"
    try:
        if args.repeats < 1 or (
            args.max_cost_usd is not None and args.max_cost_usd <= 0
        ):
            raise ValueError("--repeats and --max-cost-usd must be positive")
        pilot_root = (args.output_root / args.pilot_id).resolve()
        if (
            args.pilot_id in {".", ".."}
            or not re.fullmatch(r"[A-Za-z0-9._-]+", args.pilot_id)
            or pilot_root == args.output_root
            or not pilot_root.is_relative_to(args.output_root)
        ):
            raise ValueError(
                "--pilot-id must be a plain folder name that stays inside --output-root"
            )
        runtime = se.read_json(args.runtime)
        cases, excluded = selected_cases(args.corpus, args.case)
        pilot = build_pilot(args, runtime, cases)
        plan = plan_runs(args.pilot_id, cases, args.arms, args.repeats)
        checks = preflight(runtime, args.backup_dir)
        if not (args.execute or args.canaries):
            print(
                json.dumps(
                    dry_plan(args, runtime, cases, excluded, pilot, checks, plan),
                    indent=2,
                )
            )
            return
        blockers = [
            c["check"] + ": " + c["detail"] for c in checks if c["status"] == "fail"
        ]
        root = args.output_root / args.pilot_id
        if not args.pilot_id_given or args.max_cost_usd is None:
            blockers.append(
                "--pilot-id and --max-cost-usd are required with --execute or --canaries"
            )
        elif not runtime_problems(runtime) and args.max_cost_usd < reservation(runtime):
            blockers.append("--max-cost-usd is below one run's reservation")
        if args.execute:
            blockers += canary_blockers(root, pilot)
        if blockers:
            raise ValueError("refusing to launch: " + " | ".join(blockers))
        root.mkdir(parents=True, exist_ok=True)
        if (root / "pilot.json").exists():
            if (
                se.read_json(root / "pilot.json")["config_sha256"]
                != pilot["config_sha256"]
            ):
                raise ValueError(
                    "pilot.json exists with a different frozen configuration; use a new --pilot-id"
                )
        else:
            se.save_json(
                root / "pilot.json",
                pilot
                | {
                    "preflight": checks,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
        se.save_json(root / "runtime.json", runtime)
        se.save_json(root / "mcp-empty.json", {"mcpServers": {}})
        ctx = {
            "root": root,
            "pilot": pilot,
            "plan": plan,
            "runtime": runtime,
            "corpus": args.corpus,
            "output_root": args.output_root,
            "runtime_path": root / "runtime.json",
            "mcp_config": root / "mcp-empty.json",
            "backup_dir": args.backup_dir,
        }
        if args.canaries:
            summary = run_canaries(ctx)
            print(json.dumps(summary, indent=2, sort_keys=True))
            sys.exit(
                0
                if len(summary["canaries"]) == len(CANARIES)
                and all(c["passed"] for c in summary["canaries"].values())
                else 3
            )
        stop, launched, skipped = execute(ctx)
        summary = report(ctx, stop) | {
            "launched_now": launched,
            "skipped_finished": skipped,
        }
        if args.backup_dir:
            target = args.backup_dir / args.pilot_id
            target.mkdir(parents=True, exist_ok=True)
            for name in (
                "pilot.json",
                "report.json",
                "effective-session.json",
                "runtime.json",
            ):
                if (root / name).exists():
                    shutil.copy2(root / name, target / name)
        print(json.dumps(summary, indent=2, sort_keys=True))
        sys.exit(3 if stop else 0)
    except Interrupted as stop:
        parser.exit(3, f"run-eval: interrupted by {stop}; the child was killed and the run recorded as aborted\n")
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        subprocess.SubprocessError,
    ) as error:
        parser.exit(2, f"run-eval: {error}\n")


if __name__ == "__main__":
    main()
