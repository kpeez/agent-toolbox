"""Prove every Claude agent definition has a matching Codex twin.

Agents ship dual-format: a Claude .md (frontmatter + prose body) and a Codex
.toml (same fields, prose folded into developer_instructions). Nothing stops
one side from being added, renamed, or edited without the other, so a
hardcoded roster would be one more normative fact that cannot notice it went
stale -- the roster is discovered from plugins/*/agents/*.md on disk instead,
same justification as test_plugin_registration.py.
"""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _agent_md_paths() -> list[Path]:
    return sorted(REPO_ROOT.glob("plugins/*/agents/*.md"))


def _frontmatter(md_path: Path) -> dict[str, str]:
    text = md_path.read_text()
    _, frontmatter, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


class AgentTwinParityTests(unittest.TestCase):
    def test_every_agent_has_a_toml_twin(self) -> None:
        for md_path in _agent_md_paths():
            toml_path = md_path.with_suffix(".toml")
            with self.subTest(agent=md_path.name):
                self.assertTrue(toml_path.is_file(), f"missing twin: {toml_path}")

    def test_twin_names_match(self) -> None:
        for md_path in _agent_md_paths():
            toml_path = md_path.with_suffix(".toml")
            if not toml_path.is_file():
                continue
            md_name = _frontmatter(md_path)["name"]
            toml_name = tomllib.loads(toml_path.read_text())["name"]
            with self.subTest(agent=md_path.name):
                self.assertEqual(md_name, toml_name)

    def test_twin_descriptions_agree(self) -> None:
        for md_path in _agent_md_paths():
            toml_path = md_path.with_suffix(".toml")
            if not toml_path.is_file():
                continue
            md_description = _frontmatter(md_path)["description"]
            toml_description = tomllib.loads(toml_path.read_text())["description"]
            with self.subTest(agent=md_path.name):
                self.assertTrue(md_description, "md description is empty")
                self.assertTrue(toml_description, "toml description is empty")
                self.assertEqual(md_description, toml_description)


if __name__ == "__main__":
    unittest.main()
