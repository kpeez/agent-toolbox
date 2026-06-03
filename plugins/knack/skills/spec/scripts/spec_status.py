#!/usr/bin/env python3
"""Generate a project-level spec status overview."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

GENERATED_HEADER = "# Specs Status\n<!-- generated; do not edit by hand -->\n"


def read_description(status_path: Path) -> str:
    text = status_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return ""
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return ""
    for line in lines[1:end]:
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    return ""


def discover_specs(specs_dir: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    active: list[tuple[str, str]] = []
    archived: list[tuple[str, str]] = []

    for child in sorted(specs_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        status_path = child / "STATUS.md"
        if status_path.exists():
            active.append((child.name, read_description(status_path)))

    archive_dir = specs_dir / "_archive"
    if archive_dir.is_dir():
        for child in sorted(archive_dir.iterdir()):
            if not child.is_dir():
                continue
            status_path = child / "STATUS.md"
            if status_path.exists():
                archived.append((child.name, read_description(status_path)))

    return active, archived


def render_section(title: str, specs: list[tuple[str, str]], prefix: str = "") -> str:
    parts = [f"\n## {title}\n\n"]
    if not specs:
        return "".join(parts) + "_None._\n"
    for slug, description in specs:
        path = f"{prefix}{slug}/STATUS.md"
        suffix = f" — {description}" if description else ""
        parts.append(f"- [{slug}]({path}){suffix}\n")
    return "".join(parts)


def generate_overview(specs_dir: Path | str = Path("specs")) -> str:
    specs_path = Path(specs_dir)
    if not specs_path.is_dir():
        return ""
    active, archived = discover_specs(specs_path)
    return (
        GENERATED_HEADER
        + render_section("Active", active)
        + render_section("Archived", archived, prefix="_archive/")
    )


def write_overview(specs_dir: Path | str = Path("specs")) -> bool:
    specs_path = Path(specs_dir)
    overview = generate_overview(specs_path)
    if not overview:
        return False
    (specs_path / "STATUS.md").write_text(overview, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--specs-dir", default="specs")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    specs_dir = Path(args.specs_dir)

    if args.write:
        wrote = write_overview(specs_dir)
        if wrote and not args.quiet:
            print(f"Wrote {specs_dir / 'STATUS.md'}")
        return 0

    overview = generate_overview(specs_dir)
    if overview:
        print(overview, end="")
    elif not args.quiet:
        print(f"No specs directory found at {specs_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
