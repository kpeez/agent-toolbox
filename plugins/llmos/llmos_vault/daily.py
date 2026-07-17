"""llmOS-profile daily-note helpers encoding the vault's daily contract (see
`agents/references/schema.md`, "Daily note contract") so no agent re-derives
it by hand: creating today's note from the vault's daily template with the
Reviews/no-project/bare-date-title properties, appending prose to the
agent-owned `## Thoughts` section, and reading back the last N days
headlessly for weekly-synthesis work. `## Projects` and its
`<!-- llmos-activity:start/end -->` markers are machine-owned -- nothing here
reads or writes inside them, and `append_thought` refuses outright rather
than risk it. This module is llmOS-profile-specific, like `schema.py`; a
plain vault (e.g. xbrain) has no daily-note contract and never calls it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from llmos_vault import frontmatter, mutations
from llmos_vault.notes import Note, read_note

DAILY_DIR = "reviews/daily"
DAILY_TEMPLATE = "daily-note"
THOUGHTS_HEADING = "## Thoughts"
MARKER_START = "<!-- llmos-activity:start -->"
MARKER_END = "<!-- llmos-activity:end -->"


class MachineOwnedBlock(RuntimeError):
    """Raised when a write would land inside the machine-owned llmos-activity block."""


def _relative_path(day: date) -> str:
    return f"{DAILY_DIR}/{day.isoformat()}.md"


def _insert_under_heading(text: str, heading: str, addition: str) -> str:
    if heading not in text:
        raise ValueError(f"note has no '{heading}' heading")
    start = text.index(heading) + len(heading)
    rest = text[start:]
    next_heading = rest.find("\n## ")
    section, tail = (rest, "") if next_heading == -1 else (rest[:next_heading], rest[next_heading:])
    new_section = section.rstrip("\n") + "\n\n" + addition.strip() + "\n"
    return text[:start] + new_section + tail


def get_or_create_daily(vault_root: Path, *, today: date | None = None) -> Note:
    """Return the day's daily note, creating it from the vault's daily
    template with the contract properties (Reviews category, no project,
    bare date title) only when it does not already exist on disk.

    Use when an agent needs today's (or a given day's) daily note before
    appending a thought or checking its properties -- the sanctioned way to
    get a contract-compliant note without hand-writing frontmatter. Requires
    Obsidian to be running only when the note is actually missing; an
    existing note is read straight off disk and returned unmodified.
    Do NOT use when you only need to read days that may or may not exist
    without creating any of them -- use `read_recent_dailies`, which skips
    absent days silently instead of creating them.

    Example output:
        Note(path=PosixPath('/vault/reviews/daily/2026-07-17.md'), name='2026-07-17',
             properties={'status': 'active', 'created': '2026-07-17',
             'updated': '2026-07-17', 'categories': ['[[Reviews]]']}, body='# 2026-07-17\\n...')

    Example invocation:
        from llmos_vault.daily import get_or_create_daily
        get_or_create_daily(vault_root)

    Args:
        vault_root: Root directory of the llmOS vault.
        today: Date to resolve the daily note for; defaults to today.

    Raises:
        ObsidianNotRunning: the note is missing and obsidian-cli could not
            reach a running app.
    """
    relative = _relative_path(today or date.today())
    if not (vault_root / relative).exists():
        mutations.create_note(vault_root, relative, template=DAILY_TEMPLATE)
    return read_note(vault_root, relative)


def append_thought(vault_root: Path, text: str, *, today: date | None = None) -> str:
    """Append `text` as a new paragraph under the daily note's `## Thoughts`
    heading, creating the day's note first if it does not exist yet.

    Use when an agent has a lesson, an open question, or a decision not yet
    worth an ADR to record for the day -- the sanctioned way to write to
    `## Thoughts` without risking the machine-owned `## Projects` block.
    Everything from the `<!-- llmos-activity:start -->` marker onward is
    carried through byte-identical; only the `## Thoughts` section changes.
    Do NOT use when `text` itself contains `llmos-activity` marker syntax, or
    when the note has no marker pair to protect -- both raise
    `MachineOwnedBlock` rather than risk writing into the digest's block.

    Example output:
        'Created: reviews/daily/2026-07-17.md\\n'

    Example invocation:
        from llmos_vault.daily import append_thought
        append_thought(vault_root, "TIL obsidian-cli has no heading-targeted append.")

    Args:
        vault_root: Root directory of the llmOS vault.
        text: Thought prose to append under `## Thoughts`.
        today: Date to resolve the daily note for; defaults to today.

    Raises:
        MachineOwnedBlock: `text` contains marker syntax, or the note has no
            `llmos-activity` marker pair to protect.
        ObsidianNotRunning: obsidian-cli could not reach a running app.
    """
    if MARKER_START in text or MARKER_END in text:
        raise MachineOwnedBlock(
            "refusing to write llmos-activity marker syntax into ## Thoughts -- "
            "that block is machine-owned"
        )
    note = get_or_create_daily(vault_root, today=today)
    before, marker_sep, after_start = note.body.partition(MARKER_START)
    if not marker_sep:
        raise MachineOwnedBlock(
            f"{note.path} has no llmos-activity markers -- refusing to append blind"
        )
    updated_before = _insert_under_heading(before, THOUGHTS_HEADING, text)
    new_body = updated_before + marker_sep + after_start
    relative = str(note.path.relative_to(vault_root))
    return mutations.overwrite_note(
        vault_root, relative, frontmatter.serialize(note.properties, new_body)
    )


def read_recent_dailies(vault_root: Path, n: int) -> list[Note]:
    """Read the last `n` daily notes headlessly, most recent first.

    Use when a weekly-synthesis pass needs the last N days' content and
    frontmatter in one call -- ISO-dated filenames sort chronologically, so
    no per-note date parsing is needed. Works with Obsidian closed.
    Do NOT use when you need one specific day created if it is missing --
    use `get_or_create_daily` instead.

    Example output:
        [Note(path=PosixPath('/vault/reviews/daily/2026-07-17.md'), name='2026-07-17',
              properties={'categories': ['[[Reviews]]']}, body='# 2026-07-17\\n...'), ...]

    Example invocation:
        from llmos_vault.daily import read_recent_dailies
        read_recent_dailies(vault_root, 7)

    Args:
        vault_root: Root directory of the llmOS vault.
        n: Number of most recent daily notes to read.
    """
    daily_dir = vault_root / DAILY_DIR
    if not daily_dir.is_dir():
        return []
    paths = sorted(daily_dir.glob("*.md"), reverse=True)[:n]
    return [read_note(vault_root, str(path.relative_to(vault_root))) for path in paths]
