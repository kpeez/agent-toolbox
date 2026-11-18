#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Blinded relevant-action labeler for Claude Code skill-eval transcripts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import skill_eval as se

PROMPT_INSTRUCTIONS = (
    "Here is a user's request to a coding agent, a description of the first action "
    "that counts as doing the requested work, and the agent's tool calls in order. "
    "Reply with the tool_use_id of the first call that starts that action, or none "
    "if no call does."
)
# A bare system prompt keeps the labeler blind to the host: no CLAUDE.md, plugin hooks, or skill listings.
LABELER_SYSTEM_PROMPT = "You label coding-agent transcripts. Answer only through the structured output."
PROMPT_SHA256 = se.digest((LABELER_SYSTEM_PROMPT + "\n\n" + PROMPT_INSTRUCTIONS).encode("utf-8"))
TARGET_KEYS = ("file_path", "pattern", "path", "command")
PATH_KEYS = ("file_path", "path", "notebook_path")
MAX_TARGET_CHARS = 300


def load_case(case_id: str, corpus_path: Path = se.DATASET) -> dict:
    cases = se.read_cases(corpus_path)
    case = next((c for c in cases if c["id"] == case_id), None)
    if case is None:
        raise ValueError(f"unknown case: {case_id}")
    user_messages = [m["content"] for m in case["messages"] if m.get("role") == "user"]
    if not user_messages:
        raise ValueError(f"case {case_id} has no user message")
    return {
        "id": case["id"],
        "user_message": user_messages[-1],
        "relevant_action": case["relevant_action"],
    }


def _plugin_matchers(plugin_dirs: list[str | Path]) -> tuple[list[tuple[Path, Path, Path | None]], list[re.Pattern[str]]]:
    roots: list[tuple[Path, Path, Path | None]] = []
    bash_patterns: list[re.Pattern[str]] = []
    seen_bash: set[str] = set()
    for raw in plugin_dirs:
        raw_str = str(raw)
        abs_str = posixpath.normpath(os.path.abspath(raw_str))
        real_str = posixpath.normpath(os.path.realpath(raw_str))
        rel_root = None if os.path.isabs(raw_str) else Path(posixpath.normpath(raw_str))
        roots.append((Path(abs_str), Path(real_str), rel_root))
        for root_str in (abs_str, real_str):
            if root_str not in seen_bash:
                seen_bash.add(root_str)
                bash_patterns.append(re.compile(re.escape(root_str) + r"(?![\w.-])"))
    return roots, bash_patterns


def _path_in_plugin_dir(raw_path: str, roots: list[tuple[Path, Path, Path | None]]) -> bool:
    if os.path.isabs(raw_path):
        norm_p = Path(posixpath.normpath(raw_path))
        real_p = Path(os.path.realpath(raw_path))
        return any(norm_p.is_relative_to(norm_r) or real_p.is_relative_to(real_r) for norm_r, real_r, _ in roots)
    rel_p = Path(posixpath.normpath(raw_path))
    return any(rel_r is not None and rel_p.is_relative_to(rel_r) for _, _, rel_r in roots)


def _is_dropped_call(name: object, inp: object, roots: list[tuple[Path, Path, Path | None]], bash_patterns: list[re.Pattern[str]]) -> bool:
    if name == "Skill":
        return True
    if not isinstance(inp, dict):
        return False
    for key in PATH_KEYS:
        val = inp.get(key)
        if isinstance(val, str) and val and _path_in_plugin_dir(val, roots):
            return True
    if name == "Bash" and isinstance(inp.get("command"), str):
        command = inp["command"]
        if any(pattern.search(command) for pattern in bash_patterns):
            return True
    return False


def _call_target(inp: object) -> str:
    if isinstance(inp, dict):
        for key in TARGET_KEYS:
            val = inp.get(key)
            if isinstance(val, str) and val:
                return val[:MAX_TARGET_CHARS]
    return json.dumps(inp, separators=(",", ":"), sort_keys=True)[:MAX_TARGET_CHARS]


def build_view(
    transcript_path: Path,
    case_id: str,
    plugin_dirs: list[str | Path],
    corpus_path: Path = se.DATASET,
) -> dict:
    case = load_case(case_id, corpus_path)
    issues: list[str] = []
    rows = se.claude_lines(Path(transcript_path), str(transcript_path), issues)
    if not rows and issues:
        raise ValueError("; ".join(issues))
    root_rows = [
        (line, row)
        for line, row in rows
        if not row.get("isSidechain") and not row.get("agentId")
    ]
    sid = next(
        (row.get("sessionId") for _, row in root_rows if isinstance(row.get("sessionId"), str)),
        None,
    )
    session = se.claude_session(root_rows, str(transcript_path), sid, None, issues, hook_arm="hook-on")
    roots, bash_patterns = _plugin_matchers(plugin_dirs)
    tool_calls = []
    for tool_use_id, use in session["uses"].items():
        if not isinstance(tool_use_id, str) or not tool_use_id:
            raise ValueError(f"root tool_use missing string id at line {use['line']}")
        if _is_dropped_call(use["name"], use["input"], roots, bash_patterns):
            continue
        tool_calls.append({
            "tool_use_id": tool_use_id,
            "tool": use["name"],
            "target": _call_target(use["input"]),
        })
    return {
        "case": case["id"],
        "user_message": case["user_message"],
        "relevant_action": case["relevant_action"],
        "tool_calls": tool_calls,
    }


def build_prompt(view: dict) -> str:
    calls = "\n".join(
        f"{index}. {json.dumps(call, ensure_ascii=False)}"
        for index, call in enumerate(view["tool_calls"], 1)
    )
    return (
        f"{PROMPT_INSTRUCTIONS}\n\n"
        f"User request:\n{view['user_message']}\n\n"
        f"Relevant action:\n{view['relevant_action']}\n\n"
        f"Tool calls:\n{calls or '(none)'}\n"
    )


def output_schema(view: dict) -> dict:
    choices = [call["tool_use_id"] for call in view["tool_calls"]] + ["none"]
    return {
        "type": "object",
        "properties": {
            "tool_use_id": {"type": "string", "enum": choices},
        },
        "required": ["tool_use_id"],
        "additionalProperties": False,
    }


def claude_executable() -> str:
    override = os.environ.get("SKILL_EVAL_CLAUDE")
    if override:
        return override
    found = shutil.which("claude")
    if not found:
        raise ValueError("claude executable not found on PATH; set SKILL_EVAL_CLAUDE or install claude")
    return found


def label_transcript(
    transcript_path: Path,
    case_id: str,
    plugin_dirs: list[str | Path],
    model: str,
    corpus_path: Path = se.DATASET,
) -> dict:
    view = build_view(transcript_path, case_id, plugin_dirs, corpus_path)
    prompt = build_prompt(view)
    schema = json.dumps(output_schema(view))
    cmd = [
        claude_executable(),
        "-p",
        "--model",
        model,
        "--effort",
        "low",
        "--tools",
        "",
        "--no-session-persistence",
        "--restricted",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--system-prompt",
        LABELER_SYSTEM_PROMPT,
        "--output-format",
        "json",
        "--json-schema",
        schema,
    ]
    proc = subprocess.run(cmd, input=prompt, text=True, capture_output=True)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit status {proc.returncode}"
        raise ValueError(f"claude exited with {proc.returncode}: {detail}")
    try:
        payload = json.loads(proc.stdout)
    except ValueError as error:
        raise ValueError(f"malformed claude JSON reply: {error}") from error
    if not isinstance(payload, dict):
        raise ValueError("malformed claude JSON reply: expected an object")
    if payload.get("is_error") is True:
        raise ValueError(f"claude returned an error: {payload.get('result') or payload}")
    structured = payload.get("structured_output")
    if not isinstance(structured, dict):
        raise ValueError("claude reply missing structured_output object")
    tool_use_id = structured.get("tool_use_id")
    if not isinstance(tool_use_id, str):
        raise ValueError("structured_output missing string tool_use_id")
    valid_ids = {call["tool_use_id"] for call in view["tool_calls"]}
    if tool_use_id != "none" and tool_use_id not in valid_ids:
        raise ValueError(f"returned tool_use_id {tool_use_id!r} is not in the labeler view")
    raw_cost = payload.get("total_cost_usd")
    cost_usd = raw_cost if isinstance(raw_cost, (int, float)) and not isinstance(raw_cost, bool) else None
    return {
        "case": view["case"],
        "tool_use_id": tool_use_id,
        "model": model,
        "prompt_sha256": PROMPT_SHA256,
        "cost_usd": cost_usd,
    }


def _resolve_path(raw: str, base_dir: Path) -> Path:
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    candidate = base_dir / path
    return candidate if candidate.exists() else path


def load_labels(labels_path: Path) -> list[dict]:
    items: list[dict] = []
    base_dir = labels_path.resolve().parent
    for line_no, text in enumerate(labels_path.read_text(encoding="utf-8").splitlines(), 1):
        if not text.strip():
            continue
        try:
            row = json.loads(text)
        except ValueError as error:
            raise ValueError(f"{labels_path} line {line_no}: {error}") from error
        if not isinstance(row, dict):
            raise ValueError(f"{labels_path} line {line_no}: expected JSON object")
        for key in ("transcript", "case", "tool_use_id"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError(f"{labels_path} line {line_no}: missing string {key!r}")
        plugin_dirs = row.get("plugin_dirs")
        if not isinstance(plugin_dirs, list) or not all(isinstance(d, str) for d in plugin_dirs):
            raise ValueError(f"{labels_path} line {line_no}: plugin_dirs must be a list of strings")
        items.append({
            "transcript": _resolve_path(row["transcript"], base_dir),
            "case": row["case"],
            "plugin_dirs": [_resolve_path(d, base_dir) for d in plugin_dirs],
            "tool_use_id": row["tool_use_id"],
        })
    if not items:
        raise ValueError(f"labels file is empty: {labels_path}")
    return items


def calibrate(labels_path: Path, models: list[str], corpus_path: Path = se.DATASET) -> dict:
    items = load_labels(labels_path)
    total = len(items)
    results = []
    for model in models:
        correct = 0
        mismatches = []
        costs = []
        for item in items:
            labeled = label_transcript(
                item["transcript"],
                item["case"],
                item["plugin_dirs"],
                model,
                corpus_path,
            )
            got = labeled["tool_use_id"]
            expected = item["tool_use_id"]
            if got == expected:
                correct += 1
            else:
                mismatches.append({
                    "case": item["case"],
                    "expected": expected,
                    "got": got,
                })
            costs.append(labeled["cost_usd"])
        results.append({
            "model": model,
            "agreement": f"{correct}/{total}",
            "fraction": correct / total,
            "correct": correct,
            "total": total,
            "mismatches": mismatches,
            "cost_usd": sum(c for c in costs if c is not None) if any(c is not None for c in costs) else None,
        })
    return {
        "prompt_sha256": PROMPT_SHA256,
        "total": total,
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=se.DATASET)
    commands = parser.add_subparsers(dest="command", required=True)

    view_cmd = commands.add_parser("view", help="print the blinded labeler view as JSON")
    view_cmd.add_argument("--transcript", required=True, type=Path)
    view_cmd.add_argument("--case", required=True)
    view_cmd.add_argument("--plugin-dir", action="append", default=[], dest="plugin_dirs")

    label_cmd = commands.add_parser("label", help="label one transcript with claude -p")
    label_cmd.add_argument("--transcript", required=True, type=Path)
    label_cmd.add_argument("--case", required=True)
    label_cmd.add_argument("--plugin-dir", action="append", default=[], dest="plugin_dirs")
    label_cmd.add_argument("--model", required=True)

    cal_cmd = commands.add_parser("calibrate", help="measure exact agreement against hand labels")
    cal_cmd.add_argument("--labels", required=True, type=Path)
    cal_cmd.add_argument("--model", action="append", nargs="+", required=True)

    args = parser.parse_args()
    try:
        if args.command == "view":
            result = build_view(args.transcript, args.case, args.plugin_dirs, args.corpus)
        elif args.command == "label":
            result = label_transcript(args.transcript, args.case, args.plugin_dirs, args.model, args.corpus)
        else:
            models = [m for group in args.model for m in group]
            result = calibrate(args.labels, models, args.corpus)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"label-relevant-action: {error}\n")


if __name__ == "__main__":
    main()
