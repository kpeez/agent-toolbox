#!/usr/bin/env python3
"""Append one spec-completion receipt to a project's dated log.

A receipt has exactly two fields: `desc` (what the implemented spec does) and
`info` (backlinks to the spec, plans, local issues, PRs). The agent names
itself in the entry header; nothing stamps note frontmatter. Receipts always
route to `projects/<slug>/logs/YYYY-MM-DD-<slug>.md`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from datetime import date, datetime
from pathlib import Path

from vault_root import vault_root

CANONICAL_AGENTS = {"claude", "codex", "gemini", "human"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, choices=sorted(CANONICAL_AGENTS))
    parser.add_argument("--desc", required=True, help="What the implemented spec does.")
    parser.add_argument(
        "--info",
        action="append",
        default=[],
        help="Backlink to the spec, a plan, a local issue, or a PR (repeatable).",
    )
    parser.add_argument(
        "--project", help="Project slug; inferred from the working repo when omitted."
    )
    parser.add_argument(
        "--receipt-id", required=True, help="Stable id for idempotent re-runs."
    )
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Vault root; resolved via the shared resolver when omitted.",
    )
    return parser.parse_args()


SLUG_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]*")


def project_slug(value: str) -> str:
    if not SLUG_PATTERN.fullmatch(value):
        raise SystemExit(f"invalid project slug: {value}")
    return value


def repo_project(cwd: Path, root: Path) -> str | None:
    """Map the working git repo's basename to a vault project slug, or None."""
    result = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    slug = Path(result.stdout.strip()).name.lower()
    if not SLUG_PATTERN.fullmatch(slug):
        return None
    if not (root / "projects" / slug / f"{slug}.md").is_file():
        return None
    return slug


def project_title(root: Path, slug: str) -> str:
    note = root / "projects" / slug / f"{slug}.md"
    heading = re.search(r"^#\s+(.+)$", note.read_text(encoding="utf-8"), re.MULTILINE)
    if not heading:
        raise SystemExit(f"project landing note lacks a title: {note}")
    return heading.group(1).strip()


def log_header(date_value: str, agent: str, slug: str, title: str) -> str:
    return (
        "---\n"
        "status: active\n"
        "authors:\n"
        f"  - {agent}\n"
        f"created: {date_value}\n"
        f"updated: {date_value}\n"
        "categories:\n"
        '  - "[[Project Logs]]"\n'
        "project:\n"
        f'  - "[[projects/{slug}/{slug}|{title}]]"\n'
        "---\n\n"
        f"# {title} daily log — {date_value}\n\n"
        f"Daily review: [[{date_value}]]\n\n"
        "## Receipts\n"
    )


def main() -> None:
    args = parse_args()
    root = args.root.expanduser().resolve() if args.root else vault_root()

    slug = (
        project_slug(args.project) if args.project else repo_project(Path.cwd(), root)
    )
    if not slug:
        raise SystemExit(
            "Failed to infer project from repository. Specify --project <slug>."
        )

    log_path = root / "projects" / slug / "logs" / f"{args.date}-{slug}.md"
    marker = f"<!-- llmos-receipt:{args.agent}:{args.receipt_id}:{slug} -->"

    if not log_path.exists():
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(
            log_header(args.date, args.agent, slug, project_title(root, slug)),
            encoding="utf-8",
        )

    current = log_path.read_text(encoding="utf-8")
    if marker in current:
        print(log_path)
        return

    info = ", ".join(args.info) if args.info else "none"
    entry = (
        f"\n### {datetime.now().strftime('%H:%M')} | {args.agent}\n"
        f"{marker}\n"
        f"- desc: {args.desc}\n"
        f"- info: {info}\n"
    )
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(entry)
    print(log_path)


if __name__ == "__main__":
    main()
