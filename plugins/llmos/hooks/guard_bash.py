#!/usr/bin/env python3
"""PreToolUse guard for Bash: obsidian-cli targeting + vault-unsafe mv/rm.

Runs on every Bash call, so the fast path must stay fast and silent (spec
0014, Risks: guard latency/false positives): a cheap word-boundary-aware
pre-filter runs before any `shlex` parsing, and vault roots are only read
from disk once an actual `mv`/`git mv`/`rm` invocation is found -- never for
the common case of an unrelated command. Tokenizing uses `shlex.shlex(...,
punctuation_chars=True)` rather than `shlex.split` so shell operators
(`&&`, `;`, `|`, redirections) come out as their own tokens even when glued
to an adjacent word with no whitespace (`hi&&rm`), while quotes are still
respected. Redirection operators and their operand (`> file`, `2>&1`) are
stripped before mv/rm/obsidian-cli argument extraction -- a redirect target
is never one of their arguments.

Two independently-triggered rules, both denying via exit code 2 with the
message on stderr (the PreToolUse block contract) -- plain stdout here reaches
neither transcript nor model:

1. An `obsidian-cli` invocation of a note-operating verb (`read`, `delete`,
   `move`, ...) that names neither `file=` nor `path=` silently acts on
   whatever note is focused in the Obsidian app. Verbs with their own
   `active` flag (`aliases`, `properties`, `tags`, `tasks`) list vault-wide by
   default and are deliberately excluded -- omitting file/path there does not
   touch the active file, so denying would be a false positive.
2. Raw `mv`, `git mv`, or `rm` acting on a `.md` file resolved under any known
   vault root (llmOS root + Obsidian's registry, `llmos_vault.root`) orphans
   any wikilinks pointing at it; `obsidian-cli move`/`rename` rewrites them.

Hook entry scripts run under plain `python3` (no venv), so the plugin root
(parent of this file's directory) is put on `sys.path` before importing
`llmos_vault`. Any failure here -- missing vault config, a parse error --
must never block an unrelated Bash call, so `main` swallows every exception
and approves.
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

from llmos_vault.root import registered_vaults, vault_root  # noqa: E402

FAST_REJECT_RE = re.compile(r"\b(?:obsidian-cli|mv|rm)\b")
OPERATOR_TOKENS = frozenset({"&&", "||", ";", "|"})
REDIRECT_OPERATORS = frozenset({">", ">>", "<", "<<", "&>", "&>>", ">&", "<&"})

# obsidian-cli verbs where an omitted file=/path= silently falls back to the
# active file in the app (per `obsidian-cli help`). Verbs with an explicit
# `active` flag (aliases, properties, tags, tasks) default to a vault-wide
# listing instead and are excluded on purpose, as are verbs with alternate
# targeting mechanisms (`task` via `ref=`, `bookmark` via `folder=`/`search=`)
# where file=/path= absence alone is not a reliable signal.
NOTE_TARGETING_VERBS = frozenset(
    {
        "read",
        "append",
        "prepend",
        "delete",
        "move",
        "rename",
        "backlinks",
        "links",
        "outline",
        "file",
        "wordcount",
        "property:read",
        "property:set",
        "property:remove",
        "diff",
        "history",
        "history:read",
        "history:restore",
        "sync:read",
        "sync:restore",
        "sync:history",
    }
)


def _read_payload() -> dict:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _basename(token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _tokenize(command: str) -> list[str] | None:
    """Tokenize `command` with shell separators (`&&`, `;`, `|`, ...) and
    redirection operators (`>`, `2>`, ...) as their own tokens -- even when
    glued to an adjacent word with no whitespace (`hi&&rm`) -- while still
    respecting quotes, unlike a plain string-level split."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _split_subcommands(tokens: list[str]) -> list[list[str]]:
    subcommands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in OPERATOR_TOKENS:
            if current:
                subcommands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        subcommands.append(current)
    return subcommands


def _strip_redirections(tokens: list[str]) -> list[str]:
    """Drop every redirection operator and its operand (`> file`, `2>&1`)
    from `tokens` -- a redirection target is never an mv/rm/obsidian-cli
    argument, just where the shell sends output."""
    stripped: list[str] = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in REDIRECT_OPERATORS:
            skip_next = True
            continue
        stripped.append(token)
    return stripped


def _obsidian_cli_verb(tokens: list[str]) -> str | None:
    if not tokens or _basename(tokens[0]) != "obsidian-cli":
        return None
    for token in tokens[1:]:
        if token.startswith("vault=") or token.startswith("-"):
            continue
        return token
    return None


def _check_obsidian_cli(tokens: list[str]) -> str | None:
    verb = _obsidian_cli_verb(tokens)
    if verb is None or verb not in NOTE_TARGETING_VERBS:
        return None
    has_target = any(token.startswith(("file=", "path=")) for token in tokens)
    if has_target:
        return None
    return (
        f"obsidian-cli '{verb}' names no file= or path=: it will silently act on "
        "whatever note is currently focused in the Obsidian app. Pass "
        "file=<name> (resolves like a wikilink) or path=<exact/path.md> to target "
        "the note explicitly."
    )


def _mv_rm_args(tokens: list[str]) -> list[str] | None:
    if not tokens:
        return None
    name = _basename(tokens[0])
    if name in ("mv", "rm"):
        rest = tokens[1:]
    elif name == "git" and len(tokens) > 1 and tokens[1] == "mv":
        rest = tokens[2:]
    else:
        return None
    return [token for token in rest if not token.startswith("-")]


def _known_vault_roots() -> list[Path]:
    """Every known vault root, resolved (ADR-0002) to match the resolved mv/rm
    target -- an unresolved root (e.g. a symlinked tmp or iCloud path) would
    never match a resolved argument otherwise.
    """
    roots: list[Path] = []
    try:
        roots.append(vault_root())
    except SystemExit:
        pass
    try:
        roots.extend(registered_vaults())
    except SystemExit:
        pass
    seen: set[Path] = set()
    unique: list[Path] = []
    for root in roots:
        resolved = root.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _check_vault_mv_rm(
    tokens: list[str],
    args: list[str],
    cwd: Path,
    vault_roots: list[Path],
    raw_command: str,
) -> str | None:
    prog = "git mv" if _basename(tokens[0]) == "git" else _basename(tokens[0])
    for arg in args:
        path = Path(arg)
        if not path.is_absolute():
            path = cwd / path
        path = path.resolve()
        if path.suffix.lower() != ".md":
            continue
        if any(path == root or root in path.parents for root in vault_roots):
            return (
                f"'{raw_command}' touches a vault note ({path}) with raw {prog}: this "
                "orphans any wikilinks pointing at it. Use `obsidian-cli move "
                "file=<name> to=<dest>` (or `obsidian-cli rename`) so backlinks get "
                "rewritten."
            )
    return None


def check_command(command: str, cwd: str) -> str | None:
    """The stderr deny message for `command`, or None to approve."""
    if not FAST_REJECT_RE.search(command):
        return None
    tokens = _tokenize(command)
    if tokens is None:
        return None

    subcommands = [_strip_redirections(sub) for sub in _split_subcommands(tokens)]

    for sub in subcommands:
        message = _check_obsidian_cli(sub)
        if message:
            return message

    mv_rm_subs = [(sub, args) for sub in subcommands if (args := _mv_rm_args(sub)) is not None]
    if not mv_rm_subs:
        return None

    vault_roots = _known_vault_roots()
    if not vault_roots:
        return None
    resolved_cwd = Path(cwd or ".").resolve()
    for sub, args in mv_rm_subs:
        message = _check_vault_mv_rm(sub, args, resolved_cwd, vault_roots, command)
        if message:
            return message
    return None


def main() -> None:
    data = _read_payload()
    command = (data.get("tool_input") or {}).get("command")
    if not command:
        return
    try:
        message = check_command(command, data.get("cwd") or ".")
    except Exception:
        return  # hook failure must never block the tool call
    if message:
        print(message, file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
