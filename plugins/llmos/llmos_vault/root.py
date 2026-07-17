"""Vault-root resolution.

Resolution order for the llmOS root: $LLMOS_ROOT env var -> config file
(key "vault_root") -> fail loud. No branch derives the root from this file's
own location (ADR-0001) -- a stale or unset config fails loudly instead of
guessing. `registered_vaults` separately enumerates every vault Obsidian's
own registry knows about (llmOS + xbrain), for hooks that must recognize any
known vault, not just llmOS's.

Config and registry paths are keyword arguments with real-machine defaults,
so callers never need to guess -- and tests inject a tmp_path instead of
touching the operator's actual files.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "llmos" / "config.json"
DEFAULT_REGISTRY_PATH = (
    Path.home() / "Library" / "Application Support" / "obsidian" / "obsidian.json"
)

REPAIR_MESSAGE = (
    "llmOS vault root is not configured. Run /setup-llmos, or set it manually:\n"
    "  export LLMOS_ROOT=/path/to/your/llmos-vault"
)


def validated(path: Path) -> Path:
    """Assert `path` is a real llmOS vault; exit loudly (never fall back) if not."""
    is_vault = (
        path.exists()
        and (path / ".obsidian").is_dir()
        and (path / "AGENTS.md").is_file()
    )
    if not is_vault:
        sys.exit(
            f"llmOS root '{path}' is not a valid vault "
            f"(must exist and contain .obsidian/ and AGENTS.md).\n{REPAIR_MESSAGE}"
        )
    return path


def vault_root(config_path: Path = DEFAULT_CONFIG_PATH) -> Path:
    """Resolve the llmOS vault root: $LLMOS_ROOT -> config file -> fail loud."""
    env = os.environ.get("LLMOS_ROOT")
    if env:
        return validated(Path(env).expanduser())
    if config_path.exists():
        config = json.loads(config_path.read_text())
        if isinstance(config, dict) and "vault_root" in config:
            return validated(Path(config["vault_root"]).expanduser())
    sys.exit(REPAIR_MESSAGE)


def registered_vaults(registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[Path]:
    """Every vault root Obsidian's own registry knows about (llmOS + xbrain).

    Missing registry fails loudly -- the same never-guess stance as
    `vault_root`: open Obsidian at least once so it records its known vaults.
    """
    if not registry_path.exists():
        sys.exit(
            f"Obsidian vault registry not found at '{registry_path}'.\n"
            "Open Obsidian at least once so it records its known vaults."
        )
    registry = json.loads(registry_path.read_text())
    vaults = registry.get("vaults", {}) if isinstance(registry, dict) else {}
    return [
        Path(entry["path"]).expanduser() for entry in vaults.values() if "path" in entry
    ]
