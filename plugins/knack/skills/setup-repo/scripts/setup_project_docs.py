#!/usr/bin/env python3
"""Establish the llmOS-backed project documentation topology for a repository."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


IGNORE_PATHS = ("specs", "adrs", "docs/specs", "docs/adrs")


@dataclass(frozen=True)
class Migration:
    source: Path
    destination: Path


class CollisionError(Exception):
    def __init__(self, collisions: list[str], *, worktree: bool = False) -> None:
        self.collisions = collisions
        self.worktree = worktree


def exists(path: Path) -> bool:
    return path.is_symlink() or path.exists()


def entry_type(path: Path) -> str:
    if path.is_symlink():
        return "symlink"
    if path.is_file():
        return "file"
    if path.is_dir():
        return "directory"
    return "unsupported filesystem entry"


def entry_identity(path: Path) -> tuple[str, bytes | str | None]:
    kind = entry_type(path)
    if kind == "file":
        return kind, path.read_bytes()
    if kind == "symlink":
        return kind, os.readlink(path)
    return kind, None


def linked_project(path: Path, llmos: Path) -> str | None:
    if not path.is_symlink():
        return None
    try:
        relative = path.resolve(strict=False).relative_to(
            (llmos / "projects").resolve(strict=False)
        )
    except (RuntimeError, ValueError):
        return None
    return relative.parts[0] if relative.parts else None


def walk(source: Path) -> list[tuple[Path, str]]:
    entries: list[tuple[Path, str]] = []

    def visit(directory: Path) -> None:
        for path in sorted(directory.iterdir(), key=lambda item: item.name):
            relative = path.relative_to(source)
            kind = entry_type(path)
            entries.append((relative, kind))
            if kind == "directory":
                visit(path)

    visit(source)
    return entries


def desired_gitignore(original: str) -> str:
    lines = [line for line in original.splitlines() if line != "docs/adr"]
    for path in IGNORE_PATHS:
        if path not in lines:
            lines.append(path)
    return "\n".join(lines) + "\n"


def preflight(
    repo: Path,
    llmos: Path,
    project: str,
    *,
    worktree: bool,
) -> tuple[Path, Path, list[Migration]]:
    collisions: list[str] = []
    project_root = llmos / "projects" / project
    canonical_docs = project_root / "docs"
    canonical_specs = canonical_docs / "specs"
    canonical_adrs = canonical_docs / "adrs"

    if not repo.is_dir() or repo.is_symlink():
        collisions.append(f"{repo}: repository root must be a real directory")

    for path in (
        llmos,
        llmos / "projects",
        project_root,
        canonical_docs,
        canonical_specs,
        canonical_adrs,
    ):
        if exists(path) and (path.is_symlink() or not path.is_dir()):
            collisions.append(f"{path}: canonical path must be a real directory")

    docs = repo / "docs"
    if exists(docs) and (docs.is_symlink() or not docs.is_dir()):
        collisions.append(f"{docs}: documentation parent must be a real directory")

    gitignore = repo / ".gitignore"
    if not worktree:
        if gitignore.is_symlink():
            collisions.append(f"{gitignore}: ignore policy must be a regular file")
        elif gitignore.exists() and not gitignore.is_file():
            collisions.append(f"{gitignore}: ignore policy must be a regular file")
        elif gitignore.is_file():
            try:
                original_gitignore = gitignore.read_text()
            except (OSError, UnicodeError) as error:
                collisions.append(f"{gitignore}: cannot read ignore policy: {error}")
            else:
                if desired_gitignore(
                    original_gitignore
                ) != original_gitignore and not os.access(gitignore, os.W_OK):
                    collisions.append(f"{gitignore}: cannot update ignore policy")
        elif repo.is_dir() and not os.access(repo, os.W_OK):
            collisions.append(f"{gitignore}: cannot create ignore policy")

    links = {
        repo / "docs/specs": str(canonical_specs),
        repo / "docs/adrs": str(canonical_adrs),
        repo / "specs": "docs/specs",
        repo / "adrs": "docs/adrs",
    }
    for path in links:
        if exists(path) and not path.is_symlink():
            collisions.append(
                f"{path}: expected a symlink or an absent path, found {entry_type(path)}"
            )

    legacy_repo_adr = repo / "docs/adr"
    for path in (*links, legacy_repo_adr):
        owner = linked_project(path, llmos)
        if owner and owner != project:
            collisions.append(
                f"{path}: symlink points into llmOS project {owner!r}, expected {project!r}"
            )

    migrations = [
        Migration(project_root / "specs", canonical_specs),
        Migration(project_root / "adr", canonical_adrs),
        Migration(legacy_repo_adr, canonical_adrs),
    ]

    for migration in migrations:
        if not exists(migration.source):
            continue
        kind = entry_type(migration.source)
        if worktree and kind != "symlink":
            collisions.append(f"{migration.source}: legacy {kind} requires migration")
        elif (
            not worktree
            and kind != "directory"
            and not (migration.source == legacy_repo_adr and kind == "symlink")
        ):
            collisions.append(
                f"{migration.source}: legacy source must be a real directory, found {kind}"
            )

    if not worktree:
        proposed: dict[Path, tuple[Path, tuple[str, bytes | str | None]]] = {}
        for migration in migrations:
            if not migration.source.is_dir() or migration.source.is_symlink():
                continue
            for relative, kind in walk(migration.source):
                source = migration.source / relative
                destination = migration.destination / relative
                if kind == "unsupported filesystem entry":
                    collisions.append(f"{source}: unsupported legacy content")
                    continue
                identity = entry_identity(source)
                previous = proposed.get(destination)
                if previous and previous[1] != identity:
                    collisions.append(
                        f"{destination}: non-identical legacy content from "
                        f"{previous[0]} and {source}"
                    )
                else:
                    proposed[destination] = (source, identity)
                if exists(destination) and entry_identity(destination) != identity:
                    collisions.append(
                        f"{destination}: non-identical legacy content already exists"
                    )

    if collisions:
        raise CollisionError(collisions, worktree=worktree)
    return canonical_specs, canonical_adrs, migrations


def migrate(source: Path, destination: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        return
    entries = walk(source)
    destination.mkdir(parents=True, exist_ok=True)
    for relative, kind in entries:
        if kind == "directory":
            (destination / relative).mkdir(parents=True, exist_ok=True)
    for relative, kind in entries:
        if kind == "directory":
            continue
        old = source / relative
        new = destination / relative
        new.parent.mkdir(parents=True, exist_ok=True)
        if exists(new):
            old.unlink()
        else:
            shutil.move(str(old), str(new))
    for relative, kind in reversed(entries):
        if kind == "directory":
            (source / relative).rmdir()
    source.rmdir()


def ensure_link(path: Path, target: str) -> None:
    if path.is_symlink() and os.readlink(path) == target:
        return
    if path.is_symlink():
        path.unlink()
    path.symlink_to(target)


def update_gitignore(repo: Path) -> None:
    gitignore = repo / ".gitignore"
    original = gitignore.read_text() if gitignore.exists() else ""
    updated = desired_gitignore(original)
    if updated != original:
        gitignore.write_text(updated)


def establish_topology(
    repo: Path,
    llmos: Path,
    project: str,
    *,
    worktree: bool,
) -> None:
    canonical_specs, canonical_adrs, migrations = preflight(
        repo, llmos, project, worktree=worktree
    )
    canonical_specs.mkdir(parents=True, exist_ok=True)
    canonical_adrs.mkdir(parents=True, exist_ok=True)

    legacy_repo_adr = repo / "docs/adr"
    if not worktree:
        for migration in migrations:
            migrate(migration.source, migration.destination)
    if legacy_repo_adr.is_symlink():
        legacy_repo_adr.unlink()

    (repo / "docs").mkdir(parents=True, exist_ok=True)
    ensure_link(repo / "docs/specs", str(canonical_specs))
    ensure_link(repo / "docs/adrs", str(canonical_adrs))
    ensure_link(repo / "specs", "docs/specs")
    ensure_link(repo / "adrs", "docs/adrs")
    if not worktree:
        update_gitignore(repo)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Establish collision-safe llmOS project documentation links."
    )
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--llmos-root", type=Path, required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument(
        "--worktree",
        action="store_true",
        help="create safe links only; refuse any legacy content that needs migration",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if Path(args.project).name != args.project or args.project in {"", ".", ".."}:
        print(
            "project docs setup aborted: --project must be one path segment",
            file=sys.stderr,
        )
        return 2
    repo = args.repo_root.absolute()
    llmos = args.llmos_root.absolute()
    try:
        establish_topology(repo, llmos, args.project, worktree=args.worktree)
    except CollisionError as error:
        print(
            "project docs setup aborted: collisions detected before mutation:",
            file=sys.stderr,
        )
        for collision in error.collisions:
            print(f"- {collision}", file=sys.stderr)
        if error.worktree:
            print(
                "Run /setup-repo in the main repository to migrate legacy content, then retry.",
                file=sys.stderr,
            )
        return 2
    print(f"project docs topology ready: {repo} -> {llmos / 'projects' / args.project}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
