#!/usr/bin/env python3
"""Resolve the llmOS vault root.

Resolution order: $LLMOS_ROOT env var -> ~/.config/llmos/config.json
(key "vault_root") -> fail loud. No branch derives the root from this file's
own location (ADR-0001) -- a stale or unset config fails loudly instead of
guessing. Stdlib only: this gets imported by a PreToolUse hook that runs on
every Write/Edit, so it must stay cheap to import and cheap to fail.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "llmos" / "config.json"

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


def vault_root() -> Path:
    """Resolve the llmOS vault root: $LLMOS_ROOT -> config file -> fail loud."""
    env = os.environ.get("LLMOS_ROOT")
    if env:
        return validated(Path(env).expanduser())
    if CONFIG_PATH.exists():
        config = json.loads(CONFIG_PATH.read_text())
        if isinstance(config, dict) and "vault_root" in config:
            return validated(Path(config["vault_root"]).expanduser())
    sys.exit(REPAIR_MESSAGE)


if __name__ == "__main__":
    print(vault_root())
