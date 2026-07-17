"""The llmOS profile's frontmatter contract checks -- moved out of
`scripts/audit_metadata.py` so `vault_health`'s schema-violations section and
the standalone audit CLI share one check, never two (issue #31: "reusing the
existing audit logic rather than duplicating it"). This module is llmOS-
profile-specific (specs, dailies, the canonical property set); a plain vault
like xbrain has no schema layer and never calls it.

Frontmatter parsing itself is never hand-rolled here -- `_properties_or_none`
routes through `llmos_vault.frontmatter.parse`, the one canonical
reader/writer (ADR-0004: "one frontmatter owner"), so schema checks see
exactly the same inline-list/empty-scalar/wikilink-quoting semantics as every
other verb in the library.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from llmos_vault.frontmatter import Property
from llmos_vault.frontmatter import parse as parse_frontmatter

# Specs advance draft -> active -> review -> done; ADRs use proposed/accepted/superseded.
SPEC_STATUSES = {"draft", "active", "review", "done", "archived"}
STATUSES = SPEC_STATUSES | {"proposed", "accepted", "superseded"}
AUTHORS = {"claude", "codex", "gemini", "human"}
LINK_FIELDS = {"categories", "topics", "project"}
WIKILINK = re.compile(r'^"?\[\[[^\]]+\]\]"?$')
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SPEC_NAME = re.compile(r"^\d{4}-[A-Za-z0-9][A-Za-z0-9_-]*\.md$")


def _properties_or_none(path: Path) -> dict[str, Property] | None:
    """A note's frontmatter properties via the canonical parser, or None if
    the note has no frontmatter block at all -- `collect_errors` treats a
    missing block as its own violation rather than a parse error."""
    text = path.read_text(encoding="utf-8")
    try:
        properties, _ = parse_frontmatter(text)
    except ValueError:
        return None
    return properties


def project_alias(root: Path, slug: str) -> str:
    """Display alias for a project link: the landing page's H1, else the slug.

    Use when stamping a `project` wikilink property -- the vault convention is
    `[[projects/<slug>/<slug>|Alias]]`, and the alias is the landing page's
    own H1 heading so the link reads naturally rather than as a raw slug.
    Do NOT use when the note being stamped *is* the project's own landing
    page -- schema.md says to omit the self-link on a canonical project
    note/landing page rather than call this at all.

    Example output:
        'Agent Toolbox'

    Example invocation:
        from llmos_vault.schema import project_alias
        project_alias(Path("/path/to/vault"), "agent-toolbox")

    Args:
        root: Vault root the project lives in.
        slug: Project directory name under `projects/`.
    """
    landing = root / "projects" / slug / f"{slug}.md"
    if landing.is_file():
        for line in landing.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    return slug


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
        properties = _properties_or_none(path)
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
