"""Prove pick_agent.py picks the first agent CLI with quota left.

The payloads below are verbatim captures from a real machine, trimmed of account
identifiers. They are the point of these tests: every provider reports usage in
its own shape, with its own polarity, and the traps are all in the data --
copilot reports percent *remaining* alongside a negative credit balance, and
codex puts its weekly window in the positionally-named "primary" slot. A parser
written against a guessed shape passes a hand-written fixture and fails at 8am.

Selection short-circuits, so the chain is checked lazily: a probe for a provider
after the winner must never run.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

PICK_AGENT = Path(__file__).resolve().parent / "pick_agent.py"

sys.path.insert(0, str(PICK_AGENT.parent))

import pick_agent  # noqa: E402

Absent = pick_agent.Absent
Known = pick_agent.Known
Unknown = pick_agent.Unknown

# gh api /copilot_internal/user -- 1507 of 1500 premium interactions used.
COPILOT_EXHAUSTED = {
    "quota_reset_date": "2026-08-01",
    "quota_snapshots": {
        "premium_interactions": {
            "percent_remaining": 0.0,
            "quota_remaining": -7.9,
            "unlimited": False,
            "has_quota": False,
            "credits_used": 1507,
            "remaining": -8,
            "entitlement": 1500,
            "timestamp_utc": "2026-07-17T03:48:48.099Z",
        },
        "chat": {
            "percent_remaining": 100.0,
            "unlimited": True,
            "has_quota": True,
            "entitlement": 0,
        },
    },
}

# Newest ~/.codex/sessions/**/*.jsonl -- weekly window sits in "primary".
CODEX_WEEKLY_BLOWN = {
    "rate_limits": {
        "limit_id": "codex",
        "limit_name": None,
        "primary": {
            "used_percent": 99.0,
            "window_minutes": 10080,
            "resets_at": 1784784224,
        },
        "secondary": None,
        "credits": {"has_credits": False, "unlimited": False, "balance": "0"},
        "individual_limit": None,
        "plan_type": "plus",
        "rate_limit_reached_type": None,
    }
}

NOW = datetime(2026, 7, 17, 4, 0, tzinfo=timezone.utc)
AFTER_CODEX_RESET = datetime(2026, 7, 24, tzinfo=timezone.utc)


def explode() -> pick_agent.Probe:
    raise AssertionError("probed a provider after the winner")


def lazy_chain(chain: list[tuple[str, object]]) -> object:
    return ((name, probe()) for name, probe in chain)


class TodaysStateTests(unittest.TestCase):
    def test_exhausted_copilot_falls_through_to_agy_without_probing_the_rest(
        self,
    ) -> None:
        probed: list[str] = []

        def record(name: str, probe: pick_agent.Probe) -> pick_agent.Probe:
            probed.append(name)
            return probe

        chain = [
            ("copilot", lambda: record("copilot", parse_copilot_today())),
            ("agy", lambda: record("agy", Unknown("no quota interface"))),
            ("codex", explode),
        ]
        self.assertEqual(pick_agent.select(lazy_chain(chain)), "agy")
        self.assertEqual(probed, ["copilot", "agy"])

    def test_without_agy_installed_the_spent_chain_selects_nothing(self) -> None:
        # agy is the only fallback once copilot is spent: claude is deliberately
        # not in the chain, so an uninstalled agy leaves codex, and codex is
        # under the threshold.
        chain = [
            ("copilot", lambda: parse_copilot_today()),
            ("agy", lambda: Absent()),
            ("codex", lambda: pick_agent.parse_codex(CODEX_WEEKLY_BLOWN, NOW)),
        ]
        self.assertIsNone(pick_agent.select(lazy_chain(chain)))

    def test_every_provider_exhausted_selects_nothing(self) -> None:
        chain = [
            ("copilot", lambda: parse_copilot_today()),
            ("agy", lambda: Absent()),
            ("codex", lambda: Known(1.0, "weekly")),
        ]
        self.assertIsNone(pick_agent.select(lazy_chain(chain)))


def parse_copilot_today() -> pick_agent.Probe:
    return pick_agent.parse_copilot(COPILOT_EXHAUSTED)


class CopilotParserTests(unittest.TestCase):
    def test_zero_percent_remaining_survives_a_negative_credit_balance(self) -> None:
        self.assertEqual(parse_copilot_today(), Known(0.0, "monthly"))

    def test_unlimited_snapshot_reads_fully_available(self) -> None:
        payload = {
            "quota_snapshots": {
                "premium_interactions": {
                    "percent_remaining": 0.0,
                    "unlimited": True,
                    "has_quota": True,
                    "entitlement": 0,
                }
            }
        }
        self.assertEqual(pick_agent.parse_copilot(payload), Known(100.0, "monthly"))

    def test_missing_snapshot_is_unknown(self) -> None:
        self.assertIsInstance(
            pick_agent.parse_copilot({"quota_snapshots": {}}), Unknown
        )


class CodexParserTests(unittest.TestCase):
    def test_weekly_window_is_keyed_off_window_minutes_not_position(self) -> None:
        self.assertEqual(
            pick_agent.parse_codex(CODEX_WEEKLY_BLOWN, NOW), Known(1.0, "weekly")
        )

    def test_a_rolled_over_window_voids_a_stale_ninety_nine_percent_reading(
        self,
    ) -> None:
        self.assertEqual(
            pick_agent.parse_codex(CODEX_WEEKLY_BLOWN, AFTER_CODEX_RESET),
            Known(100.0, "weekly"),
        )

    def test_the_blown_window_governs_when_another_window_is_healthy(self) -> None:
        record = {
            "rate_limits": {
                "primary": {
                    "used_percent": 99.0,
                    "window_minutes": 10080,
                    "resets_at": 1784784224,
                },
                "secondary": {
                    "used_percent": 2.0,
                    "window_minutes": 300,
                    "resets_at": 1784784224,
                },
            }
        }
        probe = pick_agent.parse_codex(record, NOW)
        self.assertEqual(probe, Known(1.0, "weekly"))
        self.assertIsNone(pick_agent.select(lazy_chain([("codex", lambda: probe)])))

    def test_unexpected_record_is_unknown(self) -> None:
        self.assertIsInstance(pick_agent.parse_codex({}, NOW), Unknown)


class UnreadableSourceTests(unittest.TestCase):
    """Unknown means available: a missing file must never refuse a provider.

    Each `shutil.which` guard is stubbed to a fake path so the guard clears and
    the IO body underneath actually runs -- otherwise these assertions would be
    satisfied by `Absent()` without ever touching subprocess or the filesystem.
    Unknown is asserted exactly, never as `(Unknown, Absent)`, so an IO body
    that never executes cannot pass by accident.
    """

    def test_unknown_providers_are_selected(self) -> None:
        chain = [
            ("copilot", lambda: Unknown("gh api exited nonzero")),
            ("agy", explode),
        ]
        self.assertEqual(pick_agent.select(lazy_chain(chain)), "copilot")

    def test_gh_failure_yields_unknown_rather_than_a_traceback(self) -> None:
        with (
            patch("pick_agent.shutil.which", return_value="/usr/local/bin/copilot"),
            patch("pick_agent.subprocess.run", side_effect=OSError("gh not found")),
        ):
            probe = pick_agent.probe_copilot()
        self.assertIsInstance(probe, Unknown)

    def test_gh_nonzero_exit_yields_unknown(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="")
        with (
            patch("pick_agent.shutil.which", return_value="/usr/local/bin/copilot"),
            patch("pick_agent.subprocess.run", return_value=completed),
        ):
            probe = pick_agent.probe_copilot()
        self.assertIsInstance(probe, Unknown)

    def test_gh_non_json_stdout_yields_unknown(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="not json"
        )
        with (
            patch("pick_agent.shutil.which", return_value="/usr/local/bin/copilot"),
            patch("pick_agent.subprocess.run", return_value=completed),
        ):
            probe = pick_agent.probe_copilot()
        self.assertIsInstance(probe, Unknown)

    def test_gh_success_delegates_to_parse_copilot(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps(COPILOT_EXHAUSTED)
        )
        with (
            patch("pick_agent.shutil.which", return_value="/usr/local/bin/copilot"),
            patch("pick_agent.subprocess.run", return_value=completed),
        ):
            probe = pick_agent.probe_copilot()
        self.assertEqual(probe, Known(0.0, "monthly"))

    def test_no_codex_session_directory_yields_unknown(self) -> None:
        with (
            patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
            patch("pick_agent.Path.home", return_value=Path("/nonexistent-home")),
        ):
            probe = pick_agent.probe_codex(NOW)
        self.assertIsInstance(probe, Unknown)

    def test_codex_session_without_rate_limits_line_yields_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            (sessions / "rollout.jsonl").write_text(
                '{"other": true}\n', encoding="utf-8"
            )
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertIsInstance(probe, Unknown)

    def test_a_fresh_empty_session_does_not_hide_the_reading_beneath_it(
        self,
    ) -> None:
        # Codex writes a rollout the instant a session opens, before any
        # response has attached rate_limits. Keying off the newest file alone
        # reported Unknown -- which the optimistic policy reads as "available"
        # -- while codex sat at 100% used. Observed live on 2026-07-16.
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            older = sessions / "rollout-older.jsonl"
            older.write_text(
                json.dumps({"payload": CODEX_WEEKLY_BLOWN}) + "\n", encoding="utf-8"
            )
            newer = sessions / "rollout-newer.jsonl"
            newer.write_text('{"payload": {"other": true}}\n', encoding="utf-8")
            os.utime(older, (1_000_000, 1_000_000))
            os.utime(newer, (2_000_000, 2_000_000))
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertEqual(probe, Known(1.0, "weekly"))

    def test_an_exhausted_premium_record_does_not_hide_the_reading_beneath_it(
        self,
    ) -> None:
        # Verbatim capture, 2026-07-16 23:40. On hitting the usage limit codex
        # writes a "premium"-bucket record whose windows are both null: the line
        # exists and parses, it just carries no reading. It sat directly on top
        # of a "codex"-bucket record reading 100% used, so keying off the newest
        # rate_limits *line* reported Unknown -- i.e. "available" -- for a
        # provider with nothing left.
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            real = sessions / "rollout-real.jsonl"
            real.write_text(
                json.dumps({"payload": CODEX_WEEKLY_BLOWN}) + "\n", encoding="utf-8"
            )
            spent = sessions / "rollout-premium.jsonl"
            spent.write_text(
                json.dumps(
                    {
                        "payload": {
                            "rate_limits": {
                                "limit_id": "premium",
                                "limit_name": None,
                                "primary": None,
                                "secondary": None,
                                "credits": {
                                    "has_credits": False,
                                    "unlimited": False,
                                    "balance": "0",
                                },
                                "plan_type": None,
                            }
                        }
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            os.utime(real, (1_000_000, 1_000_000))
            os.utime(spent, (2_000_000, 2_000_000))
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertEqual(probe, Known(1.0, "weekly"))

    def test_an_unparseable_line_does_not_poison_the_scan(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            real = sessions / "rollout-real.jsonl"
            real.write_text(
                json.dumps({"payload": CODEX_WEEKLY_BLOWN}) + "\n", encoding="utf-8"
            )
            junk = sessions / "rollout-junk.jsonl"
            junk.write_text('{"rate_limits": TRUNCATED\n', encoding="utf-8")
            os.utime(real, (1_000_000, 1_000_000))
            os.utime(junk, (2_000_000, 2_000_000))
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertEqual(probe, Known(1.0, "weekly"))

    def test_no_recent_session_carries_a_reading_yields_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            for index in range(3):
                (sessions / f"rollout-{index}.jsonl").write_text(
                    '{"other": true}\n', encoding="utf-8"
                )
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertIsInstance(probe, Unknown)

    def test_the_scan_is_bounded_so_a_stale_reading_cannot_resurface(self) -> None:
        # A machine accumulates hundreds of sessions; an unbounded walk would
        # read them all to surface a reading its own resets_at would void.
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            buried = sessions / "rollout-buried.jsonl"
            buried.write_text(
                json.dumps({"payload": CODEX_WEEKLY_BLOWN}) + "\n", encoding="utf-8"
            )
            os.utime(buried, (1_000_000, 1_000_000))
            for index in range(pick_agent.CODEX_SESSIONS_SCANNED):
                empty = sessions / f"rollout-empty-{index}.jsonl"
                empty.write_text('{"other": true}\n', encoding="utf-8")
                os.utime(empty, (2_000_000 + index, 2_000_000 + index))
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertIsInstance(probe, Unknown)

    def test_codex_session_with_rate_limits_delegates_to_parse_codex(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            sessions = Path(home) / ".codex/sessions"
            sessions.mkdir(parents=True)
            line = json.dumps({"payload": CODEX_WEEKLY_BLOWN})
            (sessions / "rollout.jsonl").write_text(line + "\n", encoding="utf-8")
            with (
                patch("pick_agent.shutil.which", return_value="/usr/local/bin/codex"),
                patch("pick_agent.Path.home", return_value=Path(home)),
            ):
                probe = pick_agent.probe_codex(NOW)
        self.assertEqual(probe, Known(1.0, "weekly"))

    def test_main_selects_agy_and_never_probes_codex(self) -> None:
        def explode_probe(now: datetime) -> pick_agent.Probe:
            raise AssertionError("main probed codex after agy won")

        with (
            patch("pick_agent.probe_copilot", return_value=parse_copilot_today()),
            patch("pick_agent.probe_agy", return_value=Unknown("no quota interface")),
            patch("pick_agent.probe_codex", side_effect=explode_probe),
            patch("builtins.print") as mock_print,
        ):
            exit_code = pick_agent.main()
        self.assertEqual(exit_code, 0)
        mock_print.assert_any_call("agy")


class CommandLineTests(unittest.TestCase):
    def test_the_script_prints_one_bare_word_to_stdout(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PICK_AGENT)], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn(result.stdout.strip(), {"copilot", "agy", "codex"})
        self.assertEqual(len(result.stdout.split()), 1)

    def test_exhausted_chain_exits_one_with_empty_stdout(self) -> None:
        script = (
            f"import sys; sys.path.insert(0, {str(PICK_AGENT.parent)!r});"
            "import pick_agent;"
            "pick_agent.probe_copilot = lambda: pick_agent.Known(0.0, 'monthly');"
            "pick_agent.probe_agy = lambda: pick_agent.Absent();"
            "pick_agent.probe_codex = lambda now: pick_agent.Known(1.0, 'weekly');"
            "sys.exit(pick_agent.main())"
        )
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("copilot: 0.0% remaining (monthly)", result.stderr)


if __name__ == "__main__":
    unittest.main()
