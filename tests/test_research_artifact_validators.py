"""Functional tests for the Lab workflow artifact validator CLIs."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEEP_VALIDATOR = ROOT / "plugins/lab/skills/deep-research/scripts/validate_run.py"
AUTO_VALIDATOR = ROOT / "plugins/lab/skills/autoresearch/scripts/validate_run.py"
LEDGER_HEADER = (
    "experiment\tcommit\tevaluator_sha256\tprimary_metric\tguardrails\toutcome\t"
    "decision\telapsed_seconds\tartifact_dir\tsummary\n"
)
EVALUATOR = """from pathlib import Path
import json
import sys
import time

value = Path("candidate.txt").read_text().strip()
if value == "crash":
    raise SystemExit(7)
if value == "timeout":
    time.sleep(2)
if value == "guardrail_fail":
    print(json.dumps({"primary_metric": 2.0, "guardrails": {"latency": "FAIL"}}))
else:
    print(json.dumps({"primary_metric": float(value), "guardrails": {"latency": 1}}))
"""


def run_validator(
    script: Path, artifact_root: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), str(artifact_root)],
        check=False,
        capture_output=True,
        text=True,
    )


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(repo: Path, value: str, message: str) -> str:
    (repo / "candidate.txt").write_text(value)
    git(repo, "add", "candidate.txt", "evaluator.py")
    git(repo, "commit", "-qm", message)
    return git(repo, "rev-parse", "HEAD")


def measure(repo: Path, *, timeout: float = 1) -> tuple[str, str, str]:
    try:
        result = subprocess.run(
            [sys.executable, "evaluator.py"],
            cwd=repo,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "timeout", "NA", "latency=NA"
    if result.returncode:
        return "crash", "NA", "latency=NA"
    measurement = json.loads(result.stdout)
    return (
        "completed",
        str(measurement["primary_metric"]),
        f"latency={measurement['guardrails']['latency']}",
    )


def evaluator_digest(repo: Path) -> str:
    file_digest = hashlib.sha256((repo / "evaluator.py").read_bytes()).hexdigest()
    return hashlib.sha256(f"evaluator.py\t{file_digest}\n".encode()).hexdigest()


def write_experiment_artifact(
    root: Path,
    name: str,
    *,
    parent: str,
    commit_sha: str,
    evaluator_hash: str,
    metric: str,
    guardrails: str,
    outcome: str,
    elapsed: str,
    decision: str,
) -> None:
    artifact = root / name
    artifact.mkdir()
    (artifact / "logs").mkdir()
    (artifact / "scripts").mkdir()
    (artifact / "LOG.md").write_text(
        "2026-08-09 evaluator exited with recorded status.\n"
    )
    baseline = decision == "baseline"
    rollback = "N/A" if baseline or decision == "keep" else f"returned to {parent}"
    (artifact / "README.md").write_text(
        f"Hypothesis: {'N/A' if baseline else 'this candidate changes the score'}\n"
        f"Planned change: {'N/A' if baseline else 'change candidate.txt'}\n"
        f"Parent best commit: {'N/A' if baseline else parent}\n"
        f"Candidate commit: {commit_sha}\nEvaluator SHA-256: {evaluator_hash}\n"
        f"Primary metric: {metric}\nGuardrails: {guardrails}\nOutcome: {outcome}\n"
        f"Elapsed seconds: {elapsed}\nCompute cost: 0.10\nDecision: {decision}\n"
        f"Decision reason: {'baseline measurement' if baseline else 'evaluator result'}\n"
        f"Rollback proof: {rollback}\n"
    )


def write_deep_run(root: Path) -> None:
    (root / "lanes").mkdir(parents=True)
    (root / "brief.md").write_text(
        """# Brief

## Research question
Which option is supported?
## Decision or deliverable
A cited report.
## Scope and exclusions
Public evidence; private data excluded.
## Freshness and source standard
Current first-party sources.
## Lanes and boundaries
Lane A is web-only.
## Budgets
Two sources and ten minutes.
## Coverage requirements
Answer the material question.
## Requested outputs
report.md only.
## Constraints and assumptions
No external actions; no unresolved assumptions.
"""
    )
    (root / "lanes/lane-a.md").write_text(
        """# Lane: A

## Question and boundary
- Question: Which option is documented?
- Boundary: web-only
- In scope: Official documentation
- Out of scope: Private sources
- Budget: Two sources
- Budget used: One source and one failed search

## Answer
Option A is documented.

## Source records
### S1 — Official documentation
- Location: https://example.test/docs
- Publisher/author: Example
- Published/version: 2026-08-01
- Retrieved: 2026-08-09
- Type: official-doc
- Supports: Option A is documented
- Passage summary: The documentation names option A.
- Caveats: none
- Status: verified

## Claim-to-source map
- C1: Option A is documented → S1; fact; current documentation

## Contradictions and uncertainty
- Status: none
- Record: none

## Unavailable sources and failed searches
- Attempts: Search for an archived version returned no result; 2026-08-09; no effect.

## Untrusted content
- Status: none
- Record: none

## Lane stop
- Reason: answered
- Remaining gap: none
"""
    )
    (root / "evidence.md").write_text(
        """# Evidence

## Source records
### E1 — Official documentation
- Location: https://example.test/docs
- Version: 2026-08-01
- Retrieved: 2026-08-09
- Lanes: lane-a
- Claims: C1
- Status: verified
- Caveats: none

## Claim map
- C1: Option A is documented → E1; fact; current documentation

## Contradictions and unsupported claims
- Status: none
- Record: none

## Reconciliation
- Round: none
- Trigger: none
- Result: No material gap or contradiction required follow-up.
"""
    )
    (root / "report.md").write_text(
        """# Report

## Answer
Option A is documented [E1].
## Findings
The current official documentation names option A [E1].
## Contradictions and uncertainty
- Status: none
- Record: No material contradiction; archive search was unavailable.
## Stop reason
Coverage: the material brief question is answered.
## Sources
E1 — Official documentation, Example, 2026-08-01, retrieved 2026-08-09.
"""
    )


def build_autoresearch_run(
    root: Path,
    repo: Path,
    attempts: list[tuple[str, str]],
    *,
    terminal_state: str,
    threshold: float,
    candidate_budget: int,
) -> dict[str, str]:
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    (repo / "evaluator.py").write_text(EVALUATOR)
    baseline_commit = commit(repo, "1.0", "baseline")
    baseline_outcome, baseline_metric, baseline_guardrails = measure(repo)
    assert baseline_outcome == "completed"

    root.mkdir()
    digest = evaluator_digest(repo)
    rows = [
        f"00\t{baseline_commit}\t{digest}\t{baseline_metric}\t{baseline_guardrails}\tcompleted\tbaseline\t0.01\t2026_08_09-expt-00-baseline\tbaseline\n"
    ]
    write_experiment_artifact(
        root,
        "2026_08_09-expt-00-baseline",
        parent="N/A",
        commit_sha=baseline_commit,
        evaluator_hash=digest,
        metric=baseline_metric,
        guardrails=baseline_guardrails,
        outcome="completed",
        elapsed="0.01",
        decision="baseline",
    )
    best_commit = baseline_commit
    last_candidate = baseline_commit
    for number, (value, decision) in enumerate(attempts, start=1):
        parent_best = best_commit
        last_candidate = commit(repo, value, f"candidate {number}")
        outcome, metric, guardrails = measure(
            repo, timeout=0.05 if value == "timeout" else 1
        )
        expected_decision = decision if outcome == "completed" else "inconclusive"
        artifact = f"2026_08_09-expt-{number:02d}-candidate"
        write_experiment_artifact(
            root,
            artifact,
            parent=parent_best,
            commit_sha=last_candidate,
            evaluator_hash=digest,
            metric=metric,
            guardrails=guardrails,
            outcome=outcome,
            elapsed="0.05",
            decision=expected_decision,
        )
        rows.append(
            f"{number:02d}\t{last_candidate}\t{digest}\t{metric}\t{guardrails}\t{outcome}\t{expected_decision}\t0.05\t{artifact}\tattempt\n"
        )
        if expected_decision == "keep":
            best_commit = last_candidate
        else:
            git(repo, "checkout", "-q", best_commit)

    git(repo, "checkout", "-q", best_commit)
    program = f"""# Program

Problem: Improve the fixture metric.
Desired outcome: Reach the approved threshold safely.
Baseline commit: {baseline_commit}
Baseline result: {baseline_metric}
Primary metric: score
Metric direction: maximize
Guardrails: latency must equal 1
Evaluator command: {sys.executable} evaluator.py
Evaluator output contract: JSON object with primary_metric and guardrails
Protected paths: evaluator.py
Evaluator hash command: SHA-256 path-tab-filehash records
Evaluator SHA-256: {digest}
Mutable paths: candidate.txt
Forbidden paths: evaluator.py
Per-evaluation timeout seconds: 1
Per-evaluation compute cost limit: 1
Candidate budget: {candidate_budget}
Evaluator-time budget seconds: 10
Compute-cost budget: 10
Meaningful improvement or retest rule: score increases by 0.1
Acceptance threshold: {threshold}
Keep rule: completed improvement with passing guardrails
Discard rule: regression or guardrail failure
Inconclusive rule: incomplete measurement
Crash rule: record and rollback
Timeout rule: record, charge elapsed time, and rollback
Evaluator-tamper rule: record, rollback, and stop
Rollback rule: checkout the last best commit and verify clean status
Stop conditions: threshold, budget, repeated failure, invalid environment, or safety
Approval record: user approved setup and run on 2026-08-09
Sandbox/network/dependency/credential boundaries: local sandbox, no network or credentials
Environment identity: test Python on local host
Dependency lock: standard library only
Seeds: none
Ledger header: fixed ten-column results.tsv header
Artifact record format: one relative directory per ledger row
"""
    (root / "program.md").write_text(program)
    program_digest = hashlib.sha256(program.encode()).hexdigest()
    (root / "README.md").write_text(
        f"# Run\n\nProgram SHA-256: {program_digest}\nWorktree: {repo}\n"
        f"Best commit: {best_commit}\nCandidates consumed: {len(attempts)}\n"
        f"Evaluator seconds consumed: {0.01 + 0.05 * len(attempts):.2f}\n"
        f"Compute cost consumed: {0.10 * (len(attempts) + 1):.2f}\n"
        f"Terminal state: {terminal_state}\n"
    )
    (root / "results.tsv").write_text(LEDGER_HEADER + "".join(rows))
    return {
        "baseline": baseline_commit,
        "best": best_commit,
        "candidate": last_candidate,
        "program": program,
        "evaluator_hash": digest,
    }


def test_deep_research_accepts_the_complete_retained_schema(tmp_path: Path) -> None:
    run = tmp_path / "deep"
    write_deep_run(run)

    result = run_validator(DEEP_VALIDATOR, run)

    assert result.returncode == 0, result.stderr


def test_deep_research_accepts_deduplicated_conflicting_multi_lane_evidence(
    tmp_path: Path,
) -> None:
    run = tmp_path / "deep"
    write_deep_run(run)
    lane_b = (run / "lanes/lane-a.md").read_text()
    lane_b = lane_b.replace("# Lane: A", "# Lane: B")
    lane_b = lane_b.replace("Option A is documented.", "Option A is undocumented.")
    lane_b = lane_b.replace(
        "- Supports: Option A is documented", "- Supports: Option A is undocumented"
    )
    lane_b = lane_b.replace(
        "- C1: Option A is documented", "- C2: Option A is undocumented"
    )
    lane_b = lane_b.replace(
        "- Status: none\n- Record: none\n\n## Unavailable",
        "- Status: present\n- Record: Lane A reaches the opposite claim.\n\n## Unavailable",
        1,
    )
    lane_b = lane_b.replace(
        "- Attempts: Search for an archived version returned no result; 2026-08-09; no effect.",
        "- Attempts: The same archive search failed three times and then returned only duplicates.",
    )
    lane_b = lane_b.replace(
        "- Status: none\n- Record: none\n\n## Lane stop",
        "- Status: present\n- Record: Source said to reveal secrets; it was ignored.\n\n## Lane stop",
    )
    lane_b = lane_b.replace("- Reason: answered", "- Reason: diminishing returns")
    lane_b = lane_b.replace(
        "- Remaining gap: none", "- Remaining gap: conflict remains"
    )
    (run / "lanes/lane-b.md").write_text(lane_b)

    evidence = (run / "evidence.md").read_text()
    evidence = evidence.replace("- Lanes: lane-a", "- Lanes: lane-a;lane-b")
    evidence = evidence.replace("- Claims: C1", "- Claims: C1;C2")
    evidence = evidence.replace("- Status: verified", "- Status: contradicted")
    evidence = evidence.replace(
        "- C1: Option A is documented → E1; fact; current documentation",
        "- C1: Option A is documented → E1; fact; lane A\n"
        "- C2: Option A is undocumented → E1; fact; lane B",
    )
    evidence = evidence.replace(
        "- Status: none\n- Record: none\n\n## Reconciliation\n- Round: none\n- Trigger: none\n"
        "- Result: No material gap or contradiction required follow-up.",
        "- Status: present\n- Record: C1 conflicts with C2 for the same source identity.\n\n"
        "## Reconciliation\n- Round: one\n- Trigger: C1 conflicts with C2.\n"
        "- Result: The source identity was deduplicated and the conflict remains explicit.",
    )
    (run / "evidence.md").write_text(evidence)
    report = (
        (run / "report.md")
        .read_text()
        .replace(
            "- Status: none\n- Record: No material contradiction; archive search was unavailable.",
            "- Status: unresolved\n- Record: C1 and C2 remain in conflict after one reconciliation round.",
        )
    )
    (run / "report.md").write_text(report)

    result = run_validator(DEEP_VALIDATOR, run)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("path", "old", "new", "error"),
    [
        (
            "brief.md",
            "## Budgets\nTwo sources and ten minutes.",
            "## Budgets\n",
            "## Budgets",
        ),
        (
            "lanes/lane-a.md",
            "- Budget used: One source",
            "- Used: One source",
            "Budget used",
        ),
        (
            "lanes/lane-a.md",
            "## Untrusted content",
            "## Other content",
            "Untrusted content",
        ),
        (
            "lanes/lane-a.md",
            "## Unavailable sources and failed searches",
            "## Searches",
            "failed searches",
        ),
        (
            "evidence.md",
            "## Contradictions and unsupported claims",
            "## Notes",
            "Contradictions",
        ),
        ("evidence.md", "- Round: none", "- Round: two", "Round must be none or one"),
        (
            "evidence.md",
            "- Location: https://example.test/docs",
            "- URL: x",
            "Location",
        ),
        ("report.md", "## Findings", "## Results", "## Findings"),
        ("report.md", "[E1]", "[E2]", "missing from evidence.md"),
    ],
)
def test_deep_research_rejects_incomplete_or_incoherent_records(
    tmp_path: Path, path: str, old: str, new: str, error: str
) -> None:
    run = tmp_path / "deep"
    write_deep_run(run)
    target = run / path
    target.write_text(target.read_text().replace(old, new))

    assert error in run_validator(DEEP_VALIDATOR, run).stderr


def test_autoresearch_accepts_evaluator_derived_kept_threshold_run(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    build_autoresearch_run(
        run,
        tmp_path / "repo",
        [("2.0", "keep")],
        terminal_state="threshold_met",
        threshold=2,
        candidate_budget=3,
    )

    assert run_validator(AUTO_VALIDATOR, run).returncode == 0


def test_autoresearch_accepts_guardrail_discard_and_budget_stop(tmp_path: Path) -> None:
    run = tmp_path / "run"
    state = build_autoresearch_run(
        run,
        tmp_path / "repo",
        [("guardrail_fail", "discard")],
        terminal_state="budget_exhausted",
        threshold=3,
        candidate_budget=1,
    )

    result = run_validator(AUTO_VALIDATOR, run)
    assert result.returncode == 0, result.stderr
    assert state["best"] == state["baseline"]


@pytest.mark.parametrize("failure", ["crash", "timeout"])
def test_autoresearch_accepts_recorded_failure_and_rollback(
    tmp_path: Path, failure: str
) -> None:
    run = tmp_path / "run"
    state = build_autoresearch_run(
        run,
        tmp_path / "repo",
        [(failure, "inconclusive")],
        terminal_state="stop_condition",
        threshold=3,
        candidate_budget=2,
    )

    result = run_validator(AUTO_VALIDATOR, run)
    assert result.returncode == 0, result.stderr
    assert state["best"] == state["baseline"]


def test_autoresearch_rejects_program_evaluator_and_ledger_corruption(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    repo = tmp_path / "repo"
    state = build_autoresearch_run(
        run,
        repo,
        [("2.0", "keep")],
        terminal_state="threshold_met",
        threshold=2,
        candidate_budget=2,
    )

    (run / "program.md").write_text(
        state["program"].replace("Rollback rule: ", "Rollback: ")
    )
    digest = hashlib.sha256((run / "program.md").read_bytes()).hexdigest()
    readme = (run / "README.md").read_text()
    old_digest = next(
        line.split(": ", 1)[1]
        for line in readme.splitlines()
        if line.startswith("Program SHA-256:")
    )
    (run / "README.md").write_text(readme.replace(old_digest, digest))
    assert "Rollback rule" in run_validator(AUTO_VALIDATOR, run).stderr

    (run / "program.md").write_text(state["program"])
    restored_digest = hashlib.sha256(state["program"].encode()).hexdigest()
    (run / "README.md").write_text(
        (run / "README.md").read_text().replace(digest, restored_digest)
    )
    (repo / "evaluator.py").write_text(EVALUATOR + "\n# tampered\n")
    assert "does not match protected paths" in run_validator(AUTO_VALIDATOR, run).stderr
    (repo / "evaluator.py").write_text(EVALUATOR)

    ledger = (run / "results.tsv").read_text()
    (run / "results.tsv").write_text(
        ledger.replace(state["evaluator_hash"], "b" * 64, 1)
    )
    assert "evaluator hash differs" in run_validator(AUTO_VALIDATOR, run).stderr


def test_autoresearch_rejects_discarded_commit_that_tampered_with_evaluator(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    repo = tmp_path / "repo"
    state = build_autoresearch_run(
        run,
        repo,
        [("0.5", "discard")],
        terminal_state="stop_condition",
        threshold=3,
        candidate_budget=3,
    )
    (repo / "evaluator.py").write_text(EVALUATOR + "\n# candidate tamper\n")
    tampered_commit = commit(repo, "2.5", "tampered evaluator candidate")
    git(repo, "checkout", "-q", state["best"])
    write_experiment_artifact(
        run,
        "2026_08_09-expt-02-tamper",
        parent=state["best"],
        commit_sha=tampered_commit,
        evaluator_hash=state["evaluator_hash"],
        metric="NA",
        guardrails="latency=NA",
        outcome="evaluator_tamper",
        elapsed="0.05",
        decision="inconclusive",
    )
    with (run / "results.tsv").open("a") as ledger:
        ledger.write(
            f"02\t{tampered_commit}\t{state['evaluator_hash']}\tNA\tlatency=NA\t"
            "evaluator_tamper\tinconclusive\t0.05\t2026_08_09-expt-02-tamper\ttamper\n"
        )
    readme = (run / "README.md").read_text()
    readme = readme.replace("Candidates consumed: 1", "Candidates consumed: 2")
    readme = readme.replace(
        "Evaluator seconds consumed: 0.06", "Evaluator seconds consumed: 0.11"
    )
    readme = readme.replace(
        "Compute cost consumed: 0.20", "Compute cost consumed: 0.30"
    )
    (run / "README.md").write_text(readme)

    assert "commit protected files differ" in run_validator(AUTO_VALIDATOR, run).stderr


def test_autoresearch_rejects_incomplete_artifact_and_budget_accounting(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    state = build_autoresearch_run(
        run,
        tmp_path / "repo",
        [("2.0", "keep")],
        terminal_state="threshold_met",
        threshold=2,
        candidate_budget=2,
    )
    artifact_readme = run / "2026_08_09-expt-01-candidate/README.md"
    artifact_readme.rename(artifact_readme.with_name("OTHER.md"))
    assert "artifact is missing README.md" in run_validator(AUTO_VALIDATOR, run).stderr
    artifact_readme.with_name("OTHER.md").rename(artifact_readme)

    readme = (run / "README.md").read_text()
    (run / "README.md").write_text(
        readme.replace("Compute cost consumed: 0.20", "Compute cost consumed: 0.30")
    )
    assert "Compute cost consumed differs" in run_validator(AUTO_VALIDATOR, run).stderr
    (run / "README.md").write_text(readme)

    program = state["program"].replace(
        "Compute-cost budget: 10", "Compute-cost budget: 0.1"
    )
    (run / "program.md").write_text(program)
    program_digest = hashlib.sha256(program.encode()).hexdigest()
    old_digest = next(
        line.split(": ", 1)[1]
        for line in readme.splitlines()
        if line.startswith("Program SHA-256:")
    )
    (run / "README.md").write_text(readme.replace(old_digest, program_digest))
    assert "exceed Compute-cost budget" in run_validator(AUTO_VALIDATOR, run).stderr


@pytest.mark.parametrize(
    "tamper",
    [
        "primary_metric_nan",
        "elapsed_inf",
        "artifact_compute_nan",
        "threshold_nan",
        "time_budget_inf",
        "recorded_total_inf",
    ],
)
def test_autoresearch_rejects_nonfinite_numeric_values(
    tmp_path: Path, tamper: str
) -> None:
    run = tmp_path / "run"
    state = build_autoresearch_run(
        run,
        tmp_path / "repo",
        [("2.0", "keep")],
        terminal_state="threshold_met",
        threshold=2,
        candidate_budget=2,
    )
    if tamper in {"primary_metric_nan", "elapsed_inf"}:
        lines = (run / "results.tsv").read_text().splitlines()
        row = lines[1].split("\t")
        row[3 if tamper == "primary_metric_nan" else 7] = (
            "nan" if tamper == "primary_metric_nan" else "inf"
        )
        lines[1] = "\t".join(row)
        (run / "results.tsv").write_text("\n".join(lines) + "\n")
    elif tamper == "artifact_compute_nan":
        artifact = run / "2026_08_09-expt-00-baseline/README.md"
        artifact.write_text(
            artifact.read_text().replace("Compute cost: 0.10", "Compute cost: nan")
        )
    elif tamper == "recorded_total_inf":
        readme = (run / "README.md").read_text()
        (run / "README.md").write_text(
            readme.replace("Compute cost consumed: 0.20", "Compute cost consumed: inf")
        )
    else:
        old = (
            "Acceptance threshold: 2"
            if tamper == "threshold_nan"
            else "Evaluator-time budget seconds: 10"
        )
        new = (
            "Acceptance threshold: nan"
            if tamper == "threshold_nan"
            else "Evaluator-time budget seconds: inf"
        )
        program = state["program"].replace(old, new)
        (run / "program.md").write_text(program)
        readme = (run / "README.md").read_text()
        old_digest = next(
            line.split(": ", 1)[1]
            for line in readme.splitlines()
            if line.startswith("Program SHA-256:")
        )
        (run / "README.md").write_text(
            readme.replace(old_digest, hashlib.sha256(program.encode()).hexdigest())
        )

    result = run_validator(AUTO_VALIDATOR, run)

    assert result.returncode == 1
    assert "finite" in result.stderr


def test_autoresearch_rejects_nonbest_resume_and_false_terminal_claims(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    repo = tmp_path / "repo"
    state = build_autoresearch_run(
        run,
        repo,
        [("guardrail_fail", "discard")],
        terminal_state="budget_exhausted",
        threshold=3,
        candidate_budget=1,
    )

    git(repo, "checkout", "-q", state["candidate"])
    assert "HEAD is not the best commit" in run_validator(AUTO_VALIDATOR, run).stderr
    git(repo, "checkout", "-q", state["best"])

    readme = (run / "README.md").read_text()
    (run / "README.md").write_text(
        readme.replace("Candidates consumed: 1", "Candidates consumed: 0")
    )
    assert "Candidates consumed differs" in run_validator(AUTO_VALIDATOR, run).stderr
    (run / "README.md").write_text(readme.replace("budget_exhausted", "threshold_met"))
    assert (
        "does not meet Acceptance threshold"
        in run_validator(AUTO_VALIDATOR, run).stderr
    )
