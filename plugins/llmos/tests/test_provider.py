"""Prove `llmos_vault.provider.detect_provider`: the one shared invoking-
provider detector (SHOULD-FIX 5), replacing the byte-identical copies that
used to live in the PostToolUse stamp hook and the CLI.
"""

from __future__ import annotations

from llmos_vault.provider import detect_provider


def test_detects_claude(monkeypatch):
    monkeypatch.delenv("CODEX_SANDBOX_NETWORK_DISABLED", raising=False)
    monkeypatch.delenv("GEMINI_CLI", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")

    assert detect_provider() == "claude"


def test_detects_codex(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("GEMINI_CLI", raising=False)
    monkeypatch.setenv("CODEX_SANDBOX_NETWORK_DISABLED", "1")

    assert detect_provider() == "codex"


def test_detects_gemini(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_SANDBOX_NETWORK_DISABLED", raising=False)
    monkeypatch.setenv("GEMINI_CLI", "1")

    assert detect_provider() == "gemini"


def test_returns_none_when_no_marker_set(monkeypatch):
    monkeypatch.delenv("CLAUDECODE", raising=False)
    monkeypatch.delenv("CODEX_SANDBOX_NETWORK_DISABLED", raising=False)
    monkeypatch.delenv("GEMINI_CLI", raising=False)

    assert detect_provider() is None
