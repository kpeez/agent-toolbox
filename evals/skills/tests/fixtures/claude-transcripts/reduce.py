#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Reduce a real Claude Code eval transcript to a small, scrubbed scorer fixture.

The reduction keeps every row, in order, with its type, attachment type, and chain links. It keeps
the message, tool call, tool result, and skill body fields that skill_eval.py reads. It drops the
other fields, shortens long strings outside skill bodies, and replaces private paths and the
session id. It replaces the local user name with "user". It stops when a home-folder path, the
user name, or an email address is left.
"""

import argparse
import json
import re
from pathlib import Path

PLUGIN_ROOT = "@PLUGIN_ROOT@"
SESSION_ID = "00000000-0000-4000-8000-000000000000"
CHAIN_KEYS = (
    "type",
    "uuid",
    "parentUuid",
    "isSidechain",
    "agentId",
    "sessionId",
    "version",
)
MESSAGE_KEYS = ("isMeta", "sourceToolUseID", "toolUseResult")
SKILL_BODY_PREFIX = "Base directory for this skill: "
LONG = 2000
USER = re.compile(rf"\b{re.escape(Path.home().name)}\b")
PRIVATE = re.compile(rf"/Users/|/home/(?!user/)|[\w.+-]+@[\w-]+\.[\w.]+|{USER.pattern}")


def shorten(value):
    if isinstance(value, str):
        return value if len(value) <= LONG else value[:200] + " [reduced]"
    if isinstance(value, list):
        return [shorten(item) for item in value]
    if isinstance(value, dict):
        return {key: shorten(item) for key, item in value.items()}
    return value


def reduce_row(row):
    kept = {key: row[key] for key in CHAIN_KEYS if key in row}
    if row.get("type") == "attachment":
        kept["attachment"] = {"type": (row.get("attachment") or {}).get("type")}
    if row.get("type") in {"user", "assistant"}:
        kept.update({key: shorten(row[key]) for key in MESSAGE_KEYS if key in row})
        message = row.get("message") or {}
        content = message.get("content")
        if isinstance(content, list):
            content = [
                {"type": "thinking"}
                if block.get("type") == "thinking"
                else block
                if str(block.get("text", "")).startswith(SKILL_BODY_PREFIX)
                else shorten(block)
                for block in content
            ]
        kept["message"] = {
            key: message[key] for key in ("id", "role") if key in message
        } | {"content": content}
    return kept


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--stream", type=Path, required=True)
    parser.add_argument(
        "--plugin-root", required=True, help="the --plugin-dir the session loaded"
    )
    parser.add_argument(
        "--workspace", required=True, help="the session's working folder"
    )
    parser.add_argument(
        "--sandbox",
        help="a folder that holds the workspace, such as a plugin-eval sandbox",
    )
    parser.add_argument(
        "--skill",
        action="append",
        required=True,
        metavar="PLUGIN:NAME=SKILL.md",
        help="a frozen SKILL.md that a Skill call loaded",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    raw = args.transcript.read_text(encoding="utf-8")
    session_id = json.loads(raw.splitlines()[-1])["sessionId"]
    replacements = [(args.plugin_root, PLUGIN_ROOT), (args.workspace, "/workspace"),
                    (args.sandbox, "/sandbox"), (session_id, SESSION_ID)]

    def scrub(text):
        for old, new in replacements:
            text = text.replace(old, new) if old else text
        return USER.sub("user", text)

    def write(name, rows):
        text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
        if found := PRIVATE.search(text):
            raise SystemExit(f"private text left: {text[max(0, found.start() - 60):found.end() + 60]!r}")
        (args.out / name).write_text(text, encoding="utf-8")

    stream = [row for row in map(json.loads, scrub(args.stream.read_text(encoding="utf-8")).splitlines())
              if row.get("type") == "result"]
    skills = {}
    for spec in args.skill:
        skill, path = spec.split("=", 1)
        skills[skill] = Path(path).read_text(encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    write("transcript.jsonl", [reduce_row(json.loads(line)) for line in scrub(raw).splitlines()])
    write("stream.jsonl", [{key: stream[-1][key] for key in ("type", "subtype", "is_error", "session_id")}])
    (args.out / "skills.json").write_text(json.dumps(skills, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
