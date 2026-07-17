"""Prove `vault_health` aggregates vault hygiene into one report (spec
behavior 7): seeded orphans, unresolved links, schema violations, and stale
inbox items are each detected exactly once from the fixture vault. Also
covers profile gating (llmOS schema checks skip on a plain/core vault),
graceful qmd degradation with the subprocess boundary mocked, and the CLI
surface (`--json`, exit codes, `--help`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

from llmos_vault import health as health_module
from llmos_vault.health import Profile, SchemaViolation, UnresolvedLink, summary, vault_health

VAULT = Path(__file__).parent / "fixtures" / "health_vault"
TODAY = date(2026, 7, 17)


def make_health_report(profile: Profile = "llmos"):
    return vault_health(VAULT, profile=profile, today=TODAY)


def test_vault_health_reports_seeded_orphan():
    report = make_health_report()

    assert "linker" in report.orphans


def test_vault_health_reports_seeded_dead_end():
    report = make_health_report()

    assert "dead-end" in report.dead_ends


def test_vault_health_reports_unresolved_link_with_referrer():
    report = make_health_report()

    assert report.unresolved_links == [UnresolvedLink(referrer="hub", target="Missing Note")]


def test_vault_health_reports_schema_violation_llmos_profile():
    report = make_health_report()

    assert report.schema_violations == [
        SchemaViolation(path="notes/bad-status.md", message="invalid status 'not-a-real-status'")
    ]


def test_vault_health_skips_schema_violations_for_core_profile():
    report = make_health_report(profile="core")

    assert report.schema_violations == []


def test_vault_health_reports_stale_inbox_item():
    report = make_health_report()

    assert report.stale_inbox == ["inbox/stale-capture.md"]


def test_vault_health_excludes_fresh_inbox_item_from_stale():
    report = make_health_report()

    assert "inbox/fresh-capture.md" not in report.stale_inbox


def test_vault_health_is_not_clean_when_findings_exist():
    report = make_health_report()

    assert report.is_clean is False


def test_vault_health_qmd_gap_reported_when_file_missing_from_index(monkeypatch):
    indexed = {
        "AGENTS.md",
        "notes/hub.md",
        "notes/dead-end.md",
        "notes/linker.md",
        "notes/bad-status.md",
        "inbox/stale-capture.md",
        # "inbox/fresh-capture.md" deliberately missing from the qmd index
    }
    monkeypatch.setattr(health_module, "_qmd_indexed_paths", lambda collection: indexed)

    report = make_health_report()

    assert report.qmd_gaps == ["inbox/fresh-capture.md"]
    assert report.qmd_notice is None


def test_vault_health_qmd_notice_when_qmd_unavailable(monkeypatch):
    monkeypatch.setattr(health_module, "_qmd_indexed_paths", lambda collection: None)

    report = make_health_report()

    assert report.qmd_gaps == []
    assert report.qmd_notice is not None
    assert "qmd" in report.qmd_notice.lower()


def test_qmd_indexed_paths_parses_qmd_ls_output(monkeypatch):
    """The subprocess boundary: mock `subprocess.run` itself to prove the
    `qmd ls <collection>` output parser extracts vault-relative paths."""
    fake_stdout = (
        " 4.2 KB  Jul 16 23:53  qmd://llmos/CLAUDE.md\n"
        " 1.9 KB  Jul 16 22:17  qmd://llmos/notes/alpha.md\n"
    )

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args, returncode=0, stdout=fake_stdout, stderr="")

    monkeypatch.setattr(health_module.subprocess, "run", fake_run)

    paths = health_module._qmd_indexed_paths("llmos")

    assert paths == {"CLAUDE.md", "notes/alpha.md"}


def test_qmd_indexed_paths_returns_none_when_qmd_missing(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("qmd not on PATH")

    monkeypatch.setattr(health_module.subprocess, "run", fake_run)

    assert health_module._qmd_indexed_paths("llmos") is None


def test_clean_vault_reports_no_findings(tmp_path, monkeypatch):
    root = tmp_path / "clean_vault"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "a.md").write_text(
        textwrap.dedent(
            """\
            ---
            created: 2026-07-01
            ---

            # A

            Links to [[b]].
            """
        )
    )
    (root / "notes" / "b.md").write_text(
        textwrap.dedent(
            """\
            ---
            created: 2026-07-01
            ---

            # B

            Links to [[a]].
            """
        )
    )
    monkeypatch.setattr(
        health_module, "_qmd_indexed_paths", lambda collection: {"notes/a.md", "notes/b.md"}
    )

    report = vault_health(root, profile="core", today=TODAY)

    assert report.is_clean is True


def test_summary_includes_per_section_counts():
    report = make_health_report()

    text = summary(report)

    assert "orphans (" in text
    assert "dead-ends (" in text
    assert "unresolved links (" in text
    assert "schema violations (" in text
    assert "stale inbox (" in text
    assert "qmd gaps (" in text


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["LLMOS_ROOT"] = str(VAULT)
    return subprocess.run(
        [sys.executable, "-m", "llmos_vault.cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_health_help_renders_flag_from_docstring():
    result = run_cli("health", "--help")

    assert result.returncode == 0
    assert "--json" in result.stdout
    assert "Which registered vault to check" in result.stdout


def test_cli_health_json_emits_valid_stable_shape_and_nonzero_exit():
    result = run_cli(
        "health", "--vault", "llmos", "--json", "--qmd-collection", "no-such-collection-xyz"
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert {
        "orphans",
        "dead_ends",
        "unresolved_links",
        "schema_violations",
        "stale_inbox",
        "qmd_gaps",
        "qmd_notice",
    } <= payload.keys()
    assert "linker" in payload["orphans"]
    assert payload["unresolved_links"] == [{"referrer": "hub", "target": "Missing Note"}]


def test_cli_health_degrades_qmd_section_with_clear_notice_when_absent():
    result = run_cli(
        "health", "--vault", "llmos", "--json", "--qmd-collection", "no-such-collection-xyz"
    )

    payload = json.loads(result.stdout)

    assert payload["qmd_gaps"] == []
    assert payload["qmd_notice"] is not None


def test_cli_health_default_output_is_readable_summary():
    result = run_cli("health", "--vault", "llmos", "--qmd-collection", "no-such-collection-xyz")

    assert "orphans (" in result.stdout
    assert result.returncode == 1
