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
    """Assert `path` is a real llmOS vault; exit loudly (never fall back) if not.

    Use when a resolved candidate root needs a final sanity check before any
    caller trusts it -- `vault_root` runs every candidate through this rather
    than returning an unverified path.
    Do NOT use when you have not yet resolved a candidate path -- call
    `vault_root` or `resolve_vault_root`, which call this for you.

    Example output:
        PosixPath('/Users/kyle/llmOS')

    Example invocation:
        from pathlib import Path
        from llmos_vault.root import validated
        validated(Path("/Users/kyle/llmOS"))

    Args:
        path: Candidate vault root to validate.
    """
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
    """Resolve the llmOS vault root: $LLMOS_ROOT -> config file -> fail loud.

    Use when a hook or verb needs the llmOS vault specifically (never derive
    it from a file's own location or the working directory, per ADR-0001).
    Do NOT use when the vault might be xbrain or another registered vault --
    use `resolve_vault_root`, which dispatches on `--vault`.

    Example output:
        PosixPath('/Users/kyle/llmOS')

    Example invocation:
        from llmos_vault.root import vault_root
        vault_root()

    Args:
        config_path: Path to the llmos config file (real-machine default;
            tests inject a tmp_path).
    """
    env = os.environ.get("LLMOS_ROOT")
    if env:
        return validated(Path(env).expanduser())
    if config_path.exists():
        config = json.loads(config_path.read_text())
        if isinstance(config, dict) and "vault_root" in config:
            return validated(Path(config["vault_root"]).expanduser())
    sys.exit(REPAIR_MESSAGE)


def resolve_vault_root(
    vault: str,
    config_path: Path = DEFAULT_CONFIG_PATH,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> Path:
    """Resolve `--vault llmos|xbrain` to a root path: "llmos" goes through
    `vault_root`, anything else is matched by directory name against
    `registered_vaults` -- the same registry, no llmOS-specific lookup.

    Use when a CLI verb needs to turn its `--vault` argument into a root path
    -- every read/graph verb calls this once per invocation.
    Do NOT use when you specifically need the llmOS vault and want the
    ADR-0001 env-var/config resolution without the registry lookup -- call
    `vault_root` directly.

    Example output:
        PosixPath('/Users/kyle/xbrain')

    Example invocation:
        from llmos_vault.root import resolve_vault_root
        resolve_vault_root("xbrain")

    Args:
        vault: Vault name, e.g. "llmos" or "xbrain".
        config_path: Path to the llmos config file (real-machine default;
            tests inject a tmp_path).
        registry_path: Path to Obsidian's vault registry (real-machine
            default; tests inject a tmp_path).
    """
    if vault == "llmos":
        return vault_root(config_path=config_path)
    for path in registered_vaults(registry_path=registry_path):
        if path.name == vault:
            return path
    sys.exit(f"no registered vault named '{vault}'. Open it in Obsidian at least once.")


def registered_vaults(registry_path: Path = DEFAULT_REGISTRY_PATH) -> list[Path]:
    """Every vault root Obsidian's own registry knows about (llmOS + xbrain).

    Missing registry fails loudly -- the same never-guess stance as
    `vault_root`: open Obsidian at least once so it records its known vaults.

    Use when a hook or verb needs every known vault, not just llmOS -- e.g.
    the Bash guard checks a target against all of them.
    Do NOT use when you already know you want the llmOS vault specifically --
    `vault_root` is the direct, config-driven path.

    Example output:
        [PosixPath('/Users/kyle/llmOS'), PosixPath('/Users/kyle/xbrain')]

    Example invocation:
        from llmos_vault.root import registered_vaults
        registered_vaults()

    Args:
        registry_path: Path to Obsidian's vault registry (real-machine
            default; tests inject a tmp_path).
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
