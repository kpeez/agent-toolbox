"""Prove the llmOS vault-root resolver: env -> config -> fail loud, never a
location-derived fallback (ADR-0001)."""

from __future__ import annotations

import importlib.util
import inspect
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent.parent / "scripts" / "vault_root.py"
_spec = importlib.util.spec_from_file_location("vault_root", MODULE_PATH)
vault_root_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vault_root_module)


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
    monkeypatch.setattr(vault_root_module, "CONFIG_PATH", config_path)
    monkeypatch.setenv("LLMOS_ROOT", str(env_vault))

    resolved = vault_root_module.vault_root()

    assert resolved == env_vault


def test_config_used_when_env_unset(tmp_path, monkeypatch):
    config_vault = make_vault(tmp_path / "config-vault")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"vault_root": str(config_vault)}))
    monkeypatch.setattr(vault_root_module, "CONFIG_PATH", config_path)

    resolved = vault_root_module.vault_root()

    assert resolved == config_vault


def test_fails_loudly_when_unconfigured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        vault_root_module, "CONFIG_PATH", tmp_path / "missing-config.json"
    )

    with pytest.raises(SystemExit) as exc_info:
        vault_root_module.vault_root()

    message = str(exc_info.value)
    assert "/setup-llmos" in message
    assert "LLMOS_ROOT" in message


def test_rejects_config_pointing_at_non_vault(tmp_path, monkeypatch):
    not_a_vault = tmp_path / "just-a-folder"
    not_a_vault.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"vault_root": str(not_a_vault)}))
    monkeypatch.setattr(vault_root_module, "CONFIG_PATH", config_path)

    with pytest.raises(SystemExit) as exc_info:
        vault_root_module.vault_root()

    message = str(exc_info.value)
    assert "not a valid vault" in message
    assert "/setup-llmos" in message


def test_no_location_derived_fallback(tmp_path, monkeypatch):
    # Static check: the resolver must never branch on its own file location.
    source = inspect.getsource(vault_root_module)
    assert "__file__" not in source

    # Behavioral check: we plant the resolver copy deep inside a valid vault-shaped tree.
    # Since the planted module genuinely sits inside a vault, any location-derived fallback
    # (__file__, __spec__.origin, inspect.stack, or walk-up) would resolve successfully
    # if it existed. This ensures the test fails if such a fallback is present.
    import shutil
    import sys

    fake_vault = make_vault(tmp_path / "looks-like-a-vault")
    fake_module_path = fake_vault / "plugins" / "llmos" / "scripts" / "vault_root.py"
    fake_module_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(MODULE_PATH, fake_module_path)

    spec = importlib.util.spec_from_file_location(
        "vault_root_planted", fake_module_path
    )
    assert spec is not None
    planted_module = importlib.util.module_from_spec(spec)
    sys.modules["vault_root_planted"] = planted_module

    try:
        spec.loader.exec_module(planted_module)
        monkeypatch.delenv("LLMOS_ROOT", raising=False)
        monkeypatch.setattr(
            planted_module, "CONFIG_PATH", tmp_path / "missing-config.json"
        )
        monkeypatch.chdir(fake_vault)

        with pytest.raises(SystemExit):
            planted_module.vault_root()
    finally:
        sys.modules.pop("vault_root_planted", None)
