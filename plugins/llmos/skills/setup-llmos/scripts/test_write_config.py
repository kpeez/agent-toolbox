"""Prove write_config.py validates before writing (ADR-0001): a rejected
path must leave the config file untouched, never pointing at a non-vault."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parent / "write_config.py"
_spec = importlib.util.spec_from_file_location("write_config", MODULE_PATH)
write_config_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(write_config_module)


def make_vault(root: Path) -> Path:
    (root / ".obsidian").mkdir(parents=True)
    (root / "AGENTS.md").write_text("# fake vault\n")
    return root


def test_writes_config_for_a_valid_vault(tmp_path, monkeypatch):
    vault = make_vault(tmp_path / "vault")
    config_path = tmp_path / "config" / "config.json"
    monkeypatch.setattr(write_config_module.vault_root, "CONFIG_PATH", config_path)

    resolved = write_config_module.write_config(vault)

    assert resolved == vault.resolve()
    written = json.loads(config_path.read_text())
    assert written == {"vault_root": str(vault.resolve())}


def test_rejects_a_non_vault_and_writes_nothing(tmp_path, monkeypatch):
    not_a_vault = tmp_path / "just-a-folder"
    not_a_vault.mkdir()
    config_path = tmp_path / "config" / "config.json"
    monkeypatch.setattr(write_config_module.vault_root, "CONFIG_PATH", config_path)

    with pytest.raises(SystemExit) as exc_info:
        write_config_module.write_config(not_a_vault)

    assert "not a valid vault" in str(exc_info.value)
    assert not config_path.exists()
