#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a TypeScript file under plugins/ uses `import.meta.main`.

Node 23.6 to 24.1 strips types but leaves `import.meta.main` undefined, so a
`main()` behind it never runs, and the hook exits 0 having done nothing. Each
error names a fix inside the file's own plugin, so no plugin imports from
another.
"""

import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
USE = "import.meta.main is undefined on Node 23.6-24.1; "
FIX = {
    "rex-agents": "use isMain() from plugins/rex-agents/scripts/is_main.ts",
    "swe": "compare realpath(process.argv[1]) with the module path, as invokedDirectly() in plugins/swe/skills/ship-pr/scripts/pr_body.ts does",
}
DEFAULT_FIX = "compare realpath(process.argv[1]) with the module path"
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def main() -> int:
    failures = 0
    for path in sorted((ROOT / "plugins").rglob("*.ts")):
        if "node_modules" in path.parts:
            continue
        # Blank block comments but keep their newlines, so line numbers stay right.
        text = BLOCK_COMMENT.sub(
            lambda m: "\n" * m.group().count("\n"), path.read_text()
        )
        for number, line in enumerate(text.splitlines(), 1):
            if "import.meta.main" in line and not line.lstrip().startswith("//"):
                plugin = path.relative_to(ROOT / "plugins").parts[0]
                print(
                    f"{path.relative_to(ROOT)}:{number}: {USE}{FIX.get(plugin, DEFAULT_FIX)}"
                )
                failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
