"""The llmOS profile's frontmatter contract checks -- moved out of
`scripts/audit_metadata.py` so `vault_health`'s schema-violations section and
the standalone audit CLI share one check, never two (issue #31: "reusing the
existing audit logic rather than duplicating it"). This module is llmOS-
profile-specific (specs, dailies, the canonical property set); a plain vault
like xbrain has no schema layer and never calls it.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

# Specs advance draft -> active -> review -> done; ADRs use proposed/accepted/superseded.
SPEC_STATUSES = {"draft", "active", "review", "done", "archived"}
STATUSES = SPEC_STATUSES | {"proposed", "accepted", "superseded"}
AUTHORS = {"claude", "codex", "gemini", "human"}
LINK_FIELDS = {"categories", "topics", "project"}
WIKILINK = re.compile(r'^"?\[\[[^\]]+\]\]"?$')
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SPEC_NAME = re.compile(r"^\d{4}-[A-Za-z0-9][A-Za-z0-9_-]*\.md$")


def frontmatter(path: Path) -> dict[str, str | list[str]] | None:
    """Parse a note's leading YAML frontmatter block by hand -- scalars,
    quoted strings, inline `[a, b]` lists, and block `  - ` lists -- without
    pulling in a full YAML parser.

    Use when `collect_errors` needs a note's properties to check against the
    llmOS schema contract; this is the property-shape half of that contract.
    Do NOT use when you need the note body too or full YAML fidelity (nested
    maps, anchors) -- this is a schema-checking shortcut, not a general
    frontmatter parser.

    Example output:
        {'status': 'active', 'categories': ['[[Specifications]]']}

    Example invocation:
        from llmos_vault.schema import frontmatter
        properties = frontmatter(Path("/path/to/vault/notes/alpha.md"))

    Args:
        path: Path to the note to parse.
    """
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
    """List markdown files under `root` that git sees as untracked (new,
    never `git add`ed), via `git ls-files --others --exclude-standard`.

    Use when `collect_errors` needs to tell a brand-new note from an existing
    one -- new notes get a stricter `created`-date check than notes already
    checked in.
    Do NOT use when `root` isn't a git repo -- a non-zero git exit is
    swallowed and an empty set is returned, silently skipping the check
    rather than raising.

    Example output:
        {PosixPath('inbox/new-capture.md')}

    Example invocation:
        from llmos_vault.schema import untracked_markdown
        new_notes = untracked_markdown(Path("/path/to/vault"))

    Args:
        root: Vault root to check untracked files under.
    """
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--others", "--exclude-standard"],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        return set()
    return {Path(line) for line in result.stdout.splitlines() if line.endswith(".md")}


def collect_errors(root: Path) -> tuple[list[str], int]:
    """Walk `root` and return (schema-violation messages, notes checked).

    Use when policing the llmOS property contract -- both the standalone
    `audit_metadata.py` CLI and `vault_health`'s schema-violations section
    call this so the rules live in exactly one place.
    Do NOT use when the vault has no llmOS schema layer (e.g. xbrain) --
    every message assumes the llmOS property contract.

    Example output:
        (["knowledge/thing.md: invalid status 'nearly-done'"], 42)

    Example invocation:
        from llmos_vault.schema import collect_errors
        errors, checked = collect_errors(Path("/path/to/llmos-vault"))

    Args:
        root: Vault root to walk.
    """
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
        if relative in new_notes or is_daily_review:
            created = properties.get("created")
            if not isinstance(created, str) or not ISO_DATE.fullmatch(created):
                errors.append(f"{relative}: created must be an ISO date")
        if is_daily_review and "project" in properties:
            errors.append(f"{relative}: daily reviews must not claim project ownership")

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
                    f"{relative}: project must link "
                    f"projects/{project_dir}/{project_dir} with an alias"
                )
        elif is_project_owned:
            if not properties.get("project"):
                errors.append(f"{relative}: project-owned note lacks project link")
    return errors, checked
