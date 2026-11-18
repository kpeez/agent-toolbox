#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tests for the mirror wrapper and the mirror hook's decisions.

The wrapper cases run the exact command the hook builds, in zsh and bash, with
the REX_* variables removed so no viewer block opens.
"""

import base64
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[2]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


hook = load("mirror_hook", PLUGIN / "hooks" / "mirror_hook.py")

CASES = [
    ("success", "printf 'a\\nb\\n'", b"a\nb\n", 0),
    ("failure", "printf 'x\\n'; false", b"x\n", 1),
    ("explicit exit", "printf 'y\\n'; exit 3", b"y\n", 3),
    ("no trailing newline", "printf 'no-newline'", b"no-newline", 0),
    ("and-list", "true && printf 'ok\\n' && false", b"ok\n", 1),
    ("stderr merged", "printf 'err\\n' >&2; exit 2", b"err\n", 2),
    ("empty output", "true", b"", 0),
    (
        "own EXIT trap",
        "trap 'echo cleanup' EXIT; echo work; exit 4",
        b"work\ncleanup\n",
        4,
    ),
    ("exec", "exec sh -c 'echo execd; exit 6'", b"execd\n", 6),
    ("trailing comment", "echo hi # note", b"hi\n", 0),
]
SHELLS = [s for s in ("/bin/zsh", "/bin/bash") if Path(s).exists()]
NO_REX = {k: v for k, v in os.environ.items() if not k.startswith("REX_")}


class WrapperMatrix(unittest.TestCase):
    def test_output_and_status_survive_the_pipe(self):
        uv = shutil.which("uv")
        for shell in SHELLS:
            for name, cmd, want_out, want_rc in CASES:
                with self.subTest(shell=shell, case=name):
                    wrapped = hook.mirrored(cmd, "[claude] test", "", uv)
                    r = subprocess.run(
                        [shell, "-c", wrapped],
                        capture_output=True,
                        env=NO_REX,
                        check=False,
                    )
                    self.assertEqual(r.stdout, want_out)
                    self.assertEqual(r.returncode, want_rc)

    def test_missing_marker_exits_125(self):
        r = subprocess.run(
            [
                "uv",
                "run",
                "--script",
                str(PLUGIN / "scripts" / "rex_mirror.py"),
                "[claude] test",
            ],
            input=b"output without a marker\n",
            capture_output=True,
            env=NO_REX,
            check=False,
        )
        self.assertEqual(r.returncode, 125)
        self.assertEqual(r.stdout, b"output without a marker\n")
        self.assertEqual(len(r.stderr.decode().strip().splitlines()), 1)


class ViewerOutput(unittest.TestCase):
    def test_only_the_nonce_exit_line_ends_the_view(self):
        def report(state, msg):
            return f"\x1b]7501;state={state}:app=rex-mirror:msg={base64.b64encode(msg.encode()).decode()}\x1b\\"

        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "mirror.log"
            log.write_text(
                "first\n"
                "__rex_mirror_exit=0\n"
                "__rex_mirror_exit_other=0\n"
                "\x1b]7501;state=done:msg=eA==\x1b\\after-spoof\n"
                "\x1b]75\x1b]7501;state=done\x1b\\01;state=done\x1b\\nested\n"
                "\x9d7501;state=done\x9c\x1b[31mred\x1b[0m\tok\r\n"
                "\n__rex_mirror_exit_abc123=3\n"
            )
            r = subprocess.run(
                [
                    "uv",
                    "run",
                    "--script",
                    str(PLUGIN / "scripts" / "rex_mirror_view.py"),
                    str(log),
                    "[claude] t",
                    "abc123",
                ],
                capture_output=True,
                text=False,
                timeout=30,
                check=False,
            )
            self.assertEqual(r.returncode, 0)
            self.assertEqual(
                r.stdout.decode(),
                report("working", "[claude] t")
                + "first\n__rex_mirror_exit=0\n__rex_mirror_exit_other=0\n]7501;state=done:msg=eA==\\after-spoof\n"
                + "]75]7501;state=done\\01;state=done\\nested\n"
                + "7501;state=done\x1b[31mred\x1b[0m\tok\r\n\n"
                + report("error", "[claude] t: exit 3"),
            )
            self.assertFalse(log.exists())


def event(command="make test", background=True, **extra):
    tool_input = {"command": command, "description": "Run the tests", "timeout": 600000}
    if background is not None:
        tool_input["run_in_background"] = background
    return {
        "tool_name": "Bash",
        "session_id": "s-1",
        "permission_mode": "auto",
        "tool_input": tool_input,
        **extra,
    }


def which_all(name):
    return f"/usr/local/bin/{name}"


ENV = {"REX_SESSION": "session:x"}


class HookDecisions(unittest.TestCase):
    def test_rewrites_a_background_call_in_rex(self):
        out = hook.decide(event(), ENV, which_all)
        spec = out["hookSpecificOutput"]
        self.assertEqual(spec["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", spec)
        updated = spec["updatedInput"]
        self.assertIn(
            "{ ( make test\n ); printf '\\n__rex_rc=%d\\n' \"$?\"; } 2>&1 | /usr/local/bin/uv run --script",
            updated["command"],
        )
        self.assertIn("'[claude] Run the tests' s-1", updated["command"])
        self.assertEqual(
            {k: v for k, v in updated.items() if k != "command"},
            {
                "description": "Run the tests",
                "timeout": 600000,
                "run_in_background": True,
            },
        )

    def test_leaves_foreground_calls_alone(self):
        self.assertIsNone(hook.decide(event(background=False), ENV, which_all))
        self.assertIsNone(hook.decide(event(background=None), ENV, which_all))

    def test_leaves_calls_outside_rex_alone(self):
        self.assertIsNone(hook.decide(event(), {}, which_all))

    def test_kill_switch(self):
        self.assertIsNone(
            hook.decide(event(), {**ENV, "REX_AGENTS_MIRROR": "0"}, which_all)
        )
        self.assertIsNotNone(
            hook.decide(event(), {**ENV, "REX_AGENTS_MIRROR": "1"}, which_all)
        )

    def test_no_double_wrap(self):
        once = hook.decide(event(), ENV, which_all)["hookSpecificOutput"][
            "updatedInput"
        ]["command"]
        self.assertIsNone(hook.decide(event(command=once), ENV, which_all))

    def test_needs_rex_and_uv(self):
        self.assertIsNone(
            hook.decide(event(), ENV, lambda n: None if n == "rex" else which_all(n))
        )
        self.assertIsNone(
            hook.decide(event(), ENV, lambda n: None if n == "uv" else which_all(n))
        )

    def test_only_modes_that_do_not_prompt(self):
        for mode in ("auto", "bypassPermissions"):
            self.assertIsNotNone(
                hook.decide(event(permission_mode=mode), ENV, which_all)
            )
        for mode in ("manual", "default", "acceptEdits", "plan", "dontAsk", None):
            self.assertIsNone(hook.decide(event(permission_mode=mode), ENV, which_all))

    def test_other_tools_are_ignored(self):
        self.assertIsNone(
            hook.decide({**event(), "tool_name": "Monitor"}, ENV, which_all)
        )

    def test_labels(self):
        sub = hook.decide(event(agent_id="a1"), ENV, which_all)["hookSpecificOutput"][
            "updatedInput"
        ]
        self.assertIn("'[claude:sub] Run the tests'", sub["command"])
        long = event()
        long["tool_input"]["description"] = "x" * 100
        cmd = hook.decide(long, ENV, which_all)["hookSpecificOutput"]["updatedInput"][
            "command"
        ]
        self.assertIn(f"'[claude] {'x' * 60}'", cmd)
        bare = event()
        del bare["tool_input"]["description"]
        cmd = hook.decide(bare, ENV, which_all)["hookSpecificOutput"]["updatedInput"][
            "command"
        ]
        self.assertIn("'[claude] make test'", cmd)


if __name__ == "__main__":
    unittest.main()
