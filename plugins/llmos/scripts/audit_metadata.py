#!/usr/bin/env python3
"""Audit llmOS frontmatter contracts. Read-only unless --fix is passed."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
from pathlib import Path

from vault_root import vault_root

# Specs advance draft -> active -> review -> done; ADRs use proposed/accepted/superseded.
SPEC_STATUSES = {"draft", "active", "review", "done", "archived"}
STATUSES = SPEC_STATUSES | {"proposed", "accepted", "superseded"}
AUTHORS = {"claude", "codex", "gemini", "human"}
LINK_FIELDS = {"categories", "topics", "project"}
WIKILINK = re.compile(r'^"?\[\[[^\]]+\]\]"?$')
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PROJECT_LOG_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}-[A-Za-z0-9][A-Za-z0-9_-]*\.md$")
SPEC_NAME = re.compile(r"^\d{4}-[A-Za-z0-9][A-Za-z0-9_-]*\.md$")


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


def frontmatter(path: Path) -> dict[str, str | list[str]] | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    result: dict[str, str | list[str]] = {}
    current: str | None = None
    for line in text[4:end].splitlines():
        if line.startswith("  - ") and current:
            value = line[4:].strip().strip('"').strip("'")
            existing = result.setdefault(current, [])
            if isinstance(existing, list):
                existing.append(value)
            continue
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        current = key.strip()
        scalar = value.strip()
        if scalar == "[]":
            result[current] = []
        elif scalar.startswith("[") and scalar.endswith("]"):
            result[current] = [
                part.strip() for part in scalar[1:-1].split(",") if part.strip()
            ]
        elif scalar:
            result[current] = scalar.strip('"')
        else:
            result[current] = []
    return result


def untracked_markdown(root: Path) -> set[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        return set()
    return {Path(line) for line in result.stdout.splitlines() if line.endswith(".md")}


def project_alias(root: Path, slug: str) -> str:
    """Display alias for a project link: the landing page's H1, else the slug."""
    landing = root / "projects" / slug / f"{slug}.md"
    if landing.is_file():
        for line in landing.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return slug


def stamp(path: Path, root: Path, relative: Path) -> bool:
    """Add the vault properties this spec's own path already implies.

    Only ever adds an absent key -- a present-but-wrong value is a judgment call
    the audit reports rather than something this silently overwrites.
    """
    properties = frontmatter(path) or {}
    slug = relative.parts[1]
    additions: list[str] = []
    if "categories" not in properties:
        additions.append('categories:\n  - "[[Specifications]]"')
    if "project" not in properties:
        alias = project_alias(root, slug)
        additions.append(f'project:\n  - "[[projects/{slug}/{slug}|{alias}]]"')
    if not additions:
        return False

    text = path.read_text(encoding="utf-8")
    block = "\n".join(additions)
    end = text.find("\n---\n", 4) if text.startswith("---\n") else -1
    if end == -1:
        text = f"---\n{block}\n---\n\n{text.lstrip()}"
    else:
        text = f"{text[:end]}\n{block}{text[end:]}"
    path.write_text(text, encoding="utf-8")
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
    errors: list[str] = []
    checked = 0
    new_notes = untracked_markdown(root)
    for path in sorted(root.rglob("*.md")):
        relative = path.relative_to(root)
        if relative.parts[0] == "templates" or any(
            part.startswith(".") for part in relative.parts
        ):
            continue
        if not path.is_file():
            # A broken symlink is a vault defect, not a schema one; report and move on.
            errors.append(f"{relative}: broken symlink -> {os.readlink(path)}")
            continue
        properties = frontmatter(path)
        if relative.name == "SKILL.md" and "skills" in relative.parts:
            if (
                properties is None
                or not properties.get("name")
                or not properties.get("description")
            ):
                errors.append(f"{relative}: invalid skill frontmatter")
            continue
        is_canonical_spec_or_status = (
            len(relative.parts) >= 3
            and relative.parts[0] == "projects"
            and "specs" in relative.parts
            and SPEC_NAME.fullmatch(relative.name) is not None
        )
        is_legacy_spec = "specs" in relative.parts

        if properties is None:
            if is_canonical_spec_or_status:
                errors.append(f"{relative}: missing frontmatter")
                checked += 1
            elif is_legacy_spec:
                # legacy supporting notes without frontmatter remain allowed
                continue
            else:
                errors.append(f"{relative}: missing frontmatter")
                checked += 1
            continue

        checked += 1

        is_daily_review = relative.parts[:2] == ("reviews", "daily")
        is_project_log = (
            len(relative.parts) == 4
            and relative.parts[0] == "projects"
            and relative.parts[2] == "logs"
            and relative.suffix == ".md"
        )
        if relative in new_notes or is_daily_review or is_project_log:
            created = properties.get("created")
            if not isinstance(created, str) or not ISO_DATE.fullmatch(created):
                errors.append(f"{relative}: created must be an ISO date")
        if is_daily_review and "project" in properties:
            errors.append(f"{relative}: daily reviews must not claim project ownership")
        if is_project_log:
            project_dir = relative.parts[1]
            if not PROJECT_LOG_NAME.fullmatch(
                relative.name
            ) or not relative.stem.endswith(f"-{project_dir}"):
                errors.append(
                    f"{relative}: project log filename must be YYYY-MM-DD-{project_dir}.md"
                )
            categories = properties.get("categories")
            if not isinstance(categories, list) or "[[Project Logs]]" not in categories:
                errors.append(f"{relative}: project logs must use [[Project Logs]]")
            project_val = properties.get("project")
            expected_prefix = f"[[projects/{project_dir}/{project_dir}|"
            if (
                not isinstance(project_val, list)
                or len(project_val) != 1
                or not project_val[0].startswith(expected_prefix)
                or not project_val[0].endswith("]]")
            ):
                errors.append(f"{relative}: project log must link its owning project")

        # Operational properties are optional; validate only when present
        status = properties.get("status")
        if status is not None and status not in STATUSES:
            errors.append(f"{relative}: invalid status {status!r}")

        authors = properties.get("authors")
        if authors is not None:
            if not isinstance(authors, list) or any(
                value not in AUTHORS for value in authors
            ):
                errors.append(f"{relative}: authors must be a canonical list")

        # Check forbidden fields and empty values for all files
        for forbidden in ("kind", "type", "related", "sources"):
            if forbidden in properties:
                errors.append(f"{relative}: contains retired property {forbidden}")
        for key, val in properties.items():
            if val == [] or val == "" or val is None:
                errors.append(f"{relative}: property {key} is empty")
            elif isinstance(val, list) and any(v == "" or v is None for v in val):
                errors.append(f"{relative}: property {key} contains empty value")

        for field in LINK_FIELDS:
            if field in properties:
                values = properties[field]
                if not isinstance(values, list):
                    errors.append(f"{relative}: {field} must be a list")
                    continue
                for value in values:
                    if not WIKILINK.match(value):
                        errors.append(
                            f"{relative}: {field} contains non-wikilink {value!r}"
                        )

        is_project_entrypoint = (
            len(relative.parts) == 3
            and relative.parts[0] == "projects"
            and relative.name == f"{relative.parts[1]}.md"
        )
        is_project_owned = (
            len(relative.parts) >= 3
            and relative.parts[0] == "projects"
            and not is_project_entrypoint
        )

        if is_canonical_spec_or_status:
            # Must have category [[Specifications]]
            categories = properties.get("categories")
            if (
                not isinstance(categories, list)
                or "[[Specifications]]" not in categories
            ):
                errors.append(
                    f"{relative}: categories must be a list containing [[Specifications]]"
                )
            # Must have correct project ownership wikilink
            project_dir = relative.parts[1]
            expected_project_prefix = f"[[projects/{project_dir}/{project_dir}|"
            project_val = properties.get("project")
            has_expected_project = isinstance(project_val, list) and any(
                value.startswith(expected_project_prefix) and value.endswith("]]")
                for value in project_val
            )
            if not has_expected_project:
                errors.append(
                    f"{relative}: project must link projects/{project_dir}/{project_dir} with an alias"
                )
        elif is_project_owned:
            if not properties.get("project"):
                errors.append(f"{relative}: project-owned note lacks project link")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"metadata audit passed: {checked} notes")


if __name__ == "__main__":
    main()
