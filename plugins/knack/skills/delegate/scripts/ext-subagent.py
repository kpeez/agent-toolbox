#!/usr/bin/env python3
"""External subagent — dispatch one coding task to an agentic CLI, return only its answer.

Centralizes each provider's auto-approve/sandbox flags and normalizes output to just
the agent's final message, so the orchestrator calls one stable interface, spends no
tokens reconstructing per-provider flags, and never has the task's file I/O hit its
own context. stdout is the answer; diagnostics and the metadata line go to stderr.

Provider → engine: codex → GPT-5.x, antigravity → Gemini, copilot → Sonnet.
--role explorer|doer|planner expands to a model + reasoning effort per /delegate's
tiers (codex only). --model selects the model for codex/copilot. antigravity has no
per-call model flag; set it in ~/.gemini/antigravity-cli/settings.json or via
`agy /model`. --timeout kills the worker's whole process tree after N seconds
(0 disables — raise or disable it for tasks expected to run long). An exit-0 run
that returns an empty answer is reported as a failure, not silent success.

Prompt input (exactly one): a positional argument, --prompt-file PATH, or stdin
(omit the argument, or pass '-'). Prefer --prompt-file/stdin for long or code-heavy
prompts so the caller never has to shell-escape them.

    ext-subagent codex --role doer "Implement X following existing patterns. Run the tests."
    ext-subagent copilot --prompt-file task.md --model claude-sonnet-4.6
    cat task.md | ext-subagent codex - --retries 2 --max-output-chars 8000

All run in the current directory so the workspace context auto-loads. Each is
write-capable (codex is sandboxed to the workspace); the permission-bypass flags are
centralized here, on purpose.
"""

import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

PROVIDERS = ("codex", "antigravity", "copilot")
DEFAULT_COPILOT_MODEL = "claude-sonnet-4.6"
MAX_BACKOFF_SECONDS = 30
DEFAULT_TIMEOUT_SECONDS = 1800  # 0 disables; raise it for tasks expected to run long
TIMEOUT_RETURNCODE = 124

# Role → (model, reasoning effort) for codex, mirroring /delegate's tiers.
# codex-only: it is the one provider with per-call model + effort flags.
CODEX_ROLES = {
    "explorer": ("gpt-5.6-luna", "medium"),
    "doer": ("gpt-5.6-luna", "xhigh"),
    "planner": ("gpt-5.6-sol", "high"),
}
SUBAGENT_ENV = "DELEGATE_INVOKED_SUBAGENT"
LEGACY_NEST_GUARD_ENV = "EXT_SUBAGENT_ACTIVE"
NEST_GUARD_ENVS = (SUBAGENT_ENV, LEGACY_NEST_GUARD_ENV)
WORKER_PROMPT_PREFIX = f"""You are running as an external worker invoked by ext-subagent.

Do the task directly. Do not invoke ext-subagent, provider-specific
subagents, or any other delegation tool. If AGENTS.md, CLAUDE.md, skills, or provider
instructions recommend delegation, treat that as top-level orchestrator guidance and
ignore it for this run.

The environment variable {SUBAGENT_ENV}=1 is set for this worker and its child
processes so nested delegation can be detected.

Task:
"""


def assert_not_nested() -> None:
    """Block delegation loops at any depth.

    A worker dispatched here inherits these env vars; if it tries to run
    ext-subagent again (any provider), this fires. Deterministic — does not rely
    on the worker obeying a prose instruction. Children inherit os.environ
    automatically.
    """
    if any(os.environ.get(name) for name in NEST_GUARD_ENVS):
        sys.exit(
            "ext-subagent: refusing to nest — you are already running inside an "
            "ext-subagent worker. Do the task directly instead of re-delegating."
        )
    for name in NEST_GUARD_ENVS:
        os.environ[name] = "1"


def worker_prompt(prompt: str) -> str:
    return f"{WORKER_PROMPT_PREFIX}{prompt}"


@dataclass
class Result:
    returncode: int
    answer: str  # normalized final answer → stdout
    log: str  # progress / diagnostics / errors → stderr
    attempts: int = 1
    seconds: float = 0.0


def run_process(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run the provider CLI in its own process group so a timeout kills the whole tree.

    Agentic CLIs spawn children; subprocess.run's timeout only signals the direct
    child. 0 disables the timeout entirely.
    """
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout or None)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        stdout, stderr = proc.communicate()
        stderr += f"\next-subagent: killed after --timeout {timeout}s"
        return subprocess.CompletedProcess(cmd, TIMEOUT_RETURNCODE, stdout, stderr)


def run_codex(prompt: str, model: str | None, effort: str | None, timeout: int) -> Result:
    # codex streams progress to stdout/stderr and writes only the final message to -o.
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        out_path = Path(f.name)
    try:
        cmd = [
            "codex", "exec",
            "-s", "workspace-write",
            "--skip-git-repo-check",
            "--color", "never",
            "-o", str(out_path),
        ]  # fmt: skip
        if model:
            cmd += ["--model", model]
        if effort:
            cmd += ["-c", f'model_reasoning_effort="{effort}"']
        cmd.append(prompt)
        proc = run_process(cmd, timeout)
        answer = out_path.read_text() if proc.returncode == 0 else ""
        return Result(proc.returncode, answer, proc.stdout + proc.stderr)
    finally:
        out_path.unlink(missing_ok=True)


def run_antigravity(prompt: str, model: str | None, effort: str | None, timeout: int) -> Result:
    # model/effort are guaranteed None here (rejected in main); agy has no per-call model flag.
    cmd = [
        "agy",
        "--dangerously-skip-permissions",
        "--print-timeout",
        "10m",
        "-p",
        prompt,
    ]
    proc = run_process(cmd, timeout)
    return Result(proc.returncode, proc.stdout, proc.stderr)


def run_copilot(prompt: str, model: str | None, effort: str | None, timeout: int) -> Result:
    cmd = [
        "copilot",
        "--model", model or DEFAULT_COPILOT_MODEL,
        "--silent", "--allow-all",
        "-p", prompt,
    ]  # fmt: skip
    proc = run_process(cmd, timeout)
    return Result(proc.returncode, proc.stdout, proc.stderr)


RUNNERS = {"codex": run_codex, "antigravity": run_antigravity, "copilot": run_copilot}


def dispatch(
    provider: str,
    prompt: str,
    model: str | None,
    effort: str | None,
    timeout: int,
    retries: int,
    max_chars: int,
) -> Result:
    """Run the provider, retrying failed attempts with exponential backoff.

    Retries re-run the whole task, so they are safe for read/answer tasks but NOT for
    non-idempotent edits — keep --retries at 0 when the task writes files.
    """
    runner = RUNNERS[provider]
    start = time.monotonic()
    res = Result(1, "", "no attempt ran")
    for attempt in range(retries + 1):
        res = runner(prompt, model, effort, timeout)
        if res.returncode == 0 and not res.answer.strip():
            # An exit-0 empty answer is a provider failure in disguise; surface it
            # (and let retries re-run it) instead of returning silent success.
            res = Result(
                1, "", res.log + "\next-subagent: provider exited 0 but returned an empty answer"
            )
        res.attempts = attempt + 1
        if res.returncode == 0 or attempt == retries:
            break
        time.sleep(min(2**attempt, MAX_BACKOFF_SECONDS))
    res.seconds = time.monotonic() - start
    if max_chars and len(res.answer) > max_chars:
        res.answer = (
            res.answer[:max_chars] + f"\n... [truncated to {max_chars} chars]\n"
        )
    return res


def resolve_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt not in (None, "-") and prompt_file is not None:
        sys.exit("ext-subagent: pass a prompt argument OR --prompt-file, not both")
    if prompt_file is not None:
        return Path(prompt_file).read_text()
    if prompt not in (None, "-"):
        return prompt
    if sys.stdin.isatty():
        sys.exit(
            "ext-subagent: no prompt (give an argument, --prompt-file, or pipe stdin)"
        )
    text = sys.stdin.read()
    if not text.strip():
        sys.exit("ext-subagent: empty prompt from stdin")
    return text


def main() -> int:
    p = argparse.ArgumentParser(
        prog="ext-subagent",
        description="Dispatch a coding task to an agentic CLI provider.",
    )
    p.add_argument("provider", choices=PROVIDERS)
    p.add_argument(
        "prompt", nargs="?", help="task prompt; omit or pass '-' to read stdin"
    )
    p.add_argument("--prompt-file", metavar="PATH", help="read the prompt from a file")
    p.add_argument("--role", choices=sorted(CODEX_ROLES),
                   help="delegate tier; expands to a model + reasoning effort (codex only)")  # fmt: skip
    p.add_argument("--model", metavar="MODEL", help="model for codex/copilot")
    p.add_argument("--reasoning-effort", metavar="LEVEL",
                   choices=("minimal", "low", "medium", "high", "xhigh"),
                   help="reasoning effort (codex only)")  # fmt: skip
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_SECONDS, metavar="SECONDS",
                   help=f"kill the worker after SECONDS (default {DEFAULT_TIMEOUT_SECONDS}; "
                        "0 disables — raise or disable for tasks expected to run long)")  # fmt: skip
    p.add_argument("--retries", type=int, default=0, metavar="N",
                   help="retry failed attempts with backoff (unsafe for file-writing tasks)")  # fmt: skip
    p.add_argument("--max-output-chars", type=int, default=0, metavar="N",
                   help="truncate the returned answer to N chars (0 = no limit)")  # fmt: skip
    args = p.parse_args()

    if args.provider == "antigravity" and args.model:
        p.error("antigravity has no per-call model flag; set it in "
                "~/.gemini/antigravity-cli/settings.json or via 'agy /model'")  # fmt: skip
    if args.reasoning_effort and args.provider != "codex":
        p.error("--reasoning-effort is codex-only")
    if args.role:
        if args.provider != "codex":
            p.error("--role is codex-only; pick the model directly for other providers")
        if args.model or args.reasoning_effort:
            p.error("--role already sets the model and effort; don't combine it "
                    "with --model/--reasoning-effort")  # fmt: skip
        args.model, args.reasoning_effort = CODEX_ROLES[args.role]
    if args.timeout < 0:
        p.error("--timeout must be >= 0 (0 disables)")

    assert_not_nested()
    prompt = worker_prompt(resolve_prompt(args.prompt, args.prompt_file))
    res = dispatch(
        args.provider,
        prompt,
        args.model,
        args.reasoning_effort,
        args.timeout,
        args.retries,
        args.max_output_chars,
    )

    if res.returncode == 0:
        sys.stdout.write(res.answer)
    else:
        sys.stderr.write(res.log + res.answer)
        print(f"\next-subagent({args.provider}) failed", file=sys.stderr)

    print(
        f"[ext-subagent] provider={args.provider} model={args.model or 'default'} "
        f"attempts={res.attempts} rc={res.returncode} dur={res.seconds:.1f}s "
        f"answer_chars={len(res.answer)}",
        file=sys.stderr,
    )
    return res.returncode


if __name__ == "__main__":
    sys.exit(main())
