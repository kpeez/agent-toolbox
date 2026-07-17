#!/usr/bin/env python3
"""Back-compat shim over `llmos_vault.root`.

The hook (`hooks/llmos_hook.py`) and the setup-llmos skill still import this
module by file path via `sys.path`/`importlib`, so it stays in place rather
than moving wholesale. The canonical implementation -- and the only place the
resolution logic itself lives -- is `llmos_vault.root`; `CONFIG_PATH` here is
re-read on every call so tests that monkeypatch this module's `CONFIG_PATH`
still change behavior.
"""

from __future__ import annotations

from pathlib import Path

from llmos_vault.root import DEFAULT_CONFIG_PATH, validated
from llmos_vault.root import vault_root as _vault_root

CONFIG_PATH = DEFAULT_CONFIG_PATH
__all__ = ["CONFIG_PATH", "validated", "vault_root"]


def vault_root() -> Path:
    """Resolve the llmOS vault root: $LLMOS_ROOT -> config file -> fail loud."""
    return _vault_root(config_path=CONFIG_PATH)


if __name__ == "__main__":
    print(vault_root())
