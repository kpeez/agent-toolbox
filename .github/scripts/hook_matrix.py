#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Run every plugin hook command on every host shell and runtime, and compare what each one does.

Claude Code runs a hook command with sh. Codex runs it with the user's shell,
which may be fish. run-ts starts bun when it is on PATH, else node. A hook that
works on one of these hosts and does nothing on another is the bug this
catches: fish rejecting `${CLAUDE_PLUGIN_ROOT}`, or node never calling a
`main()` behind `import.meta.main`.

Each cell is one shell (sh, fish) and one runtime (each --runtime, alone on
PATH). For each hooks.json command and each recorded payload in
hook_payloads.json that its event and matcher select, every cell must have the
same effect as the first cell: exit code, stdout, stderr, and the files in its
sandbox, after the runtime path and name are normalized. The first cell must
have an effect, so a payload the hook ignores fails. The sandbox gives the
hooks a Rex session: REX_SESSION, a fake `rex` that logs its calls, and one
mirror block for the payload's session.

Usage: hook_matrix.py --runtime <bun or node path> [--runtime ...]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PAYLOADS = json.loads((Path(__file__).parent / "hook_payloads.json").read_text())
SHELLS = ("sh", "fish")
REX_SESSION = "rex-hook-matrix"
FAKE_REX = """#!/bin/sh
printf '%s\\n' "$*" >> "$HOME/rex-calls.log"
case "$*" in *program_status*) echo '{"records":[{"state":"done","updated_at":"1"}]}' ;; esac
"""


def selects(matcher: str | None, tool: str | None) -> bool:
    """Claude Code's matcher rule: empty or `*` selects all; otherwise a regex over the tool name."""
    if not matcher or matcher == "*" or tool is None:
        return True
    return re.fullmatch(matcher, tool) is not None


def snapshot(sandbox: Path) -> dict[str, str]:
    files = {}
    for path in sorted(sandbox.rglob("*")):
        rel = path.relative_to(sandbox).as_posix()
        if path.is_file() and rel.split("/")[0] not in ("bin", "xdg"):
            files[rel] = path.read_text(errors="replace")
    return files


def run_cell(
    command: str, plugin: Path, payload: dict, shell: str, runtime: Path, timeout: int
) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        for sub in ("bin", "work", "xdg", "home/.cache/rex-agents"):
            (sandbox / sub).mkdir(parents=True)
        (sandbox / "bin" / runtime.name).symlink_to(runtime)
        (sandbox / "bin" / "rex").write_text(FAKE_REX)
        (sandbox / "bin" / "rex").chmod(0o755)
        # One row file of rex_mirror.ts remember: <session_id>.<uuid>.json.
        block = {"rex_session": REX_SESSION, "block": "block-1"}
        row = f"{payload['session_id']}.00000000-0000-4000-8000-000000000001.json"
        (sandbox / "home/.cache/rex-agents" / row).write_text(json.dumps(block) + "\n")
        env = {
            "PATH": f"{sandbox / 'bin'}:/usr/bin:/bin",
            "HOME": str(sandbox / "home"),
            "XDG_CONFIG_HOME": str(sandbox / "xdg/config"),
            "XDG_DATA_HOME": str(sandbox / "xdg/data"),
            "XDG_CACHE_HOME": str(sandbox / "xdg/cache"),
            "CLAUDE_PLUGIN_ROOT": str(plugin),
            "REX_SESSION": REX_SESSION,
        }
        stdin = json.dumps(payload).replace("@SANDBOX@", str(sandbox))
        before = snapshot(sandbox)
        try:
            done = subprocess.run(
                [shutil.which(shell) or shell, "-c", command],
                check=False,
                input=stdin,
                capture_output=True,
                text=True,
                env=env,
                cwd=sandbox / "work",
                timeout=timeout,
            )
            effect = {
                "exit": done.returncode,
                "stdout": done.stdout,
                "stderr": done.stderr,
            }
        except subprocess.TimeoutExpired:
            effect = {"exit": "timeout", "stdout": "", "stderr": ""}
        after = snapshot(sandbox)
        effect["files"] = {k: v for k, v in after.items() if before.get(k) != v}
        effect["removed"] = sorted(set(before) - set(after))
        text = json.dumps(effect, sort_keys=True)
        for real in {str(sandbox), os.path.realpath(sandbox)}:
            text = text.replace(real, "<sandbox>")
        for path in {
            str(runtime),
            os.path.realpath(runtime),
            str(sandbox / "bin" / runtime.name),
        }:
            text = text.replace(path, "<runtime>")
        text = re.sub(r"\s?--disable-warning=ExperimentalWarning", "", text)
        text = re.sub(r"\b(bun|node)\b", "<runtime>", text)
        return json.loads(text)


def hooks():
    """Yield each hooks.json command with its plugin, case name, and the payloads it selects."""
    for hooks_json in sorted(ROOT.glob("plugins/*/hooks/hooks.json")):
        plugin = hooks_json.parent.parent
        for event, groups in json.loads(hooks_json.read_text())["hooks"].items():
            for group in groups:
                matcher = group.get("matcher")
                name = f"{plugin.name} {event}{'/' + matcher if matcher else ''}"
                payloads = [p for p in PAYLOADS if p["hook_event_name"] == event and selects(matcher, p.get("tool_name"))]
                for hook in group["hooks"]:
                    yield plugin, name, hook, payloads


def problems(plugin: Path, hook: dict, payload: dict, cells: list, label: dict) -> list[str]:
    """Run one hook and payload in every cell; return each way a cell differs from the reference cell."""
    effects = [run_cell(hook["command"], plugin, payload, s, r, hook.get("timeout", 60)) for s, r in cells]
    found = [f"{s} + {label[r]}: {json.dumps(e)[:400]}" for (s, r), e in zip(cells, effects) if e != effects[0]]
    if not any(effects[0][key] for key in ("stdout", "stderr", "files", "removed")):
        found.insert(0, "the reference cell had no effect: pick a payload the hook acts on")
    if found:
        s, r = cells[0]
        found.insert(0, f"reference {s} + {label[r]}: {json.dumps(effects[0])[:400]}")
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--runtime", action="append", type=Path, required=True, help="a bun or node binary; repeat")
    args = parser.parse_args()
    for runtime in args.runtime:
        if runtime.name not in ("bun", "node"):
            parser.error(f"{runtime}: name the bun or node binary itself")
    for name in ("bun", "node"):
        for folder in ("/usr/bin", "/bin"):
            if os.path.exists(f"{folder}/{name}"):
                parser.error(f"{folder}/{name} would be on every cell's PATH")
    if shutil.which("fish") is None:
        parser.error("fish is not installed")
    cells = [(shell, runtime) for shell in SHELLS for runtime in args.runtime]
    version = lambda r: subprocess.run([r, "--version"], check=True, capture_output=True, text=True).stdout.strip()
    label = {r: f"{r.name} {version(r)}" for r in args.runtime}
    failures = 0
    for plugin, name, hook, payloads in hooks():
        if not payloads:
            failures += 1
            print(f"FAIL {name}: no payload in hook_payloads.json selects this hook; record one")
        for payload in payloads:
            case = f"{name} <- {payload.get('tool_name', payload['hook_event_name'])}"
            found = problems(plugin, hook, payload, cells, label)
            failures += bool(found)
            print(f"FAIL {case}\n  " + "\n  ".join(found) if found else f"PASS {case} ({len(cells)} cells)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
