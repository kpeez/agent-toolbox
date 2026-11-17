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
CANARIES = (
    ("read-outside", "hook-off"),
    ("write-outside", "hook-off"),
    ("network", "hook-off"),
    ("playbook-read", "hook-off"),
    ("hook-on", "hook-on"),
    ("hook-off", "hook-off"),
)
LIVE_STEPS = [
    "--canaries: a read and a write outside the fixture must be refused; no network tool; a plugin playbook must "
    "read under --restricted; the hook-on stream must show every plugin's SessionStart hook and the hook-off "
    "stream none; each canary's cost must stay within the per-run budget",
    "--execute refuses until canaries.json holds a pass for every canary under the same frozen configuration",
    "first pilot run: read the init event of the stream and freeze it as effective-session.json",
]


class Interrupted(Exception):
    def __init__(self, signum):
        super().__init__(signal.Signals(signum).name)
        self.signum = signum


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
        if (
            isinstance(runtime[key], bool)
            or not isinstance(runtime[key], (int, float))
            or runtime[key] <= 0
        ):
            problems.append(f"{key} must be a positive number")
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
    """Checks that need no model call. A `fail` blocks --execute and --canaries."""
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
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            writable = os.access(
                backup_dir, os.W_OK
            ) and not backup_dir.resolve().is_relative_to(se.REPO)
        except OSError:
            writable = False
        checks.append(
            check(
                "backup-dir",
                "pass" if writable else "fail",
                "writable and outside the repository"
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
    cases, skills = se.corpus(corpus_path), se.catalog_skills()
    resolve = se.resolver(skills)
    known = {c["id"] for c in cases}
    if set(wanted or ()) - known:
        raise ValueError(f"unknown case: {sorted(set(wanted) - known)}")
    usable = [c["id"] for c in cases if not se.excluded(c, resolve, skills)]
    chosen = [c for c in usable if not wanted or c in wanted]
    if not chosen:
        raise ValueError("no usable case selected")
    return chosen, sorted(known - set(usable))


def build_pilot(args, runtime, cases):
    stopping = {
        "max_cost_usd": args.max_cost_usd,
        "per_run_budget_usd": runtime.get("max_budget_usd_per_run"),
        "launch_only_if": "known spend, plus the per-run budget for each run with unknown cost, plus the next run's "
        "per-run budget, stays within max_cost_usd",
        "max_consecutive_failed_runs": MAX_CONSECUTIVE_FAILURES,
        "stop_on": [
            "cost cap",
            "consecutive failures",
            "effective session drifts from the first run's",
            "isolation violation in the init event or an arm violation in the hook events",
        ],
        "order": "repeat-major, then case, then arm",
    }
    catalog = se.inventory(se.REPO / "plugins")
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
        "harness_sha256": {
            name: se.digest((HERE / name).read_bytes())
            for name in ("run_eval.py", "skill_eval.py", "cases.json", "facets.json")
        },
        "unlabeled": "relevant_action is not labeled; evidence stays partial and misses stay unavailable until a labeler runs",
    }
    pilot["config_sha256"] = se.digest(json.dumps(pilot, sort_keys=True).encode())
    return pilot


def spend(root, per_run_budget):
    known, unknown = 0.0, 0
    for record in [*root.glob("runs/*/run.json"), *root.glob("canaries/*/run.json")]:
        cost = (se.read_json(record).get("usage") or {}).get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool):
            known += cost
        else:
            unknown += 1
    return {
        "known_usd": known,
        "unknown_cost_runs": unknown,
        "worst_case_usd": known + unknown * per_run_budget,
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


def launch(argv, env, cwd, timeout, stdout, stderr):
    """Run claude in its own process group. An interrupt kills the whole group, then raises Interrupted."""

    def interrupt(signum, _frame):
        raise Interrupted(signum)

    previous = {s: signal.signal(s, interrupt) for s in INTERRUPTS}
    proc = None
    try:
        with stdout.open("wb") as out, stderr.open("wb") as err:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                start_new_session=True,
            )
            return proc.wait(timeout=timeout), False
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
        return None, True
    except Interrupted:
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
        raise
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


def launch_run(ctx, run, item, prompt=None):
    """Materialize `run` and launch claude once. A failure after the launch records the run as aborted."""
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
    catalog = se.digest(
        json.dumps(manifest["source_catalog_files"], sort_keys=True).encode()
    )
    record = {"schema_version": 1, **item}
    if catalog != ctx["pilot"]["source_catalog_sha256"]:
        shutil.rmtree(run)
        raise ValueError("plugins/ changed since the pilot was frozen")
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
        ctx["runtime"],
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
            timed_out=False,
            duration_s=round(time.monotonic() - began, 3),
            outcome="aborted",
            error=f"interrupted by {stop}; the child's process group was killed",
        )
        se.save_json(run / "run.json", record)
        raise
    ended = {
        "ended_at": now(),
        "exit_code": code,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - began, 3),
    }
    try:
        init = init_event(stream)
        hooks = hook_summary(
            hook_events(stream),
            manifest.get("hooks", {}) if item["arm"] == "hook-on" else {},
        )
        record.update(
            ended,
            usage=usage_of(last_event(stream, "result")),
            stdout_sha256=se.digest(stream.read_bytes()),
            stderr_sha256=se.digest((run / "launch" / "stderr.txt").read_bytes()),
            effective_session=effective(init) if init else None,
            hook_events=hooks,
            violations=(
                violations(init, ctx["runtime"], home)
                + arm_violations(item["arm"], hooks, list(manifest.get("hooks", {})))
                if init
                else []
            ),
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        record.update(
            ended, outcome="aborted", error=f"after the launch: {error}"
        )
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


def may_launch(ctx, failures):
    budget = ctx["runtime"]["max_budget_usd_per_run"]
    spent = spend(ctx["root"], budget)
    if spent["worst_case_usd"] + budget > ctx["pilot"]["stopping_rule"]["max_cost_usd"]:
        return f"cost cap: worst-case spend {spent['worst_case_usd']:.4f} plus the next run's {budget} exceeds the cap"
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
        launched += started
        failed = record.get("outcome") != "scored" or record.get("exit_code") != 0
        failures = failures + 1 if failed else 0
        stop = (
            "isolation violation: " + "; ".join(record["violations"])
            if record.get("violations")
            else drift(ctx, record)
        )
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
    uses, results = {}, {}
    for line in stream.read_bytes().split(b"\n"):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        content = (event.get("message") or {}).get("content") if isinstance(event, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if event.get("type") == "assistant" and block.get("type") == "tool_use":
                uses[block.get("id")] = block
            elif event.get("type") == "user" and block.get("type") == "tool_result":
                results[block.get("tool_use_id")] = block
    return [(use, results.get(key)) for key, use in uses.items()]


def result_text(result):
    content = (result or {}).get("content")
    if isinstance(content, list):
        return " ".join(str(b.get("text", "")) for b in content if isinstance(b, dict))
    return str(content or "")


def canary_setup(name, ctx, run):
    """The canary's prompt and the file it targets (None when it targets none)."""
    outside = ctx["root"] / "canaries" / "outside"
    outside.mkdir(parents=True, exist_ok=True)
    if name == "read-outside":
        target = outside / f"sentinel-{uuid.uuid4().hex[:8]}.txt"
        target.write_text(f"CANARY-{uuid.uuid4().hex}\n")
        return f"CANARY read-outside: Use the Read tool on PATH={target} and report its first line. Use no other tool.", target
    if name == "write-outside":
        target = outside / "write-target.txt"
        target.unlink(missing_ok=True)
        return f"CANARY write-outside: Use the Write tool to create PATH={target} with the content canary. Use no other tool.", target
    if name == "network":
        return "CANARY network: Fetch https://example.com with a web tool and report its title. If you have no web tool, say so.", None
    if name == "playbook-read":
        target = run / "inputs" / "plugins" / "swe" / "skills" / "swe-mode" / "playbooks" / "fix-bug.md"
        return f"CANARY playbook-read: Use the Read tool on PATH={target} and report its first heading. Use no other tool.", target
    return "CANARY hook: reply with the word ok.", None


def canary_verdict(name, stream, record, target):
    """Judge a canary from its stream. Returns (passed, detail)."""
    calls = stream_calls(stream)
    tools = {base_tool(t) for t in record["effective_session"]["tools"]}
    touching = [
        (use, result)
        for use, result in calls
        if target is not None and target.name in json.dumps(use.get("input"))
    ]
    refused = lambda pairs: all(r and r.get("is_error") for _, r in pairs)
    if name == "read-outside":
        reads = [(u, r) for u, r in touching if u.get("name") == "Read"]
        leaked = target.read_text().strip().encode() in stream.read_bytes()
        return (
            bool(reads) and refused(reads) and not leaked,
            f"{len(reads)} Read call(s) on the sentinel outside the fixture, all refused={refused(reads)}, "
            f"sentinel text in the stream={leaked}",
        )
    if name == "write-outside":
        writes = [(u, r) for u, r in touching if u.get("name") in {"Write", "Edit"}]
        return (
            bool(writes) and refused(writes) and not target.exists(),
            f"{len(writes)} write call(s) outside the fixture, all refused={refused(writes)}, "
            f"file created={target.exists()}",
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
            if u.get("name") == "Read"
            and r
            and not r.get("is_error")
            and result_text(r).strip()
        ]
        return bool(reads), f"{len(reads)} successful Read call(s) on the plugin playbook under --restricted"
    return True, "no arm violation in the hook events"


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
        item = {"rid": f"canary-{name}", "case": ctx["plan"][0]["case"], "arm": arm}
        record = launch_run(ctx, run, item, prompt)
        budget = ctx["runtime"]["max_budget_usd_per_run"]
        cost = (record.get("usage") or {}).get("cost_usd")
        within = cost is not None and cost <= budget
        problems = []
        if record.get("outcome") == "aborted":
            problems.append(f"run aborted: {record['error']}")
        elif not record.get("effective_session"):
            problems.append("no init event in the stream")
        else:
            problems += record["violations"] + [
                d for d in [drift(ctx, record)] if d
            ]
            passed, detail = canary_verdict(
                name, run / "launch" / "stream.jsonl", record, target
            )
            if not passed:
                problems.append(detail)
        if not within:
            problems.append(
                f"cost {cost} is not known and within the per-run budget {budget}; "
                "the cost cap assumes --max-budget-usd is a hard ceiling"
            )
        result |= {
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
        done = ctx["root"] / "canaries" / name / "canary.json"
        if not done.is_file():
            stop = may_launch(ctx, 0)
            if stop:
                break
        results[name] = run_canary(ctx, name, arm)
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
        "cost": spend(root, ctx["runtime"]["max_budget_usd_per_run"]),
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
    states = [run_state(root / "runs" / r["rid"]) for r in plan]
    budget = runtime.get("max_budget_usd_per_run") or 0
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
    args.pilot_id_given = args.pilot_id is not None
    args.pilot_id = args.pilot_id or "dry-run"
    try:
        if args.repeats < 1 or (
            args.max_cost_usd is not None and args.max_cost_usd <= 0
        ):
            raise ValueError("--repeats and --max-cost-usd must be positive")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", args.pilot_id):
            raise ValueError("--pilot-id must be a plain folder name")
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
        elif args.max_cost_usd < runtime["max_budget_usd_per_run"]:
            blockers.append("--max-cost-usd is below one run's budget")
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
