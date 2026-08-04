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
    path = os.environ.get("FAKE_QMD_COLLECTION_PATH", str(root))
    print("Collection: llmos")
    print(f"  Path:     {path}")
    raise SystemExit(0)

if args[:2] == ["ls", "llmos/llmOS.md"]:
    if args != ["ls", "llmos/llmOS.md"]:
        print(f"unexpected qmd arguments: {args}", file=sys.stderr)
        raise SystemExit(2)
    if mode == "unindexed":
        print("No files found under qmd://llmos/llmos.md")
    else:
        print("1.0 KB  Jan 1 00:00  qmd://llmos/llmos.md")
    raise SystemExit(0)

if args[:2] == ["get", "qmd://llmos/llmOS.md"]:
    if args != ["get", "qmd://llmos/llmOS.md", "--no-line-numbers"]:
        print(f"unexpected qmd arguments: {args}", file=sys.stderr)
        raise SystemExit(2)
    if mode == "retrieval-mismatch":
        print("# Wrong document")
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
        extra_env: dict[str, str] | None = None,
        resolution: str = "env",
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PATH"] = str(self.bin)
        env["HOME"] = str(self.home)
        env["FAKE_VAULT_ROOT"] = str(self.root)
        env["FAKE_QMD_COLLECTION_PATH"] = str(self.root)
        env.pop("LLMOS_ROOT", None)
        if resolution == "env":
            env["LLMOS_ROOT"] = str(self.root)
        elif resolution == "config":
            self.write_config(self.root)
        else:
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

    def test_wrong_obsidian_sentinel_fails(self) -> None:
        result = self.run_doctor(
            extra_env={"FAKE_OBSIDIAN_MODE": "wrong", "LLMOS_DOCTOR_OS": "Darwin"}
        )

        self.assert_failed(result, "obsidian-vault", f'open -a Obsidian "{self.root}"')
        self.assertIn("content does not match", result.stdout)

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

    def test_qmd_retrieval_content_mismatch_fails(self) -> None:
        result = self.run_doctor(extra_env={"FAKE_QMD_MODE": "retrieval-mismatch"})

        self.assert_failed(result, "qmd-retrieval", "qmd update")
        self.assertIn("does not match", result.stdout)


if __name__ == "__main__":
    unittest.main()
