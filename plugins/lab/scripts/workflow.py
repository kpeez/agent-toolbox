#!/usr/bin/env python3
"""Forward tracked Lab operations to the operator-selected SWE interface."""

import json
import os
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--help"] or not argv:
        print("Usage: workflow.py <SWE operation> [arguments]\n"
              "Requires SWE_WORKFLOW_ENTRYPOINT: absolute path to the installed "
              "SWE workflow.py, interface version 1. No engine is bundled in Lab.\n"
              "Use capabilities to inspect the dependency; no global installation is performed.")
        return 0
    configured = os.environ.get("SWE_WORKFLOW_ENTRYPOINT", "")
    entry = Path(configured)
    if not configured or not entry.is_absolute() or not entry.is_file():
        print(json.dumps({"error": "missing_dependency", "message":
              "Tracked Lab work requires installed SWE workflow interface v1. "
              "Set SWE_WORKFLOW_ENTRYPOINT to its absolute Python entry point."}), file=sys.stderr)
        return 2
    try:
        check = subprocess.run([sys.executable, str(entry), "capabilities"],
                               capture_output=True, text=True, timeout=10, check=False)
        capabilities = json.loads(check.stdout)
        if check.returncode or capabilities.get("interface_version") != 1:
            raise ValueError("incompatible interface")
    except (OSError, subprocess.TimeoutExpired, ValueError):
        print(json.dumps({"error": "incompatible_dependency", "message":
              "The selected SWE entry point did not provide workflow interface v1."}), file=sys.stderr)
        return 2
    # An operator-supplied executable path is configuration, never tracker input.
    return subprocess.run([sys.executable, str(entry), *argv], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
