from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DOCTOR = PLUGIN_ROOT / "scripts/doctor.sh"
ROOT_REPAIR = (
    'Run /setup-llmos, or set it manually: export LLMOS_ROOT="/absolute/path/to/llmOS"'
)
SENTINEL = """---
status: active
---

# llmOS

Shared test vault.
"""

FAKE_OBSIDIAN = r"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

mode = os.environ.get("FAKE_OBSIDIAN_MODE", "pass")
if sys.argv[1:] != ["vault=llmOS", "read", "path=llmOS.md"]:
    print(f"unexpected obsidian-cli arguments: {sys.argv[1:]}", file=sys.stderr)
    raise SystemExit(2)
if mode == "fail":
    print("The CLI is unable to find Obsidian.", file=sys.stderr)
    raise SystemExit(1)
if mode == "wrong":
    print("# Not llmOS")
    raise SystemExit(0)
root = Path(os.environ["FAKE_VAULT_ROOT"])
print((root / "llmOS.md").read_text(encoding="utf-8"), end="")
"""

FAKE_QMD = r"""#!/usr/bin/env python3
import os
import sys
from pathlib import Path

args = sys.argv[1:]
mode = os.environ.get("FAKE_QMD_MODE", "pass")
root = Path(os.environ["FAKE_VAULT_ROOT"])

if args[:3] == ["collection", "show", "llmos"]:
    if args != ["collection", "show", "llmos"]:
        print(f"unexpected qmd arguments: {args}", file=sys.stderr)
        raise SystemExit(2)
    if mode == "missing-collection":
        print("Collection not found: llmos", file=sys.stderr)
        raise SystemExit(1)
    path = os.environ.get("FAKE_QMD_COLLECTION_PATH", str(root))
    print("Collection: llmos")
    print(f"  Path:     {path}")
    raise SystemExit(0)

if args[:2] == ["ls", "llmos/llmOS.md"]:
    if args != ["ls", "llmos/llmOS.md"]:
        print(f"unexpected qmd arguments: {args}", file=sys.stderr)
        raise SystemExit(2)
    if mode == "index-failure":
        print("sqlite database unavailable", file=sys.stderr)
        raise SystemExit(1)
    if mode == "unindexed":
        print("No files found under qmd://llmos/llmos.md")
    else:
        print("1.0 KB  Jan 1 00:00  qmd://llmos/llmos.md")
    raise SystemExit(0)

if args[:2] == ["get", "qmd://llmos/llmOS.md"]:
    if args != ["get", "qmd://llmos/llmOS.md", "--no-line-numbers"]:
        print(f"unexpected qmd arguments: {args}", file=sys.stderr)
        raise SystemExit(2)
    if mode == "retrieval-failure":
        print("Document not found: qmd://llmos/llmOS.md", file=sys.stderr)
        raise SystemExit(1)
    if mode == "retrieval-mismatch":
        print("# Wrong document")
    elif mode == "headered-retrieval":
        print("qmd://llmos/llmOS.md  #fixture")
        print("Folder Context: fixture")
        print("---")
        print()
        print((root / "llmOS.md").read_text(encoding="utf-8"), end="")
    else:
        print((root / "llmOS.md").read_text(encoding="utf-8"))
    raise SystemExit(0)

print(f"unsupported qmd arguments: {args}", file=sys.stderr)
raise SystemExit(2)
"""


class DoctorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(prefix="setup-llmos-")
        self.base = Path(self.temporary_directory.name)
        self.root = self.base / "vault"
        self.bin = self.base / "bin"
        self.home = self.base / "home"
        (self.root / ".obsidian").mkdir(parents=True)
        self.root = self.root.resolve()
        self.bin.mkdir()
        self.home.mkdir()
        for tool in ("awk", "dirname", "uname", "python3"):
            tool_path = shutil.which(tool)
            if tool_path is None:
                self.fail(f"required test tool not found: {tool}")
            (self.bin / tool).symlink_to(tool_path)
        (self.root / "llmOS.md").write_text(SENTINEL, encoding="utf-8")
        self.write_executable("obsidian-cli", FAKE_OBSIDIAN)
        self.write_executable("qmd", FAKE_QMD)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_executable(self, name: str, content: str) -> None:
        path = self.bin / name
        content = content.replace("#!/usr/bin/env python3", f"#!{sys.executable}", 1)
        path.write_text(content, encoding="utf-8")
        path.chmod(0o755)

    def write_config(self, root: Path) -> None:
        config_dir = self.home / ".config" / "llmos"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps({"vault_root": str(root)}), encoding="utf-8"
        )

    def run_doctor(
        self,
        *,
        obsidian: bool = True,
        qmd: bool = True,
        root: Path | None = None,
        extra_env: dict[str, str] | None = None,
        resolution: str = "env",
    ) -> subprocess.CompletedProcess[str]:
        if not obsidian:
            (self.bin / "obsidian-cli").unlink()
        if not qmd:
            (self.bin / "qmd").unlink()

        target_root = root or self.root

        env = os.environ.copy()
        env["PATH"] = str(self.bin)
        env["HOME"] = str(self.home)
        env["FAKE_VAULT_ROOT"] = str(target_root)
        env["FAKE_QMD_COLLECTION_PATH"] = str(target_root)
        env.pop("LLMOS_ROOT", None)
        if resolution == "env":
            env["LLMOS_ROOT"] = str(target_root)
        elif resolution == "config":
            self.write_config(target_root)
        elif resolution != "unset":
            self.fail(f"unknown resolution mode: {resolution}")
        if extra_env:
            env.update(extra_env)

        return subprocess.run(
            ["/bin/bash", str(DOCTOR)],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def assert_failed(
        self, result: subprocess.CompletedProcess[str], check: str, repair: str
    ) -> None:
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(f"FAIL {check}:", result.stdout)
        self.assertIn(f"REPAIR {repair}", result.stdout)

    def test_healthy_setup_passes(self) -> None:
        result = self.run_doctor()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for check in (
            "vault-root",
            "obsidian-cli",
            "obsidian-vault",
            "qmd",
            "qmd-collection",
            "qmd-index",
            "qmd-retrieval",
        ):
            self.assertIn(f"PASS {check}:", result.stdout)
        self.assertNotIn("FAIL ", result.stdout)
        self.assertNotIn("REPAIR ", result.stdout)

    def test_config_used_when_env_unset(self) -> None:
        result = self.run_doctor(resolution="config")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"PASS vault-root: {self.root}", result.stdout)

    def test_env_wins_over_config(self) -> None:
        other_root = self.base / "other-vault"
        (other_root / ".obsidian").mkdir(parents=True)
        (other_root / "llmOS.md").write_text(SENTINEL, encoding="utf-8")
        self.write_config(other_root)
        result = self.run_doctor(resolution="env")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"PASS vault-root: {self.root}", result.stdout)

    def test_fails_loudly_when_neither_env_nor_config_present(self) -> None:
        result = self.run_doctor(resolution="unset")

        self.assert_failed(result, "vault-root", ROOT_REPAIR)
        self.assertEqual(result.stdout.count(" vault-root:"), 1, result.stdout)

    def test_invalid_root_fails(self) -> None:
        invalid_root = self.base / "not-a-vault"
        invalid_root.mkdir()
        result = self.run_doctor(root=invalid_root)

        self.assert_failed(result, "vault-root", ROOT_REPAIR)
        for check in (
            "vault-root",
            "obsidian-cli",
            "obsidian-vault",
            "qmd",
            "qmd-collection",
            "qmd-index",
            "qmd-retrieval",
        ):
            self.assertEqual(result.stdout.count(f" {check}:"), 1, result.stdout)

    def test_missing_obsidian_cli_fails_macos(self) -> None:
        result = self.run_doctor(
            obsidian=False, extra_env={"LLMOS_DOCTOR_OS": "Darwin"}
        )

        self.assert_failed(
            result,
            "obsidian-cli",
            'brew install --cask obsidian && ln -sfh '
            '"/Applications/Obsidian.app/Contents/MacOS/obsidian-cli" '
            '"$(brew --prefix)/bin/obsidian-cli"',
        )

    def test_missing_obsidian_cli_fails_linux(self) -> None:
        result = self.run_doctor(obsidian=False, extra_env={"LLMOS_DOCTOR_OS": "Linux"})

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL obsidian-cli:", result.stdout)
        self.assertIn("REPAIR sudo snap install obsidian --classic", result.stdout)
        self.assertIn('"$HOME/.local/bin/obsidian-cli"', result.stdout)

    def test_missing_qmd_fails(self) -> None:
        result = self.run_doctor(qmd=False)

        self.assert_failed(result, "qmd", "npm install -g @tobilu/qmd")

    def test_unavailable_obsidian_fails_macos(self) -> None:
        result = self.run_doctor(
            extra_env={"FAKE_OBSIDIAN_MODE": "fail", "LLMOS_DOCTOR_OS": "Darwin"}
        )

        self.assert_failed(result, "obsidian-vault", f'open -a Obsidian "{self.root}"')
        self.assertIn("unable to find Obsidian", result.stdout)

    def test_unavailable_obsidian_fails_linux(self) -> None:
        result = self.run_doctor(
            extra_env={"FAKE_OBSIDIAN_MODE": "fail", "LLMOS_DOCTOR_OS": "Linux"}
        )

        self.assert_failed(
            result,
            "obsidian-vault",
            f'obsidian "{self.root}"',
        )
        self.assertIn(
            "NOTE enable Settings > General > Advanced > Command line interface",
            result.stdout,
        )
        self.assertIn("unable to find Obsidian", result.stdout)

    def test_wrong_obsidian_sentinel_fails(self) -> None:
        result = self.run_doctor(
            extra_env={"FAKE_OBSIDIAN_MODE": "wrong", "LLMOS_DOCTOR_OS": "Darwin"}
        )

        self.assert_failed(result, "obsidian-vault", f'open -a Obsidian "{self.root}"')
        self.assertIn("content does not match", result.stdout)

    def test_missing_qmd_collection_fails(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "missing-collection"})

        self.assert_failed(
            result,
            "qmd-collection",
            f'qmd collection add "{self.root}" --name llmos',
        )

    def test_wrong_qmd_collection_path_fails(self) -> None:
        wrong_root = self.base / "other-vault"
        wrong_root.mkdir()
        result = self.run_doctor(
            extra_env={"FAKE_QMD_COLLECTION_PATH": str(wrong_root)}
        )

        self.assert_failed(
            result,
            "qmd-collection",
            f'qmd collection remove llmos && qmd collection add "{self.root}" --name llmos',
        )

    def test_unindexed_sentinel_fails_even_when_qmd_ls_exits_zero(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "unindexed"})

        self.assert_failed(result, "qmd-index", "qmd update")
        self.assertIn("PASS qmd-retrieval:", result.stdout)

    def test_qmd_index_runtime_failure_is_not_reported_as_stale(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "index-failure"})

        self.assert_failed(result, "qmd-index", "qmd status")
        self.assertIn("sqlite database unavailable", result.stdout)
        self.assertNotIn("stale or unindexed", result.stdout)

    def test_qmd_retrieval_failure_fails(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "retrieval-failure"})

        self.assert_failed(result, "qmd-retrieval", "qmd update")
        self.assertIn("Document not found", result.stdout)

    def test_qmd_retrieval_accepts_headered_output(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "headered-retrieval"})

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS qmd-retrieval:", result.stdout)

    def test_qmd_retrieval_content_mismatch_fails(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "retrieval-mismatch"})

        self.assert_failed(result, "qmd-retrieval", "qmd update")
        self.assertIn("does not match", result.stdout)

    def test_doctor_is_executable(self) -> None:
        self.assertTrue(os.access(DOCTOR, os.X_OK))


if __name__ == "__main__":
    unittest.main()
