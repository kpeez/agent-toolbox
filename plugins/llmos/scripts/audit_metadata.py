#!/usr/bin/env python3
"""Audit llmOS frontmatter contracts. Read-only unless --fix is passed."""

from __future__ import annotations

import argparse
from pathlib import Path

from llmos_vault import frontmatter
from llmos_vault.root import vault_root
from llmos_vault.schema import SPEC_NAME, collect_errors, project_alias


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Vault root; resolved via the shared resolver when omitted.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Stamp the path-derived properties (categories, project) onto specs "
        "that lack them, then audit. Writes only what the path already implies.",
    )
    return parser.parse_args()


def stamp(path: Path, root: Path, relative: Path) -> bool:
    """Add the vault properties this spec's own path already implies.

    Only ever adds an absent key -- a present-but-wrong value is a judgment call
    the audit reports rather than something this silently overwrites. Routes
    through the canonical `llmos_vault.frontmatter` parse/serialize (ADR-0004
    "one frontmatter owner") rather than hand-splicing raw text, so a stamped
    note comes out in the vault's one normalized shape.
    """
    text = path.read_text(encoding="utf-8")
    try:
        properties, body = frontmatter.parse(text)
    except ValueError:
        properties, body = {}, text.lstrip()

    slug = relative.parts[1]
    added = False
    if "categories" not in properties:
        properties["categories"] = ["[[Specifications]]"]
        added = True
    if "project" not in properties:
        alias = project_alias(root, slug)
        properties["project"] = [f"[[projects/{slug}/{slug}|{alias}]]"]
        added = True
    if not added:
        return False

    path.write_text(frontmatter.serialize(properties, body), encoding="utf-8")
    return True


def canonical_specs(root: Path) -> list[tuple[Path, Path]]:
    """Every canonical NNNN-<slug>.md spec, as (absolute, vault-relative) pairs."""
    result = []
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts) or not path.is_file():
            continue
        if (
            relative.parts[0] == "projects"
            and "specs" in relative.parts
            and SPEC_NAME.fullmatch(relative.name)
        ):
            result.append((path, relative))
    return result


def main() -> None:
    args = parse_args()
    root = args.root.expanduser().resolve() if args.root else vault_root()
    if args.fix:
        fixed = sum(stamp(path, root, rel) for path, rel in canonical_specs(root))
        print(f"stamped {fixed} specs")
    errors, checked = collect_errors(root)
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"metadata audit passed: {checked} notes")


if __name__ == "__main__":
    main()
