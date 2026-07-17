"""Prove `llmos_vault.root`: the canonical llmOS root resolver (env -> config
-> fail loud, never a cwd-derived guess -- ADR-0001) plus enumeration of every
vault Obsidian's own registry knows about. Config and registry paths are
constructor arguments here, not module globals, so tests never touch the
operator's real ~/.config/llmos or ~/Library/Application Support/obsidian.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmos_vault.root import registered_vaults, resolve_vault_root, vault_root


def make_vault(root: Path) -> Path:
    """Build a minimal fake vault: a directory with .obsidian/ and AGENTS.md."""
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    return root


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("LLMOS_ROOT", raising=False)


def test_env_var_wins_over_config(tmp_path, monkeypatch):
    env_vault = make_vault(tmp_path / "env-vault")
    config_vault = make_vault(tmp_path / "config-vault")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"vault_root": str(config_vault)}))
    monkeypatch.setenv("LLMOS_ROOT", str(env_vault))

    resolved = vault_root(config_path=config_path)

    assert resolved == env_vault


def test_config_used_when_env_unset(tmp_path):
    config_vault = make_vault(tmp_path / "config-vault")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"vault_root": str(config_vault)}))

    resolved = vault_root(config_path=config_path)

    assert resolved == config_vault


def test_fails_loudly_when_unconfigured(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        vault_root(config_path=tmp_path / "missing-config.json")

    message = str(exc_info.value)
    assert "/setup-llmos" in message
    assert "LLMOS_ROOT" in message


def test_rejects_config_pointing_at_non_vault(tmp_path):
    not_a_vault = tmp_path / "just-a-folder"
    not_a_vault.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"vault_root": str(not_a_vault)}))

    with pytest.raises(SystemExit) as exc_info:
        vault_root(config_path=config_path)

    message = str(exc_info.value)
    assert "not a valid vault" in message
    assert "/setup-llmos" in message


def test_registered_vaults_enumerates_all_known_roots(tmp_path):
    llmos = tmp_path / "llmos"
    xbrain = tmp_path / "xbrain"
    llmos.mkdir()
    xbrain.mkdir()
    registry_path = tmp_path / "obsidian.json"
    registry_path.write_text(
        json.dumps(
            {
                "vaults": {
                    "abc123": {"path": str(llmos), "ts": 1},
                    "def456": {"path": str(xbrain), "ts": 2},
                }
            }
        )
    )

    roots = registered_vaults(registry_path=registry_path)

    assert set(roots) == {llmos, xbrain}


def test_registered_vaults_fails_loudly_when_registry_missing(tmp_path):
    with pytest.raises(SystemExit) as exc_info:
        registered_vaults(registry_path=tmp_path / "missing-obsidian.json")

    assert "obsidian" in str(exc_info.value).lower()


def test_resolve_vault_root_llmos_goes_through_vault_root(tmp_path):
    llmos_vault = make_vault(tmp_path / "llmos")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"vault_root": str(llmos_vault)}))

    resolved = resolve_vault_root("llmos", config_path=config_path)

    assert resolved == llmos_vault


def test_resolve_vault_root_matches_other_names_via_registry(tmp_path):
    xbrain = tmp_path / "xbrain"
    xbrain.mkdir()
    registry_path = tmp_path / "obsidian.json"
    registry_path.write_text(
        json.dumps({"vaults": {"abc123": {"path": str(xbrain), "ts": 1}}})
    )

    resolved = resolve_vault_root("xbrain", registry_path=registry_path)

    assert resolved == xbrain


def test_resolve_vault_root_fails_loudly_for_unknown_name(tmp_path):
    registry_path = tmp_path / "obsidian.json"
    registry_path.write_text(json.dumps({"vaults": {}}))

    with pytest.raises(SystemExit) as exc_info:
        resolve_vault_root("nonexistent", registry_path=registry_path)

    assert "nonexistent" in str(exc_info.value)


def test_no_location_derived_fallback():
    # Static check: the resolver must never branch on its own file location.
    import inspect

    from llmos_vault import root as root_module

    source = inspect.getsource(root_module)
    assert "__file__" not in source
