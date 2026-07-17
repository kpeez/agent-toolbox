#!/usr/bin/env python3
"""Print the first agent CLI that still has quota to spend.

Walks copilot -> agy -> codex -> claude and prints the command to run. Every
provider reports usage differently -- and copilot reports percent *remaining*
while codex and claude report percent *used* -- so each probe normalizes to
remaining. A provider we cannot measure is presumed available: its CLI fails at
call time and the caller learns then, which beats a selector that crashes
because a JSON file moved.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIN_REMAINING_PCT = 5.0
GH_TIMEOUT_SECONDS = 10
CODEX_WINDOWS = {300: "5h", 10080: "weekly"}
CLAUDE_WINDOWS = {"five_hour": "5h", "seven_day": "7d"}


@dataclass(frozen=True)
class Known:
    remaining_pct: float
    window: str


@dataclass(frozen=True)
class Unknown:
    reason: str


@dataclass(frozen=True)
class Absent:
    pass


Probe = Known | Unknown | Absent


def parse_copilot(payload: dict) -> Probe:
    try:
        snapshot = payload["quota_snapshots"]["premium_interactions"]
        if snapshot["unlimited"]:
            return Known(100.0, "monthly")
        remaining = float(snapshot["percent_remaining"])
    except (KeyError, TypeError, ValueError):
        return Unknown("unexpected copilot payload")
    return Known(max(remaining, 0.0), "monthly")


def parse_codex(record: dict, now: datetime) -> Probe:
    try:
        limits = record["rate_limits"]
        slots = [limits["primary"], limits["secondary"]]
    except (KeyError, TypeError):
        return Unknown("unexpected codex record")
    windows: list[Known] = []
    for slot in slots:
        if slot is None:
            continue
        try:
            minutes = slot["window_minutes"]
            resets_at = datetime.fromtimestamp(slot["resets_at"], tz=timezone.utc)
            used = float(slot["used_percent"])
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            return Unknown("unexpected codex window")
        remaining = 100.0 if now > resets_at else max(100.0 - used, 0.0)
        windows.append(Known(remaining, CODEX_WINDOWS.get(minutes, f"{minutes}min")))
    if not windows:
        return Unknown("no codex rate-limit windows")
    return min(windows, key=lambda window: window.remaining_pct)


def parse_claude(blob: dict, now: datetime) -> Probe:
    try:
        utilization = blob["cachedUsageUtilization"]["utilization"]
    except (KeyError, TypeError):
        return Unknown("no cached claude utilization")
    windows: list[Known] = []
    for key, name in CLAUDE_WINDOWS.items():
        try:
            slot = utilization[key]
            used = float(slot["utilization"])
            resets_at = slot["resets_at"]
        except (KeyError, TypeError, ValueError):
            return Unknown("unexpected claude window")
        # A null reset instant is an idle window with no live limit.
        if resets_at is None:
            windows.append(Known(100.0, name))
            continue
        try:
            # The comparison is inside the try: a naive instant parses fine and
            # only fails when compared against an aware one.
            rolled_over = now > datetime.fromisoformat(resets_at)
        except (TypeError, ValueError):
            return Unknown("unexpected claude reset instant")
        remaining = 100.0 if rolled_over else max(100.0 - used, 0.0)
        windows.append(Known(remaining, name))
    return min(windows, key=lambda window: window.remaining_pct)


def select(probes: Iterable[tuple[str, Probe]]) -> str | None:
    """Return the first provider with headroom, reporting skips on stderr.

    Takes an iterable rather than a sequence so callers can pass a generator and
    have the chain short-circuit: providers after the winner are never probed.
    """
    for name, probe in probes:
        match probe:
            case Absent():
                print(f"{name}: not on PATH", file=sys.stderr)
            case Known(remaining_pct=remaining, window=window) if (
                remaining < MIN_REMAINING_PCT
            ):
                print(f"{name}: {remaining}% remaining ({window})", file=sys.stderr)
            case Known():
                return name
            case Unknown():
                return name
            case _:
                raise ValueError(f"unhandled probe type for {name}: {probe!r}")
    return None


def probe_copilot() -> Probe:
    if shutil.which("copilot") is None:
        return Absent()
    try:
        result = subprocess.run(
            ["gh", "api", "/copilot_internal/user"],
            capture_output=True,
            text=True,
            timeout=GH_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return Unknown(f"gh api failed: {error}")
    if result.returncode != 0:
        return Unknown("gh api exited nonzero")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return Unknown("gh api returned non-JSON")
    return parse_copilot(payload)


def probe_agy() -> Probe:
    if shutil.which("agy") is None:
        return Absent()
    return Unknown("no quota interface")


def probe_codex(now: datetime) -> Probe:
    if shutil.which("codex") is None:
        return Absent()
    try:
        newest = max(
            (Path.home() / ".codex/sessions").glob("**/*.jsonl"),
            key=lambda path: path.stat().st_mtime,
        )
    except (ValueError, OSError):
        return Unknown("no codex session file")
    try:
        with newest.open(encoding="utf-8") as handle:
            last = None
            for line in handle:
                if '"rate_limits"' in line:
                    last = line
    except OSError as error:
        return Unknown(f"codex session unreadable: {error}")
    if last is None:
        return Unknown("no rate_limits in codex session")
    try:
        record = json.loads(last)["payload"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return Unknown("unparseable codex session line")
    return parse_codex(record, now)


def probe_claude(now: datetime) -> Probe:
    if shutil.which("claude") is None:
        return Absent()
    try:
        blob = json.loads((Path.home() / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return Unknown("~/.claude.json unreadable")
    return parse_claude(blob, now)


def main() -> int:
    now = datetime.now(timezone.utc)
    chain = (
        ("copilot", probe_copilot),
        ("agy", probe_agy),
        ("codex", lambda: probe_codex(now)),
        ("claude", lambda: probe_claude(now)),
    )
    winner = select((name, probe()) for name, probe in chain)
    if winner is None:
        print("no agent CLI has quota remaining", file=sys.stderr)
        return 1
    print(winner)
    return 0


if __name__ == "__main__":
    sys.exit(main())
