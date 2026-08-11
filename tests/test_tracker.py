"""Behavior tests for plugins/swe/scripts/tracker.py.

Every Linear and git call is injected, so these drive the policy with scripted
CLI output and assert on what survives the filter and how the container ladder
resolves.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from collections.abc import Set as AbstractSet
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins" / "swe" / "scripts" / "tracker.py"

spec = importlib.util.spec_from_file_location("tracker", SCRIPT)
assert spec and spec.loader
tracker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracker)


def test_linear_backend_implements_tracker_protocol_and_wraps_issue_query() -> None:
    calls: list[list[str]] = []
    expected = issue("KP-1")

    def fake_linear(args: list[str]) -> str:
        calls.append(args)
        return json.dumps({"nodes": [expected]})

    backend = tracker.LinearBackend(fake_linear)

    assert isinstance(backend, tracker.TrackerBackend)
    assert backend.fetch_container_issues("container-1") == [expected]
    assert calls == [
        [
            "issue",
            "query",
            "--project",
            "container-1",
            "--all-teams",
            "--json",
            "--no-pager",
        ]
    ]


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
        "title": f"task {identifier}",
        "state": {"type": state},
        "labels": {"nodes": [{"name": name} for name in labels or []]},
        "inverseRelations": {"nodes": relations},
    }


def run(
    *issues: dict[str, Any],
    merged: list[str] | None = None,
    base: str | None = "base",
    stack_branches: list[str] | None = None,
) -> list[str]:
    """Identifiers reported workable, given `merged` task branches on the run's
    tip — the highest of `stack_branches` when any exist, else `base`."""

    def fake_linear(args: list[str]) -> str:
        return json.dumps({"nodes": list(issues)})

    def fake_git(args: list[str]) -> str:
        if args[:3] == ["branch", "--list", "stack/*"]:
            return "\n".join(stack_branches or [])
        assert args[:2] == ["branch", "--merged"]
        expected_tip = stack_branches[-1] if stack_branches else base
        assert args[2] == expected_tip, f"merged check ran against {args[2]}"
        return "\n".join([f"change/{name}" for name in merged or []] + ["main"])

    result = tracker.workable_issues(
        "container-1", base, run_linear_fn=fake_linear, run_git_fn=fake_git
    )
    return [entry["identifier"] for entry in result]


# ---- git is the authority on "already merged in this run" -------------------


def test_a_merged_slice_is_dropped_from_the_frontier() -> None:
    assert run(issue("KP-1"), issue("KP-2"), merged=["KP-1"]) == ["KP-2"]


def test_a_merged_blocker_unblocks_its_dependent() -> None:
    """The stall both observed multi-task runs hit: a merged task keeps its
    open tracker state until the PR lands, so judging blockers by state alone
    strands every dependent task."""
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


def test_without_a_base_branch_nothing_counts_as_merged() -> None:
    assert run(issue("KP-1"), base=None) == ["KP-1"]


# ---- stacked runs judge "merged" against the stack tip, not the base --------


def test_a_blocker_merged_mid_stack_unblocks_its_dependent() -> None:
    """The two-slice stall: mid-stack, changesets merge onto stack/<n> branches
    and never back into the base branch, so a base-branch merge check reads
    every later changeset as unmerged and drains the frontier. The run() fake
    asserts the merge check runs against stack/3 here, not `base`."""
    blocker = issue("KP-1")
    dependent = issue("KP-2", blocked_by=[blocker])
    assert run(
        blocker, dependent, merged=["KP-1"], stack_branches=["stack/2", "stack/3"]
    ) == ["KP-2"]


def test_stack_tip_is_the_highest_numbered_stack_branch() -> None:
    def fake_git(args: list[str]) -> str:
        assert args[:3] == ["branch", "--list", "stack/*"]
        return "stack/2\nstack/10\nstack/3\n"

    assert tracker.stack_tip("base", fake_git) == "stack/10"


def test_stack_tip_ignores_non_numbered_stack_branches() -> None:
    """A stray stack/wip must not shadow the base branch or break int()."""

    def fake_git(args: list[str]) -> str:
        assert args[:3] == ["branch", "--list", "stack/*"]
        return "stack/wip\n"

    assert tracker.stack_tip("base", fake_git) == "base"


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


# ---- the container ladder ---------------------------------------------------


def fake_linear_for(
    *,
    existing: AbstractSet[str] = frozenset(),
    projects: list[dict[str, Any]] | None = None,
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


def test_no_container_anywhere_is_its_own_exit_code(tmp_path: Path) -> None:
    path = write_spec(tmp_path)

    code, container_id, _ = tracker.resolve_container(
        path, fake_linear_for(projects=[])
    )

    assert (code, container_id) == (tracker.EXIT_NO_CONTAINER, None)


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


# ---- end-of-run reconcile ---------------------------------------------------


def reconcile(
    *issues: dict[str, Any],
    merged: list[str] | None = None,
    dry_run: bool = False,
) -> tuple[list[str], list]:
    calls: list = []

    def fake_linear(args: list[str]) -> str:
        calls.append(args)
        return json.dumps({"nodes": list(issues)})

    def fake_git(args: list[str]) -> str:
        return "\n".join([f"change/{name}" for name in merged or []] + ["main"])

    report = tracker.reconcile_issues(
        "c-1", "base", dry_run=dry_run, run_linear_fn=fake_linear, run_git_fn=fake_git
    )
    return report, calls


def test_a_merged_issue_left_behind_by_a_failed_write_is_promoted() -> None:
    """The observed drift: the task merged, the run's own state write did not
    land, and nothing else ever repaired it."""
    report, calls = reconcile(issue("KP-1", state="unstarted"), merged=["KP-1"])

    assert ["issue", "update", "KP-1", "--state", "In Review"] in calls
    assert "merged into base but reads 'unstarted'" in report[0]


def test_an_unmerged_issue_is_never_touched() -> None:
    """An escalated task has a branch and no merge. Moving it would assert work
    is underway that nobody is doing."""
    report, calls = reconcile(
        issue("KP-1", state="unstarted"),
        issue("KP-2", state="unstarted"),
        merged=["KP-1"],
    )

    assert [c for c in calls if c[:2] == ["issue", "update"]] == [
        ["issue", "update", "KP-1", "--state", "In Review"]
    ]
    assert not any("KP-2" in line for line in report)


def test_an_issue_already_underway_is_left_alone() -> None:
    """Nothing moves an issue to a started state except its merge, so a started
    issue has already been promoted and rewriting it is a wasted call."""
    report, calls = reconcile(issue("KP-1", state="started"), merged=["KP-1"])

    assert not [c for c in calls if c[:2] == ["issue", "update"]]
    assert "already reads as underway" in report[0]


def test_a_closed_issue_is_never_reopened() -> None:
    report, calls = reconcile(issue("KP-1", state="completed"), merged=["KP-1"])

    assert not [c for c in calls if c[:2] == ["issue", "update"]]


def test_a_run_that_merged_nothing_reconciles_nothing() -> None:
    """A run that died before its first merge must not read as work underway."""
    report, calls = reconcile(issue("KP-1", state="unstarted"), merged=[])

    assert calls == []
    assert "nothing merged into base" in report[0]


def test_a_changeset_branch_promotes_every_task_it_carries() -> None:
    """One branch carries a whole changeset, so every identifier in its name is
    merged — matching only change/<identifier> under-reports what landed."""
    report, calls = reconcile(
        issue("KP-1", state="unstarted"),
        issue("KP-2", state="unstarted"),
        merged=["KP-1-KP-2-auth"],
    )

    updated = [c[2] for c in calls if c[:2] == ["issue", "update"]]
    assert updated == ["KP-1", "KP-2"]


def test_dry_run_reports_without_writing() -> None:
    report, calls = reconcile(
        issue("KP-1", state="unstarted"), merged=["KP-1"], dry_run=True
    )

    assert not [c for c in calls if c[:2] == ["issue", "update"]]
    assert "would set" in report[0]


class MockTrackerBackend:
    def __init__(self) -> None:
        self.updated: list[tuple[str, str]] = []

    def fetch_container_issues(self, container_id: str) -> list[dict]:
        return []

    def container_exists(self, container_id: str) -> bool:
        return True

    def project_status(self, container_id: str) -> tuple[str, str]:
        return container_id, "started"

    def update_issue(self, identifier: str, state: str) -> None:
        self.updated.append((identifier, state))

    def update_project(self, container_id: str, status: str) -> None:
        return None


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def task_repo(
    tmp_path: Path, *, third: bool = False, conflict: bool = True
) -> tuple[Path, list[dict]]:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "value.txt").write_text("base\n")
    git(repo, "add", "value.txt")
    git(repo, "commit", "-m", "base")

    def branch(name: str, value: str) -> None:
        git(repo, "checkout", "-b", name, "main")
        path = (
            repo / "value.txt"
            if conflict and not (third and name == "change/KP-3")
            else repo / f"{name.replace('/', '-')}.txt"
        )
        path.write_text(value)
        git(repo, "add", path.name)
        git(repo, "commit", "-m", name)
        git(repo, "checkout", "main")

    branch("change/KP-1", "first\n")
    branch("change/KP-2", "second\n")
    if third:
        branch("change/KP-3", "third\n")
    plan = [
        {
            "branch": "change/KP-1",
            "from": "main",
            "target": "main",
            "issues": [{"identifier": "KP-1"}],
        },
        {
            "branch": "change/KP-2",
            "from": "main",
            "target": "stack/2",
            "issues": [{"identifier": "KP-2"}],
        },
    ]
    if third:
        plan.append(
            {
                "branch": "change/KP-3",
                "from": "main",
                "target": "stack/3",
                "issues": [{"identifier": "KP-3"}],
            }
        )
    return repo, plan


def test_settle_merges_plan_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, plan = task_repo(tmp_path, conflict=False)
    monkeypatch.chdir(repo)
    backend = MockTrackerBackend()

    code, payload = tracker.settle_plan(plan, backend=backend)

    assert code == tracker.EXIT_OK
    assert [entry["identifier"] for entry in payload["results"]] == ["KP-1", "KP-2"]
    assert backend.updated == [("KP-1", tracker.MERGED_STATE), ("KP-2", tracker.MERGED_STATE)]
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "stack/2"


def test_settle_stops_in_place_on_conflict(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo, plan = task_repo(tmp_path)
    monkeypatch.chdir(repo)

    code, payload = tracker.settle_plan(plan, backend=MockTrackerBackend())

    assert code == tracker.EXIT_CONFLICT
    assert payload["conflict"]["target"] == "stack/2"
    assert payload["conflict"]["files"] == ["value.txt"]
    assert "UU value.txt" in git(repo, "status", "--short")


def test_settle_continue_completes_interrupted_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, plan = task_repo(tmp_path)
    monkeypatch.chdir(repo)
    backend = MockTrackerBackend()
    tracker.settle_plan(plan, backend=backend)
    (repo / "value.txt").write_text("resolved\n")

    code, payload = tracker.continue_settle(backend=backend)

    assert code == tracker.EXIT_OK
    assert [entry["identifier"] for entry in payload["results"]] == ["KP-1", "KP-2"]
    assert backend.updated[-1] == ("KP-2", tracker.MERGED_STATE)
    assert git(repo, "status", "--short") == ""


def test_settle_skip_restacks_downstream_targets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, plan = task_repo(tmp_path, third=True)
    monkeypatch.chdir(repo)
    backend = MockTrackerBackend()
    tracker.settle_plan(plan, backend=backend)

    code, payload = tracker.skip_settle("change/KP-2", backend=backend)

    assert code == tracker.EXIT_OK
    skipped = next(entry for entry in payload["results"] if entry["identifier"] == "KP-2")
    landed = next(entry for entry in payload["results"] if entry["identifier"] == "KP-3")
    assert skipped["merged"] is False
    assert landed["stackBranch"] == "stack/2"
    assert git(repo, "show", "stack/2:change-KP-3.txt") == "third"


def test_settle_rerun_is_idempotent_from_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, plan = task_repo(tmp_path, third=True)
    monkeypatch.chdir(repo)
    backend = MockTrackerBackend()
    assert tracker.settle_plan(plan, backend=backend)[0] == tracker.EXIT_CONFLICT
    (repo / "value.txt").write_text("resolved\n")
    assert tracker.continue_settle(backend=backend)[0] == tracker.EXIT_OK
    first_main = git(repo, "rev-parse", "main")
    first_stack = git(repo, "rev-parse", "stack/2")

    code, _ = tracker.settle_plan(plan, backend=backend)

    assert code == tracker.EXIT_OK
    assert git(repo, "rev-parse", "main") == first_main
    assert git(repo, "rev-parse", "stack/2") == first_stack


def test_github_workable_parses_blocked_by_sections() -> None:
    payload = [
        {
            "number": 11,
            "title": "dependent",
            "body": "## Blocked by\n- #10\n\n## Acceptance criteria\n- works",
            "labels": [],
            "state": "OPEN",
            "comments": [],
        },
        {
            "number": 10,
            "title": "blocker",
            "body": "",
            "labels": [],
            "state": "CLOSED",
            "comments": [],
        },
    ]
    backend = tracker.GithubBackend(lambda args: json.dumps(payload))

    result = tracker.workable_issues("99", backend=backend)

    assert [entry["identifier"] for entry in result] == ["#11"]
    assert result[0]["changeset"] == ""


def test_github_workable_drains_a_merged_task_off_the_frontier() -> None:
    """`change/#11-...` merged into the run's stack tip must be recognised as
    done, the same as a Linear `change/KP-1` branch. Regression for the
    `#<number>`-shaped identifier never matching IDENTIFIER_RE."""
    payload = [
        {
            "number": 11,
            "title": "task",
            "body": "",
            "labels": [],
            "state": "OPEN",
            "comments": [],
        }
    ]
    backend = tracker.GithubBackend(lambda args: json.dumps(payload))

    def fake_git(args: list[str]) -> str:
        if args[:3] == ["branch", "--list", "stack/*"]:
            return ""
        assert args[:2] == ["branch", "--merged"]
        assert args[2] == "base"
        return "change/#11-task\nmain"

    result = tracker.workable_issues(
        "99", "base", run_git_fn=fake_git, backend=backend
    )

    assert result == []


def test_github_blocked_by_section_with_no_recognized_shape_raises() -> None:
    """A '## Blocked by' section that names blockers in prose neither `#<n>`
    nor 'None' must fail loudly, not silently report the issue workable."""
    payload = [
        {
            "number": 12,
            "title": "dependent",
            "body": "## Blocked by\n- the auth work\n\n## Acceptance criteria\n- works",
            "labels": [],
            "state": "OPEN",
            "comments": [],
        }
    ]
    backend = tracker.GithubBackend(lambda args: json.dumps(payload))

    with pytest.raises(tracker.TrackerError, match="#12"):
        tracker.workable_issues("99", backend=backend)


def test_github_state_write_flips_labels() -> None:
    calls: list[list[str]] = []

    def run_gh(args: list[str]) -> str:
        calls.append(args)
        return ""

    tracker.GithubBackend(run_gh).update_issue("#11", "In Review")

    assert calls == [
        [
            "issue",
            "edit",
            "11",
            "--add-label",
            "in-review",
            "--remove-label",
            "in-progress",
        ],
        ["issue", "comment", "11", "--body", "swe-loop: state changed to in-review"],
    ]
