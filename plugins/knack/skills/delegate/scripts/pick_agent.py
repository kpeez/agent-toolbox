#!/usr/bin/env python3
"""Print the first agent CLI that still has quota to spend.

Walks copilot -> agy -> codex and prints the command to run. Every provider
reports usage differently -- and copilot reports percent *remaining* while codex
reports percent *used* -- so each probe normalizes to remaining. A provider we
cannot measure is presumed available: its CLI fails at call time and the caller
learns then, which beats a selector that crashes because a JSON file moved.

Claude is deliberately not in the chain. A Claude session that wants Claude work
has its own in-process subagent tools; routing it back out through this script
would spawn a second session to do what the caller can already do directly.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIN_REMAINING_PCT = 5.0
GH_TIMEOUT_SECONDS = 10
CODEX_SESSIONS_SCANNED = 10
CODEX_WINDOWS = {300: "5h", 10080: "weekly"}


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


def select(
    probes: Iterable[tuple[str, Probe]], *, allow_unknown: bool = True
) -> str | None:
    """Return the first provider with headroom, reporting skips on stderr.

    Takes an iterable rather than a sequence so callers can pass a generator and
    have the chain short-circuit: providers after the winner are never probed.

    `allow_unknown` is the policy axis. True presumes an unmeasurable provider is
    available -- right when a human reads the output, since the CLI fails at call
    time and the caller learns then. False skips it, which is what an unattended
    caller wants: a skipped run is cheap, an unreviewed bad one is not.
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
            case Unknown(reason=reason) if not allow_unknown:
                print(f"{name}: unmeasurable ({reason})", file=sys.stderr)
            case Unknown():
                return name
            case _:
                raise ValueError(f"unhandled probe type for {name}: {probe!r}")
    return None


def probe_chain(now: datetime) -> Iterator[tuple[str, Probe]]:
    """Probe every provider in chain order.

    A generator, not a tuple: `select` short-circuits, so a provider after the
    winner is never probed and never pays for its `gh api` call or file read.
    Chain order lives here alone -- a second copy in the runner would be one more
    normative fact that cannot notice the two have drifted apart.
    """
    yield "copilot", probe_copilot()
    yield "agy", probe_agy()
    yield "codex", probe_codex(now)


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


def last_rate_limit_line(path: Path) -> str | None:
    try:
        with path.open(encoding="utf-8") as handle:
            last = None
            for line in handle:
                if '"rate_limits"' in line:
                    last = line
            return last
    except OSError:
        return None


def probe_codex(now: datetime) -> Probe:
    if shutil.which("codex") is None:
        return Absent()
    try:
        sessions = sorted(
            (Path.home() / ".codex/sessions").glob("**/*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return Unknown("codex session directory unreadable")
    if not sessions:
        return Unknown("no codex session file")
    # Newest session that yields an actual *reading*, not the newest file and not
    # the newest rate_limits line. Two distinct things sit on top of a real
    # reading and each reports Unknown -- which the optimistic policy takes as
    # "available" -- exactly while codex is in use:
    #
    #   1. Codex writes a rollout the instant a session opens, before any
    #      response has attached rate_limits, so the newest file is often empty.
    #   2. On hitting the usage limit codex writes a "premium"-bucket record
    #      whose primary and secondary windows are both null. The line exists and
    #      parses; it simply carries no reading. Observed 2026-07-16, sitting
    #      directly on top of a "codex"-bucket record reading 100% used.
    #
    # So keep walking until a record parses to Known. Bounded: a machine
    # accumulates hundreds of sessions, and a reading older than the newest few
    # is voided by its own resets_at anyway.
    for path in sessions[:CODEX_SESSIONS_SCANNED]:
        line = last_rate_limit_line(path)
        if line is None:
            continue
        try:
            record = json.loads(line)["payload"]
        except (json.JSONDecodeError, KeyError, TypeError):
            continue
        probe = parse_codex(record, now)
        if isinstance(probe, Known):
            return probe
    return Unknown("no usable rate limits in recent codex sessions")


def main() -> int:
    winner = select(probe_chain(datetime.now(timezone.utc)))
    if winner is None:
        print("no agent CLI has quota remaining", file=sys.stderr)
        return 1
    print(winner)
    return 0


if __name__ == "__main__":
    sys.exit(main())
