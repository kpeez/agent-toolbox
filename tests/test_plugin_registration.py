"""Prove every plugin is registered in both marketplaces and versioned consistently.

These invariants are cheap to state and were still violated on a real machine:
llmos shipped registered in .claude-plugin/marketplace.json and absent from
.agents/plugins/marketplace.json, so Codex -- which reads the .agents file, and
falls back to the .claude-plugin one only when it is absent -- could not install
llmos at all. A partial copy shadows the complete file and is worse than no copy.

The llmos suite already asserted marketplace registration -- against one of the
two files -- and passed the whole time, because it was written from a spec
sentence that named one file. A test that repeats the spec's wording inherits
the spec's blind spot.

So the expected set is discovered from plugins/*/ on disk rather than listed
here. A hardcoded roster would be one more normative fact that cannot notice it
went stale, which is the bug these tests exist to catch.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
AGENTS_MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"


def _plugin_dirs() -> set[str]:
    return {
        d.name
        for d in (REPO_ROOT / "plugins").iterdir()
        if (d / ".claude-plugin" / "plugin.json").is_file()
    }


def _entries(marketplace: Path) -> list[dict]:
    return json.loads(marketplace.read_text())["plugins"]


def _source_path(entry: dict) -> str:
    # The two marketplaces disagree on shape: claude takes a bare string, the
    # .agents schema wraps it in a local-source object.
    source = entry["source"]
    return source if isinstance(source, str) else source["path"]


class MarketplaceRegistrationTests(unittest.TestCase):
    def test_claude_marketplace_lists_every_plugin(self) -> None:
        listed = {e["name"] for e in _entries(CLAUDE_MARKETPLACE)}
        self.assertEqual(listed, _plugin_dirs())

    def test_agents_marketplace_lists_every_plugin(self) -> None:
        listed = {e["name"] for e in _entries(AGENTS_MARKETPLACE)}
        self.assertEqual(listed, _plugin_dirs())

    def test_marketplace_sources_point_at_real_directories(self) -> None:
        for marketplace in (CLAUDE_MARKETPLACE, AGENTS_MARKETPLACE):
            for entry in _entries(marketplace):
                path = (REPO_ROOT / _source_path(entry)).resolve()
                with self.subTest(marketplace=marketplace.name, plugin=entry["name"]):
                    self.assertTrue(path.is_dir(), f"{path} is not a directory")


class PluginVersionTests(unittest.TestCase):
    def test_both_manifests_agree_on_version(self) -> None:
        # bump-plugin-version.sh writes both; nothing stops a hand edit from
        # writing one, which is how the harnesses come to disagree on what a
        # given version contains.
        for name in sorted(_plugin_dirs()):
            plugin = REPO_ROOT / "plugins" / name
            versions = {
                manifest: json.loads((plugin / manifest / "plugin.json").read_text())[
                    "version"
                ]
                for manifest in (".claude-plugin", ".codex-plugin")
            }
            with self.subTest(plugin=name):
                self.assertEqual(len(set(versions.values())), 1, versions)


if __name__ == "__main__":
    unittest.main()
