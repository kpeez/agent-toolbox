"""Pin the safety bounds and runtime contract of knack-graph.js as text.

The bug this guards: a conductor whose safety bounds silently drift. Nothing
executes this script in CI -- the workflow engine runs it -- so a renamed phase,
a widened fix-loop bound, a dropped re-entry cap, a forbidden nondeterministic
call, or a mistyped slice-complete marker would only surface mid-run, after
agents have been spent. These are static checks on the file's text.
"""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "knack-graph.js"
SOURCE = SCRIPT.read_text(encoding="utf-8")

EXPECTED_PHASES = ["Slice", "Implement", "Spec review", "Ship"]
SLICE_COMPLETE_MARKER = "<!-- knack:slice-complete -->"
FORBIDDEN_TOKENS = [
    "Date.now(",
    "Math.random(",
    "new Date()",
    "require(",
    "import ",
    ": string",
    "interface ",
]


def meta_block() -> str:
    """The `export const meta = {...}` literal, matched by brace counting."""
    start = SOURCE.index("{", SOURCE.index("export const meta"))
    depth = 0
    for index in range(start, len(SOURCE)):
        if SOURCE[index] == "{":
            depth += 1
        elif SOURCE[index] == "}":
            depth -= 1
            if depth == 0:
                return SOURCE[start : index + 1]
    raise AssertionError("meta block is not brace-balanced")


def meta_phase_titles() -> list[str]:
    """The titles declared inside meta's `phases:` array, in order.

    Bounded to the array's closing bracket: an unbounded slice would run to the
    end of the meta block, so any key added after `phases` that happens to carry
    a `title:` would silently pollute the parity check below.
    """
    block = meta_block()
    start = block.index("phases:")
    phases = block[start : block.index("]", start) + 1]
    return re.findall(r"title: '([^']*)'", phases)


def required_args() -> list[str]:
    """The names in `REQUIRED_ARGS = [...]`, derived rather than restated.

    Hardcoding the list here would let a new required arg be added without any
    of the checks below ever seeing it.
    """
    start = SOURCE.index("REQUIRED_ARGS = [")
    literal = SOURCE[start : SOURCE.index("]", start) + 1]
    names = re.findall(r"'([^']+)'", literal)

    assert names, "REQUIRED_ARGS is empty -- the args contract would be unenforced"
    return names


def test_script_opens_with_a_meta_literal_naming_the_workflow():
    assert SOURCE.startswith("export const meta")
    assert "name: 'knack-graph'" in meta_block()


def test_meta_declares_exactly_the_expected_phases():
    assert meta_phase_titles() == EXPECTED_PHASES


def test_every_declared_phase_is_called_and_no_others():
    called = re.findall(r"\bphase\('([^']*)'\)", SOURCE)

    assert called, "the script never calls phase() -- the live view would be blank"
    assert set(called) == set(meta_phase_titles())


def test_safety_bounds_are_declared_at_their_pinned_values():
    assert re.search(r"^const MAX_FIX_ROUNDS = 2$", SOURCE, re.MULTILINE)
    assert re.search(r"^const SPEC_REVIEW_REENTRIES = 1$", SOURCE, re.MULTILINE)
    assert re.search(r"^const MAX_FRONTIER_ROUNDS = 25$", SOURCE, re.MULTILINE)


def test_no_forbidden_runtime_tokens():
    present = [token for token in FORBIDDEN_TOKENS if token in SOURCE]

    assert present == []


def test_slice_complete_marker_is_spelled_exactly_and_used_at_both_ends():
    assert SOURCE.count(SLICE_COMPLETE_MARKER) >= 1
    # Written by the mark prompt, read by the frontier prompt: a marker only one
    # side knows about either loses slices or replays them.
    assert SOURCE.count("${SLICE_COMPLETE_MARKER}") >= 2


def test_every_required_args_field_is_read():
    # A field can be required, named in the error string, and still never read;
    # pin the actual read.
    for field in required_args():
        assert f"ARGS.{field}" in SOURCE


def test_every_required_args_field_is_advertised_in_meta():
    # whenToUse is the contract /start-loop reads when composing the launch
    # args; a required field missing from it is a silent launch failure.
    meta = meta_block()

    for field in required_args():
        assert field in meta
