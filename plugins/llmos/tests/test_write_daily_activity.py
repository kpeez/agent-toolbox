"""Prove the deterministic guarantees of write_daily_activity."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "write_daily_activity.py"
spec = importlib.util.spec_from_file_location("write_daily_activity", SCRIPT)
assert spec is not None and spec.loader is not None
wda = importlib.util.module_from_spec(spec)
sys.modules["write_daily_activity"] = wda
spec.loader.exec_module(wda)


def make_vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    for slug, extra in [
        ("alpha", "repositories:\n  - kpeez/alpha\n"),
        ("norepo", ""),
        ("archived", "repositories:\n  - kpeez/archived\n"),
    ]:
        note = root / "projects" / slug / f"{slug}.md"
        note.parent.mkdir(parents=True)
        status = "archived" if slug == "archived" else "active"
        note.write_text(
            f"---\nstatus: {status}\n{extra}---\n\n# {slug.title()} Project\n",
            encoding="utf-8",
        )
    (root / "reviews" / "daily").mkdir(parents=True)
    return root


PR = {
    "number": 7,
    "title": "Add gate",
    "body": "Adds the hash gate.",
    "url": "https://github.com/kpeez/alpha/pull/7",
    "repository": {"nameWithOwner": "kpeez/alpha"},
    "state": "merged",
}
COMMIT = {
    "sha": "abc123",
    "commit": {"message": "wire gate"},
    "repository": {"fullName": "kpeez/alpha"},
    "url": "https://github.com/kpeez/alpha/commit/abc123",
}


def gh_with_activity(args):
    if args[1] == "prs" and "--merged-at" in args:
        return [PR]
    if args[1] == "commits":
        return [COMMIT]
    return []


def fake_ok(grouped, day, opencode_bin=""):
    return "### Alpha Project\nMerged [#7](u)."


def fake_incomplete(grouped, day, opencode_bin=""):
    return "### Alpha Project\nBusy day."


def gh_silent(args):
    return []


def test_allowlist_splits_monitored_and_unseen(tmp_path):
    monitored, unseen = wda.read_projects(make_vault(tmp_path))
    assert [p.slug for p in monitored] == ["alpha"]
    assert [p.slug for p in unseen] == ["norepo"]  # archived is silently excluded


def test_day_range_tracks_dst_offset():
    assert wda.day_range(date(2026, 7, 16)).startswith("2026-07-16T00:00:00-07:00")
    assert wda.day_range(date(2026, 1, 16)).startswith("2026-01-16T00:00:00-08:00")


def test_gh_failure_is_hard(tmp_path, monkeypatch):
    def gh_404(args):
        raise wda.DigestError("gh search failed: repository not found")

    with pytest.raises(wda.DigestError, match="not found"):
        wda.process_day(date(2026, 7, 16), make_vault(tmp_path), gh=gh_404)


def test_silent_day_creates_nothing(tmp_path):
    root = make_vault(tmp_path)
    outcome = wda.process_day(date(2026, 7, 16), root, gh=gh_silent)
    assert outcome == "silent (no note created)"
    assert list((root / "reviews" / "daily").iterdir()) == []


def test_activity_creates_note_with_block_and_unseen(tmp_path, monkeypatch):
    root = make_vault(tmp_path)
    monkeypatch.setattr(wda, "summarize", fake_ok)
    assert wda.process_day(date(2026, 7, 16), root, gh=gh_with_activity) == "created"
    text = (root / "reviews" / "daily" / "2026-07-16.md").read_text()
    assert "#7" in text and wda.MARKER_START in text and wda.MARKER_END in text
    assert "Norepo Project" in text  # active-without-repo named as unseen
    assert "archived" not in text.lower()
    assert "## Thoughts" in text


def test_hash_gate_skips_model_call_and_is_byte_stable(tmp_path, monkeypatch):
    root = make_vault(tmp_path)
    calls = []

    def fake_summarize(g, d, opencode_bin=""):
        calls.append(1)
        return "### Alpha Project\nMerged [#7](u)."

    monkeypatch.setattr(wda, "summarize", fake_summarize)
    wda.process_day(date(2026, 7, 16), root, gh=gh_with_activity)
    note = root / "reviews" / "daily" / "2026-07-16.md"
    first = note.read_bytes()
    assert wda.process_day(date(2026, 7, 16), root, gh=gh_with_activity).startswith("unchanged")
    assert note.read_bytes() == first
    assert len(calls) == 1


def test_completeness_check_fails_on_omission(tmp_path, monkeypatch):
    root = make_vault(tmp_path)
    monkeypatch.setattr(wda, "summarize", fake_incomplete)
    with pytest.raises(wda.DigestError, match="omitted references: #7"):
        wda.process_day(date(2026, 7, 16), root, gh=gh_with_activity)


def test_rewrite_replaces_block_but_preserves_thoughts(tmp_path, monkeypatch):
    root = make_vault(tmp_path)
    note = root / "reviews" / "daily" / "2026-07-16.md"
    thought = "## Thoughts\n\nA hand-written, irreplaceable thought.\n"
    note.write_text(
        f"# 2026-07-16\n\n## Projects\n\n{wda.MARKER_START} hash={'0' * 64} -->\nstale\n"
        f"{wda.MARKER_END}\n\n{thought}",
        encoding="utf-8",
    )
    monkeypatch.setattr(wda, "summarize", fake_ok)
    assert wda.process_day(date(2026, 7, 16), root, gh=gh_with_activity) == "updated"
    text = note.read_text()
    assert "stale" not in text and "#7" in text
    assert thought in text  # byte-for-byte outside the markers


def test_unmapped_repo_activity_is_hard_failure(tmp_path):
    rogue = dict(PR, repository={"nameWithOwner": "kpeez/dotfiles"})

    def gh_rogue(args):
        return [rogue] if args[1] == "prs" and "--merged-at" in args else []

    with pytest.raises(wda.DigestError, match="unmapped repo"):
        wda.process_day(date(2026, 7, 16), make_vault(tmp_path), gh=gh_rogue)


def opencode_text_event(text: str) -> str:
    return json.dumps(
        {
            "type": "text",
            "part": {
                "type": "text",
                "text": text,
                "metadata": {"openai": {"phase": "final_answer"}},
            },
        }
    )


def summarize_grouped() -> dict:
    return {
        "alpha": {
            "title": "Alpha Project",
            "repos": {"kpeez/alpha": {"merged_prs": [PR]}},
        }
    }


def test_summarize_uses_pinned_opencode_argv_and_stdin(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(
            returncode=0, stdout=opencode_text_event("### Alpha Project"), stderr=""
        )

    monkeypatch.setattr(wda.subprocess, "run", fake_run)
    assert wda.summarize(
        summarize_grouped(), date(2026, 7, 16), opencode_bin="/bin/opencode"
    ) == "### Alpha Project"

    assert len(calls) == 1
    argv, kwargs = calls[0]
    assert argv == [
        "/bin/opencode", "run", "--format", "json", "--model", "opencode-go/deepseek-v4-flash"
    ]
    assert kwargs["input"].startswith(wda.TRANSFORM_INSTRUCTIONS + "\n\n")
    assert json.loads(kwargs["input"].rsplit("\n\n", 1)[1]) == summarize_grouped()
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True
    assert kwargs["timeout"] == 600


def test_summarize_extracts_one_final_assistant_text(monkeypatch):
    output = "\n".join(
        [
            json.dumps({"type": "step_start"}),
            opencode_text_event("  ### Alpha Project  "),
            json.dumps({"type": "step_finish"}),
        ]
    )
    monkeypatch.setattr(
        wda.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )

    assert wda.summarize(summarize_grouped(), date(2026, 7, 16)) == "### Alpha Project"


def test_summarize_accepts_deepseek_final_text_without_openai_metadata(monkeypatch):
    output = json.dumps({"type": "text", "part": {"type": "text", "text": "### Alpha Project"}})
    monkeypatch.setattr(
        wda.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )

    assert wda.summarize(summarize_grouped(), date(2026, 7, 16)) == "### Alpha Project"


@pytest.mark.parametrize(
    "output, message",
    [
        ("", "0 final assistant messages"),
        ("not json\n", "malformed JSON"),
        (opencode_text_event("   "), "empty final assistant message"),
        (
            "\n".join([opencode_text_event("one"), opencode_text_event("two")]),
            "2 final assistant messages",
        ),
        (json.dumps({"type": "message", "text": "transcript"}), "unsupported event type"),
    ],
)
def test_summarize_rejects_malformed_or_non_single_final_output(
    monkeypatch, output, message
):
    monkeypatch.setattr(
        wda.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=output, stderr=""),
    )

    with pytest.raises(wda.DigestError, match=message):
        wda.summarize(summarize_grouped(), date(2026, 7, 16))


def test_summarize_rejects_nonzero_opencode_run(monkeypatch):
    monkeypatch.setattr(
        wda.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="provider unavailable"
        ),
    )

    with pytest.raises(wda.DigestError, match="opencode run failed: provider unavailable"):
        wda.summarize(summarize_grouped(), date(2026, 7, 16))
