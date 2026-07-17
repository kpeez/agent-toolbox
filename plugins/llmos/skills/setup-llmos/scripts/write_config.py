#!/usr/bin/env python3
"""Validate a candidate llmOS vault root and write it to the config file.

Reuses `validated()` and `CONFIG_PATH` from the plugin's shared resolver
(../../../scripts/vault_root.py) so setup-llmos can never write a config
pointing at a non-vault (ADR-0001) -- the same check the resolver enforces
at read time.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_VAULT_ROOT_MODULE = Path(__file__).resolve().parents[3] / "scripts" / "vault_root.py"
_spec = importlib.util.spec_from_file_location("vault_root", _VAULT_ROOT_MODULE)
vault_root = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vault_root)


def write_config(candidate: Path) -> Path:
    """Validate `candidate` as a vault and write it to CONFIG_PATH. Returns the resolved root."""
    root = vault_root.validated(candidate.expanduser().resolve())
    vault_root.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    vault_root.CONFIG_PATH.write_text(json.dumps({"vault_root": str(root)}) + "\n")
    return root


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("usage: write_config.py /path/to/llmos-vault")
    root = write_config(Path(sys.argv[1]))
    print(f"wrote {vault_root.CONFIG_PATH} -> {root}")


if __name__ == "__main__":
    main()
