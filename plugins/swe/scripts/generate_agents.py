#!/usr/bin/env python3
"""Generate the SWE plugin's provider adapters from roles.json."""

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ROLES_PATH = PLUGIN_ROOT / "roles.json"
AGENTS_ROOT = PLUGIN_ROOT / "agents"


def load_roles() -> dict[str, dict[str, Any]]:
    data = json.loads(ROLES_PATH.read_text())
    roles = data.get("roles")
    if not isinstance(roles, dict):
        raise ValueError("roles.json must contain a roles object")
    return roles


def role_body(role: dict[str, Any]) -> str:
    body = (PLUGIN_ROOT / role["body"]).read_text()
    return body.rstrip() + "\n"


def render_frontmatter(name: str, role: dict[str, Any]) -> str:
    claude = role["claude"]
    lines = ["---", f"name: {name}", f"description: {role['description']}"]
    for key in ("model", "effort"):
        if key in claude:
            lines.append(f"{key}: {claude[key]}")
    if "tools" in claude:
        lines.append(f"tools: {', '.join(claude['tools'])}")
    lines.extend(["---", "", role_body(role)])
    return "\n".join(lines)


def render_toml(name: str, role: dict[str, Any]) -> str:
    codex = role["codex"]
    lines = [
        f"name = {json.dumps(name)}",
        f"description = {json.dumps(role['description'])}",
        f"model = {json.dumps(codex['model'])}",
        f"model_provider = {json.dumps(codex['provider'])}",
        f"model_reasoning_effort = {json.dumps(codex['effort'])}",
        f"sandbox_mode = {json.dumps(codex['sandbox'])}",
        "",
        'developer_instructions = """',
        role_body(role).rstrip(),
        '"""',
        "",
    ]
    return "\n".join(lines)


def render_mcp(roles: dict[str, dict[str, Any]], *, claude: bool) -> str:
    bridge = (
        "${CLAUDE_PLUGIN_ROOT}/mcp/acp_bridge.py" if claude else "mcp/acp_bridge.py"
    )
    roles_path = "${CLAUDE_PLUGIN_ROOT}/roles.json" if claude else "roles.json"
    config: dict[str, Any] = {
        "command": "python3",
        "args": [bridge, "--roles", roles_path, "opencode", "acp"],
    }
    if claude:
        config["timeout"] = 3600000
    else:
        config["cwd"] = "."
        config["tool_timeout_sec"] = 3600
    servers = {"opencode": config}
    return json.dumps({"mcpServers": servers}, indent=2) + "\n"


def generated_files() -> dict[Path, str]:
    roles = load_roles()
    files: dict[Path, str] = {}
    for name, role in roles.items():
        files[AGENTS_ROOT / f"{name}.md"] = render_frontmatter(name, role)
        if "codex" in role:
            files[AGENTS_ROOT / f"{name}.toml"] = render_toml(name, role)
    files[PLUGIN_ROOT / ".mcp.json"] = render_mcp(roles, claude=False)
    files[PLUGIN_ROOT / ".mcp.claude.json"] = render_mcp(roles, claude=True)
    return files


def check(files: dict[Path, str]) -> int:
    drifted = False
    for path, expected in files.items():
        actual = path.read_text() if path.exists() else ""
        if actual == expected:
            continue
        drifted = True
        diff = difflib.unified_diff(
            actual.splitlines(keepends=True),
            expected.splitlines(keepends=True),
            fromfile=str(path),
            tofile=f"{path} (regenerated)",
        )
        print("".join(diff), end="")
    return 1 if drifted else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = generated_files()
    if args.check:
        return check(files)
    for path, content in files.items():
        path.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
