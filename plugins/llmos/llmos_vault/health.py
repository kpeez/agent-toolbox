"""`vault_health`: the nightly agent's opening move -- one headless pass
aggregating vault hygiene into a single report (spec behavior 7). Each
section is independently computable; a failure in one (e.g. qmd unavailable)
degrades that section only, never the whole report. Schema-violation checks
are the llmOS profile's own contract (`llmos_vault.schema`) and are skipped
entirely for a plain vault like xbrain -- every other section is schema-
agnostic and runs against any vault.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from llmos_vault.graph import _backlinks, _linked_targets, _outgoing
from llmos_vault.links import VaultIndex, build_index, read_frontmatter
from llmos_vault.schema import collect_errors

Profile = Literal["llmos", "core"]


@dataclass(frozen=True)
class UnresolvedLink:
    referrer: str
    target: str


@dataclass(frozen=True)
class SchemaViolation:
    path: str
    message: str


@dataclass(frozen=True)
class VaultHealth:
    orphans: list[str]
    dead_ends: list[str]
    unresolved_links: list[UnresolvedLink]
    schema_violations: list[SchemaViolation]
    stale_inbox: list[str]
    qmd_gaps: list[str]
    qmd_notice: str | None

    @property
    def is_clean(self) -> bool:
        return not (
            self.orphans
            or self.dead_ends
            or self.unresolved_links
            or self.schema_violations
            or self.stale_inbox
            or self.qmd_gaps
        )


def vault_health(
    vault_root: Path,
    *,
    profile: Profile = "llmos",
    qmd_collection: str = "llmos",
    stale_after_days: int = 14,
    today: date | None = None,
) -> VaultHealth:
    """Aggregate vault hygiene into one report: orphans, dead-ends, unresolved
    wikilinks, schema violations, stale inbox items, and qmd index gaps.

    Use when starting a vault-maintenance pass -- e.g. the nightly cron --
    to see every hygiene defect in one headless call. Each section
    degrades independently: a missing qmd binary reports a notice and an
    empty qmd-gap list, it never fails the whole report. Works with Obsidian
    closed; everything is read straight off disk.
    Do NOT use when you only need one relation on one note -- `get_neighbors`
    is cheaper and does not walk the whole vault.

    Example output:
        VaultHealth(orphans=['gamma'], dead_ends=['beta'],
            unresolved_links=[UnresolvedLink(referrer='alpha', target='ghost')],
            schema_violations=[SchemaViolation(path='knowledge/thing.md',
                message="invalid status 'nearly-done'")],
            stale_inbox=['inbox/old-capture.md'], qmd_gaps=[], qmd_notice=None)

    Example invocation:
        from llmos_vault.health import vault_health
        vault_health(Path("/path/to/vault"), profile="llmos")

    Args:
        vault_root: Root directory of the vault to check.
        profile: "llmos" runs the llmOS schema-violation checks; "core"
            skips them for a plain vault (e.g. xbrain) with no schema layer.
        qmd_collection: qmd collection name to check for index gaps.
        stale_after_days: Age in days after which an inbox item counts as stale.
        today: Date to measure inbox staleness against; defaults to today.
    """
    index = build_index(vault_root)
    orphans, dead_ends = _orphans_and_dead_ends(index)
    qmd_gaps, qmd_notice = _qmd_gaps(vault_root, index, qmd_collection)
    return VaultHealth(
        orphans=orphans,
        dead_ends=dead_ends,
        unresolved_links=_unresolved_links(index),
        schema_violations=_schema_violations(vault_root, profile),
        stale_inbox=_stale_inbox(vault_root, index, stale_after_days, today or date.today()),
        qmd_gaps=qmd_gaps,
        qmd_notice=qmd_notice,
    )


def _orphans_and_dead_ends(index: VaultIndex) -> tuple[list[str], list[str]]:
    orphans = [path.stem for path in index.paths if not _backlinks(index, path)]
    dead_ends = [path.stem for path in index.paths if not _linked_targets(path)]
    return sorted(orphans), sorted(dead_ends)


def _unresolved_links(index: VaultIndex) -> list[UnresolvedLink]:
    links = [
        UnresolvedLink(referrer=path.stem, target=target)
        for path in index.paths
        for target in _outgoing(index, path)[1]
    ]
    return sorted(links, key=lambda link: (link.referrer, link.target))


def _schema_violations(vault_root: Path, profile: Profile) -> list[SchemaViolation]:
    if profile != "llmos":
        return []
    errors, _ = collect_errors(vault_root)
    violations = []
    for error in errors:
        path, _, message = error.partition(": ")
        violations.append(SchemaViolation(path=path, message=message))
    return violations


def _stale_inbox(
    vault_root: Path, index: VaultIndex, stale_after_days: int, today: date
) -> list[str]:
    stale = []
    for path in index.paths:
        relative = path.relative_to(vault_root)
        if relative.parts[0] != "inbox":
            continue
        properties, _ = read_frontmatter(path)
        created = properties.get("created")
        if not isinstance(created, str):
            stale.append(str(relative))
            continue
        try:
            created_date = date.fromisoformat(created)
        except ValueError:
            stale.append(str(relative))
            continue
        if (today - created_date).days >= stale_after_days:
            stale.append(str(relative))
    return sorted(stale)


def _qmd_indexed_paths(collection: str) -> set[str] | None:
    try:
        result = subprocess.run(
            ["qmd", "ls", collection], capture_output=True, text=True, timeout=30, check=False
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    prefix = f"qmd://{collection}/"
    paths = set()
    for line in result.stdout.splitlines():
        index = line.find(prefix)
        if index == -1:
            continue
        paths.add(line[index + len(prefix) :].strip())
    return paths


def _qmd_gaps(
    vault_root: Path, index: VaultIndex, collection: str
) -> tuple[list[str], str | None]:
    indexed = _qmd_indexed_paths(collection)
    if indexed is None:
        return [], (
            f"qmd unavailable or collection '{collection}' not found; "
            "qmd-gap section skipped"
        )
    vault_paths = {str(path.relative_to(vault_root)) for path in index.paths}
    return sorted(vault_paths - indexed), None


def summary(report: VaultHealth) -> str:
    """Render a `VaultHealth` report as a readable text summary with
    per-section counts.

    Use when rendering the CLI's default (non-`--json`) output -- a human
    skimming a cron log wants counts and a short list, not a raw dataclass
    repr.
    Do NOT use when the caller needs to parse the result -- use `--json` /
    `dataclasses.asdict` instead.

    Example output:
        orphans (1): gamma
        dead-ends (1): beta
        unresolved links (1): alpha -> ghost
        schema violations (1): knowledge/thing.md: invalid status 'nearly-done'
        stale inbox (1): inbox/old-capture.md
        qmd gaps (0): none
        qmd notice: qmd unavailable or collection 'llmos' not found; qmd-gap section skipped

    Example invocation:
        from llmos_vault.health import summary, vault_health
        print(summary(vault_health(Path("/path/to/vault"))))

    Args:
        report: A `VaultHealth` report from `vault_health`.
    """
    lines = [
        f"orphans ({len(report.orphans)}): {', '.join(report.orphans) or 'none'}",
        f"dead-ends ({len(report.dead_ends)}): {', '.join(report.dead_ends) or 'none'}",
        f"unresolved links ({len(report.unresolved_links)}): "
        + (
            ", ".join(f"{link.referrer} -> {link.target}" for link in report.unresolved_links)
            or "none"
        ),
        f"schema violations ({len(report.schema_violations)}): "
        + (
            ", ".join(f"{v.path}: {v.message}" for v in report.schema_violations)
            or "none"
        ),
        f"stale inbox ({len(report.stale_inbox)}): {', '.join(report.stale_inbox) or 'none'}",
        f"qmd gaps ({len(report.qmd_gaps)}): {', '.join(report.qmd_gaps) or 'none'}",
    ]
    if report.qmd_notice:
        lines.append(f"qmd notice: {report.qmd_notice}")
    return "\n".join(lines)
