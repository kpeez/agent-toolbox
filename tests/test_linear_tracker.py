"""Behavior tests for plugins/swe/scripts/linear_tracker.py.

Every Linear and git call is injected, so these drive the policy with scripted
CLI output and assert on what survives the filter and how the container ladder
resolves.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "swe" / "scripts" / "linear_tracker.py"

spec = importlib.util.spec_from_file_location("linear_tracker", SCRIPT)
assert spec and spec.loader
tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker)


def issue(
    identifier: str,
    *,
    state: str = "started",
    labels: list[str] | None = None,
    blocked_by: list[dict[str, Any]] | None = None,
    related_to: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One issue node shaped like `linear issue query --json` output."""
    relations = [{"type": "blocks", "issue": b} for b in blocked_by or []]
    relations += [{"type": "related", "issue": r} for r in related_to or []]
    return {
        "id": f"id-{identifier}",
        "identifier": identifier,
        "title": f"slice {identifier}",
        "state": {"type": state},
        "labels": {"nodes": [{"name": name} for name in labels or []]},
        "inverseRelations": {"nodes": relations},
    }


def run(
    *issues: dict[str, Any], merged: list[str] | None = None, base: str | None = "base"
) -> list[str]:
    """Identifiers reported workable, given `merged` slice branches on `base`."""

    def fake_linear(args: list[str]) -> str:
        return json.dumps({"nodes": list(issues)})

    def fake_git(args: list[str]) -> str:
        return "\n".join([f"slice/{name}" for name in merged or []] + ["main"])

    result = tracker.workable_issues(
        "container-1", base, run_linear_fn=fake_linear, run_git_fn=fake_git
    )
    return [entry["identifier"] for entry in result]


# ---- git is the authority on "already merged in this run" -------------------


def test_a_merged_slice_is_dropped_from_the_frontier() -> None:
    assert run(issue("KP-1"), issue("KP-2"), merged=["KP-1"]) == ["KP-2"]


def test_a_merged_blocker_unblocks_its_dependent() -> None:
    """The stall both observed multi-slice runs hit: a merged slice keeps its
    open tracker state until the PR lands, so judging blockers by state alone
    strands every dependent slice."""
    blocker = issue("KP-1")
    assert run(blocker, issue("KP-2", blocked_by=[blocker]), merged=["KP-1"]) == [
        "KP-2"
    ]


def test_an_unmerged_blocker_still_blocks() -> None:
    blocker = issue("KP-1")
    assert run(blocker, issue("KP-2", blocked_by=[blocker]), merged=[]) == ["KP-1"]


def test_a_closed_blocker_unblocks_its_dependent() -> None:
    blocker = issue("KP-1", state="completed")
    assert run(blocker, issue("KP-2", blocked_by=[blocker])) == ["KP-2"]


def test_a_dependent_waits_for_every_blocker_not_just_one() -> None:
    done, pending = issue("KP-1"), issue("KP-2")
    dependent = issue("KP-3", blocked_by=[done, pending])
    assert run(done, pending, dependent, merged=["KP-1"]) == ["KP-2"]


def test_a_chain_advances_one_slice_per_round() -> None:
    """Each round merges the head and the next becomes workable, which is what
    lets the loop drain a chain without a manual relaunch."""
    first, second, third = issue("KP-1"), issue("KP-2"), issue("KP-3")
    second["inverseRelations"]["nodes"] = [{"type": "blocks", "issue": first}]
    third["inverseRelations"]["nodes"] = [{"type": "blocks", "issue": second}]

    assert run(first, second, third, merged=[]) == ["KP-1"]
    assert run(first, second, third, merged=["KP-1"]) == ["KP-2"]
    assert run(first, second, third, merged=["KP-1", "KP-2"]) == ["KP-3"]
    assert run(first, second, third, merged=["KP-1", "KP-2", "KP-3"]) == []


def test_the_legacy_branch_prefix_is_still_recognised() -> None:
    """A run already in flight when this ships has knack/slice/* branches."""

    def fake_git(args: list[str]) -> str:
        return "knack/slice/KP-1\nmain\n"

    assert tracker.merged_slice_identifiers("base", fake_git) == {"KP-1"}


def test_without_a_base_branch_nothing_counts_as_merged() -> None:
    assert run(issue("KP-1"), base=None) == ["KP-1"]


# ---- filters that do not involve git ----------------------------------------


def test_ready_for_human_is_excluded() -> None:
    assert run(issue("KP-1", labels=["ready-for-human"]), issue("KP-2")) == ["KP-2"]


def test_closed_issues_are_excluded() -> None:
    assert run(issue("KP-1", state="canceled"), issue("KP-2", state="completed")) == []


def test_a_related_relation_does_not_block() -> None:
    """Live containers carry mostly `related` edges; only `blocks` gates work."""
    other = issue("KP-1")
    assert run(other, issue("KP-2", related_to=[other])) == ["KP-1", "KP-2"]


def test_a_failed_query_raises_rather_than_reporting_an_empty_frontier() -> None:
    def fake_linear(args: list[str]) -> str:
        return "Failed to query issues: no default team"

    with pytest.raises(tracker.LinearError, match="did not return JSON"):
        tracker.workable_issues("c", None, run_linear_fn=fake_linear)


# ---- spec frontmatter -------------------------------------------------------

SPEC = """---
authors:
  - claude
created: 2026-07-24
status: review
---

# 0002 - Morphometric baselines
"""


def write_spec(
    tmp_path: Path, name: str = "0002-morphometric-baselines.md", body: str = SPEC
) -> Path:
    path = tmp_path / name
    path.write_text(body)
    return path


def test_writing_a_key_preserves_nested_yaml(tmp_path: Path) -> None:
    """A dict round-trip would flatten `authors:` into a scalar; line editing
    leaves every other line byte-identical."""
    path = write_spec(tmp_path)
    tracker.set_container(path, "container-1")
    text = path.read_text()

    assert "tracker_container: container-1" in text
    assert "tracker: linear" in text
    assert "authors:\n  - claude" in text
    assert "status: review" in text
    assert text.count("---") == 2


def test_setting_an_existing_key_replaces_it_rather_than_duplicating(
    tmp_path: Path,
) -> None:
    path = write_spec(tmp_path)
    tracker.set_container(path, "container-1")
    tracker.set_container(path, "container-2")
    text = path.read_text()

    assert text.count("tracker_container:") == 1
    assert "container-2" in text
    assert "container-1" not in text


def test_slug_is_taken_from_the_numbered_filename() -> None:
    assert (
        tracker.slug_for(Path("0002-morphometric-baselines.md"))
        == "morphometric-baselines"
    )


# ---- the container ladder ---------------------------------------------------


def fake_linear_for(
    *, existing: AbstractSet[str] = frozenset(), projects: list[dict[str, Any]] | None = None
):
    """A `linear` stub: `project view` succeeds only for ids in `existing`.

    Strict about flags on purpose. The real `project view` has no --json and
    exits 2 when given one, which reads every live container as missing; a
    permissive stub let that ship past a green suite once already.
    """

    def call(args: list[str]) -> str:
        if args[0] == "project" and args[1] == "view":
            unknown = [arg for arg in args[3:] if arg.startswith("-")]
            if unknown:
                raise tracker.LinearError(f'Unknown option "{unknown[0]}"')
            if args[2] not in existing:
                raise tracker.LinearError("Could not find referenced Project")
            return "# Some Project\n"
        if args[0] == "api":
            return json.dumps({"data": {"projects": {"nodes": projects or []}}})
        raise AssertionError(f"unexpected call: {args}")

    return call


def test_container_exists_passes_no_unsupported_flags() -> None:
    """Pins the exact argv: `project view` rejects --json, and a rejected flag
    is indistinguishable from a missing project at the exit-code level."""
    seen: list[list[str]] = []

    def record(args: list[str]) -> str:
        seen.append(args)
        return "# Some Project\n"

    assert tracker.container_exists("c-1", record) is True
    assert seen == [["project", "view", "c-1"]]


def project(name: str, project_id: str, slug: str | None = None) -> dict[str, Any]:
    content = f"<!-- knack-spec: deep-neuronmorpho/{slug} -->" if slug else ""
    return {"id": project_id, "name": name, "description": "", "content": content}


def test_frontmatter_wins_when_the_container_resolves(tmp_path: Path) -> None:
    path = write_spec(tmp_path)
    tracker.set_container(path, "c-1")

    code, container_id, _ = tracker.resolve_container(
        path, fake_linear_for(existing={"c-1"})
    )

    assert (code, container_id) == (tracker.EXIT_OK, "c-1")


def test_a_recorded_container_that_vanished_is_a_broken_link_not_a_missing_one(
    tmp_path: Path,
) -> None:
    """The distinction that prevents duplicate projects: the caller may create a
    container on EXIT_NO_CONTAINER, so a dangling link must never return it."""
    path = write_spec(tmp_path)
    tracker.set_container(path, "c-gone")

    code, container_id, message = tracker.resolve_container(
        path, fake_linear_for(existing=set())
    )

    assert code == tracker.EXIT_BROKEN_LINK
    assert code != tracker.EXIT_NO_CONTAINER
    assert container_id is None
    assert "refusing to create a second container" in message


def test_the_legacy_marker_resolves_when_frontmatter_is_absent(tmp_path: Path) -> None:
    path = write_spec(tmp_path)
    linear = fake_linear_for(
        projects=[
            project("Morphometric Baselines", "c-legacy", "morphometric-baselines"),
            project("Unrelated", "c-other", "something-else"),
        ]
    )

    code, container_id, message = tracker.resolve_container(path, linear)

    assert (code, container_id) == (tracker.EXIT_OK, "c-legacy")
    assert "needs backfill" in message


def test_two_legacy_matches_stop_rather_than_guessing(tmp_path: Path) -> None:
    path = write_spec(tmp_path)
    linear = fake_linear_for(
        projects=[
            project("First", "c-1", "morphometric-baselines"),
            project("Duplicate", "c-2", "morphometric-baselines"),
        ]
    )

    code, container_id, message = tracker.resolve_container(path, linear)

    assert code == tracker.EXIT_BROKEN_LINK
    assert container_id is None
    assert "c-1" in message and "c-2" in message


def test_no_container_anywhere_is_its_own_exit_code(tmp_path: Path) -> None:
    path = write_spec(tmp_path)

    code, container_id, _ = tracker.resolve_container(
        path, fake_linear_for(projects=[])
    )

    assert (code, container_id) == (tracker.EXIT_NO_CONTAINER, None)


# ---- the sweep --------------------------------------------------------------


def test_dry_run_reports_the_mapping_without_touching_the_specs(tmp_path: Path) -> None:
    first = write_spec(tmp_path)
    second = write_spec(tmp_path, "0003-other-thing.md")
    linear = fake_linear_for(
        projects=[project("Morphometric", "c-legacy", "morphometric-baselines")]
    )
    before = {p.name: p.read_text() for p in (first, second)}

    count, report = tracker.backfill_all(tmp_path, dry_run=True, run_linear_fn=linear)

    assert count == 1
    assert any("would link" in line and "c-legacy" in line for line in report)
    assert any("0003-other-thing.md: no container" in line for line in report)
    assert {p.name: p.read_text() for p in (first, second)} == before


def test_the_sweep_links_every_resolvable_spec(tmp_path: Path) -> None:
    first = write_spec(tmp_path)
    second = write_spec(tmp_path, "0003-other-thing.md")
    linear = fake_linear_for(
        projects=[
            project("Morphometric", "c-1", "morphometric-baselines"),
            project("Other", "c-2", "other-thing"),
        ]
    )

    count, _ = tracker.backfill_all(tmp_path, dry_run=False, run_linear_fn=linear)

    assert count == 2
    assert (
        tracker.read_frontmatter_value(first.read_text(), "tracker_container") == "c-1"
    )
    assert (
        tracker.read_frontmatter_value(second.read_text(), "tracker_container") == "c-2"
    )


def test_the_sweep_is_idempotent_and_skips_linked_specs(tmp_path: Path) -> None:
    path = write_spec(tmp_path)
    linear = fake_linear_for(
        existing={"c-1"},
        projects=[project("Morphometric", "c-1", "morphometric-baselines")],
    )
    tracker.backfill_all(tmp_path, dry_run=False, run_linear_fn=linear)

    count, report = tracker.backfill_all(tmp_path, dry_run=False, run_linear_fn=linear)

    assert count == 0
    assert any("already linked" in line for line in report)
    assert path.read_text().count("tracker_container:") == 1


def test_a_broken_link_stops_that_spec_without_halting_the_sweep(
    tmp_path: Path,
) -> None:
    broken = write_spec(tmp_path)
    tracker.set_container(broken, "c-gone")
    write_spec(tmp_path, "0003-other-thing.md")
    linear = fake_linear_for(
        existing=set(), projects=[project("Other", "c-2", "other-thing")]
    )

    count, report = tracker.backfill_all(tmp_path, dry_run=False, run_linear_fn=linear)

    assert count == 1
    assert any(line.startswith("STOP") for line in report)


# ---- project status sync ----------------------------------------------------


def fake_linear_project(
    status: str, issues: list[dict[str, Any]], calls: list | None = None
):
    """A stub answering the project query, the issue query, and project update."""

    def call(args: list[str]) -> str:
        if calls is not None:
            calls.append(args)
        if args[0] == "api":
            return json.dumps(
                {
                    "data": {
                        "project": {
                            "id": "c-1",
                            "name": "Proj",
                            "status": {"type": status},
                        }
                    }
                }
            )
        if args[0] == "issue" and args[1] == "query":
            return json.dumps({"nodes": issues})
        if args[0] == "project" and args[1] == "update":
            return ""
        raise AssertionError(f"unexpected call: {args}")

    return call


def test_a_backlog_project_with_work_underway_is_promoted() -> None:
    """The drift that makes the tracker actively misleading: work merged and
    shipped while the project still reads Backlog."""
    calls: list = []
    linear = fake_linear_project(
        "backlog",
        [issue("KP-1", state="started"), issue("KP-2", state="backlog")],
        calls,
    )

    report = tracker.sync_project("c-1", dry_run=False, run_linear_fn=linear)

    assert ["project", "update", "c-1", "--status", "started"] in calls
    assert "underway but project is 'backlog'" in report[0]


def test_a_started_project_is_left_alone() -> None:
    calls: list = []
    linear = fake_linear_project("started", [issue("KP-1", state="started")], calls)

    report = tracker.sync_project("c-1", dry_run=False, run_linear_fn=linear)

    assert not [c for c in calls if c[:2] == ["project", "update"]]
    assert "is consistent with its issues" in report[0]


def test_a_backlog_project_with_no_work_started_is_left_alone() -> None:
    calls: list = []
    linear = fake_linear_project("backlog", [issue("KP-1", state="backlog")], calls)

    tracker.sync_project("c-1", dry_run=False, run_linear_fn=linear)

    assert not [c for c in calls if c[:2] == ["project", "update"]]


def test_dry_run_reports_without_writing() -> None:
    calls: list = []
    linear = fake_linear_project("backlog", [issue("KP-1", state="started")], calls)

    report = tracker.sync_project("c-1", dry_run=True, run_linear_fn=linear)

    assert not [c for c in calls if c[:2] == ["project", "update"]]
    assert "would set" in report[0]


def test_an_all_done_project_is_reported_never_auto_completed() -> None:
    """Completing a project asserts delivery; the run ends at a draft PR, so
    that call stays with a human."""
    calls: list = []
    linear = fake_linear_project(
        "started",
        [issue("KP-1", state="completed"), issue("KP-2", state="canceled")],
        calls,
    )

    report = tracker.sync_project("c-1", dry_run=False, run_linear_fn=linear)

    assert not [c for c in calls if c[:2] == ["project", "update"]]
    assert any("consider completing the project" in line for line in report)
