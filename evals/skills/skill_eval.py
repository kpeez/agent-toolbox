#!/usr/bin/env python3
"""Offline activation corpus materialization, evidence capture and scoring.

No provider invocation, network dependency, or user configuration mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TARGETS = {"swe:" + name for name in (
    "implement", "diagnose", "testing-code", "test-audit",
    "improve-codebase-architecture")}
COUNTS = {"natural": 4, "contextual": 2, "negative": 3, "explicit": 1}
# The swe consolidation merged these skills into a successor. The corpus keeps the old
# names so every arm runs byte-identical cases; a name the catalog lacks scores as its
# successor. On such a catalog, a case the merge makes meaningless is excluded.
SUCCESSORS = {"swe:test-audit": "swe:testing-code",
              "swe:improve-codebase-architecture": "swe:codebase-design"}
RUNTIME_FIELDS = {"model", "effort", "cli", "cli_version", "permissions", "tools",
                  "harness_deltas", "catalog_scope", "context_delivery"}
# Claude Code transcript shapes seen in the audited 2.1.296 probe traces (EVIDENCE.md).
# Anything else is coverage loss until a raw audit adds it here.
CLAUDE_LINE_TYPES = {"user", "assistant", "attachment", "system", "queue-operation",
                     "atis-latch", "last-prompt", "cost-state"}
CLAUDE_SYSTEM_SUBTYPES = {"stop_hook_summary"}
CLAUDE_ATTACHMENT_TYPES = {
    "advisor_tool", "agent_listing_delta", "command_permissions", "credential_org", "date",
    "deferred_tools_delta", "deferred_tools_record", "environment", "instructions",
    "mcp_instructions_delta", "model", "prompt_snapshot", "remote_session_change",
    "session_context", "skill_listing", "total_tokens_reminder"}
CLAUDE_BASE_PREFIX = "Base directory for this skill: "
# A delivered body that names another skill, or comes from outside the frozen catalog, breaks isolation.
CLAUDE_IDENTITY_LOSS = {"base directory outside the declared snapshot",
                        "requested skill differs from the delivered base directory"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def delivered_body(text):
    """SKILL.md as a Claude Skill call delivers it: frontmatter removed, leading newlines stripped."""
    lines = text.split("\n")
    if lines[0] != "---" or "---" not in lines[1:]:
        return None
    return "\n".join(lines[lines.index("---", 1) + 1:]).lstrip("\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def contained(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relative path: {relative}")
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"path leaves root: {relative}")
    return resolved


def catalog_skills():
    return {f"{p.parents[2].name}:{p.parent.name}" for p in (REPO / "plugins").glob("*/skills/*/SKILL.md")}


def resolver(skills):
    return lambda name: SUCCESSORS[name] if name not in skills and name in SUCCESSORS else name


def excluded(case, resolve):
    if set(map(resolve, case["expected_skills"])) & set(map(resolve, case["forbidden_skills"])):
        return "the merge makes it expect and forbid one skill"
    if case["category"] == "explicit" and resolve(case["target"]) != case["target"]:
        return "it names a skill that the merge removed"
    return None


def corpus(path=HERE / "cases.json"):
    data = read_json(path)
    if data.get("schema_version") != 1:
        raise ValueError("unsupported corpus schema")
    cases = data["cases"]
    ids = set()
    groups = defaultdict(Counter)
    skills = catalog_skills()
    resolve = resolver(skills)
    for case in cases:
        if not re.fullmatch(r"[A-Za-z0-9-]+", case["id"]) or case["id"] in ids:
            raise ValueError("invalid or duplicate case ID")
        ids.add(case["id"])
        if case["target"] not in TARGETS or case["category"] not in COUNTS:
            raise ValueError("unknown target/category")
        groups[case["target"]][case["category"]] += 1
        if case["split"] not in {"development", "holdout_candidate"}:
            raise ValueError("unknown split")
        for field in ("expected_skills", "acceptable_auxiliaries", "forbidden_skills"):
            if not isinstance(case[field], list) or len(set(case[field])) != len(case[field]):
                raise ValueError(f"invalid {field}")
            if set(map(resolve, case[field])) - skills:
                raise ValueError(f"unknown skill in {field}")
        if set(case["expected_skills"]) & set(case["forbidden_skills"]):
            raise ValueError("contradictory answer key")
        if case["category"] == "negative":
            if case["target"] not in case["forbidden_skills"]:
                raise ValueError("negative must forbid target")
        elif case["target"] not in case["expected_skills"]:
            raise ValueError("positive must expect target")
        if not case["messages"] or case["messages"][-1]["role"] != "user":
            raise ValueError("case must end with user request")
        for message in case["messages"]:
            if message["role"] not in {"user", "assistant"} or not message["content"].strip():
                raise ValueError("invalid conversation message")
        if not case["relevant_action"].strip() or not case["rationale"].strip():
            raise ValueError("missing oracle/action boundary")
        fixture = contained(HERE / "fixtures", case["fixture"])
        if not fixture.is_dir():
            raise ValueError(f"missing fixture: {fixture}")
    if set(groups) != TARGETS or any(dict(counts) != COUNTS for counts in groups.values()):
        raise ValueError("expected five targets, each with 4/2/3/1 cases")
    return cases


def inventory(root):
    result = {}
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"symlink not permitted in input snapshot: {file}")
        if file.is_file() and ".git" not in file.relative_to(root).parts:
            result[file.relative_to(root).as_posix()] = digest(file.read_bytes())
    return result


def materialize(args):
    cases = corpus(args.corpus)
    case = next((c for c in cases if c["id"] == args.case), None)
    if case is None:
        raise ValueError("unknown case")
    reason = excluded(case, resolver(catalog_skills()))
    if reason:
        raise ValueError(f"case {case['id']} is excluded on this catalog: {reason}")
    runtime = read_json(args.runtime)
    if RUNTIME_FIELDS - runtime.keys() or any(runtime[k] is None for k in RUNTIME_FIELDS):
        raise ValueError("runtime must freeze model, effort, CLI, permissions, tools and harness deltas")
    if runtime["catalog_scope"] != "full_checkedout_catalog":
        raise ValueError("this slice requires the full checked-out competing catalog")
    if runtime["context_delivery"] != "serialized_conversation":
        raise ValueError("this slice supports serialized conversation, not native multi-turn replay")
    output = Path(args.output).absolute()
    output.resolve().relative_to((REPO / "artifacts" / "skill-evals").resolve())
    source_catalog_files = inventory(REPO / "plugins")
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "workspace"
    source = contained(HERE / "fixtures", case["fixture"])
    inventory(source)  # Reject links before copying.
    shutil.copytree(source, workspace)
    template = output / "empty-git-template"
    template.mkdir()
    subprocess.run(["git", "-c", "init.templateDir=" + str(template), "init", "--quiet", str(workspace)],
                   check=True, capture_output=True)
    template.rmdir()
    inputs = output / "inputs"
    inputs.mkdir()
    # Full bodies and their resources survive; executable integration bindings do not.
    shutil.copytree(REPO / "plugins", inputs / "plugins", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    removed = []
    versions = {}
    for plugin in sorted((inputs / "plugins").iterdir()):
        for name in (".claude-plugin", ".codex-plugin"):
            manifest = plugin / name / "plugin.json"
            if manifest.exists():
                original = read_json(manifest)
                versions[f"{plugin.name}/{name}"] = original["version"]
                for key in ("hooks", "mcpServers"):
                    if key in original:
                        removed.append(str(manifest.relative_to(inputs)) + ":" + key)
                        del original[key]
                save_json(manifest, original)
        for binding in ("hooks", ".mcp.json", "mcp.json"):
            path = plugin / binding
            if path.exists():
                removed.append(path.relative_to(inputs).as_posix())
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
    skills = {}
    for file in sorted((inputs / "plugins").glob("*/skills/*/SKILL.md")):
        skill = f"{file.parents[2].name}:{file.parent.name}"
        body = delivered_body(file.read_text(encoding="utf-8"))
        skills[skill] = {"path": str(file.absolute()), "sha256": digest(file.read_bytes()),
                         "body_sha256": None if body is None else digest(body.encode())}
    prompt = "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in case["messages"])
    (inputs / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    save_json(inputs / "messages.json", case["messages"])
    save_json(output / "manifest.json", {
        "schema_version": 1, "case_id": case["id"], "corpus_sha256": digest(Path(args.corpus).read_bytes()),
        "runtime": runtime, "plugin_versions": versions, "skills": skills,
        "input_files": inventory(inputs), "fixture_files": inventory(workspace),
        "fixture_catalog_files": inventory(HERE / "fixtures"),
        "source_catalog_files": source_catalog_files, "removed_bindings": removed,
        "isolation": "prepared_only_not_provider_verified", "harness_sha256": digest(Path(__file__).read_bytes()),
    })
    return {"run": str(output), "case_id": case["id"], "skills": len(skills), "state": "prepared"}


def verify_inputs(run):
    manifest = read_json(run / "manifest.json")
    if inventory(run / "inputs") != manifest["input_files"]:
        raise ValueError("frozen inputs changed")
    return manifest


def declared_snapshot(path, manifest):
    """A --plugin-dir the session loaded; its SKILL.md files must equal the frozen catalog byte for byte."""
    if not os.path.isabs(path):
        raise ValueError(f"--plugin-dir must be the absolute path given to claude: {path}")
    root = Path(path)
    plugin = read_json(root / ".claude-plugin" / "plugin.json")["name"]
    found = {f"{plugin}:{file.parent.name}": digest(file.read_bytes()) for file in root.glob("skills/*/SKILL.md")}
    frozen = {skill: entry["sha256"] for skill, entry in manifest["skills"].items() if skill.split(":")[0] == plugin}
    if not found or found != frozen:
        raise ValueError(f"--plugin-dir does not match the frozen catalog: {path}")
    return {"plugin": plugin, "path": path, "realpath": os.path.realpath(path)}


def capture(args):
    run = Path(args.run).absolute()
    manifest = verify_inputs(run)
    claude = args.format == "claude-transcript"
    if claude != bool(args.plugin_dir) or (not claude and (args.stream or args.relevant_action)):
        raise ValueError("--format claude-transcript needs --plugin-dir; --stream and --relevant-action need it too")
    if claude and args.evidence_kind != "native":
        raise ValueError("a Claude transcript is native evidence")
    source = Path(args.source)
    data = source.read_bytes()
    info = {"schema_version": 1, "sha256": digest(data), "path": "raw.jsonl", "source": str(source.absolute()),
            "state": args.state, "format": args.format, "evidence_kind": args.evidence_kind}
    sidechains = []
    if claude:
        info["plugin_dirs"] = [declared_snapshot(path, manifest) for path in args.plugin_dir]
        info["relevant_action"] = args.relevant_action
        # Claude stores sidechains at <session>/subagents/ beside <session>.jsonl.
        subagents = source.with_suffix("") / "subagents"
        sidechains = sorted(subagents.iterdir()) if subagents.is_dir() else []
        if any(file.is_symlink() or not file.is_file() for file in sidechains):
            raise ValueError(f"sidechain directory holds a link or a directory: {subagents}")
        if args.stream and not Path(args.stream).is_file():
            raise ValueError(f"missing stream file: {args.stream}")
    inventory(run / "workspace")  # Reject model-created links before copytree can dereference them.
    # Retain bytes even if a provider trace is not parseable by the offline adapter.
    with (run / "raw.jsonl").open("xb") as handle:
        handle.write(data)
    if claude:
        info["sidechains"] = {}
        if sidechains:
            (run / "raw-subagents").mkdir()
        for file in sidechains:
            copy = shutil.copyfile(file, run / "raw-subagents" / file.name)
            info["sidechains"][file.name] = digest(Path(copy).read_bytes())
        info["stream"] = None
        if args.stream:
            copy = shutil.copyfile(args.stream, run / "raw-stream.jsonl")
            info["stream"] = {"path": "raw-stream.jsonl", "sha256": digest(Path(copy).read_bytes()),
                              "source": str(Path(args.stream).absolute())}
    shutil.copytree(run / "workspace", run / "final-files", ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    info["final_files"] = inventory(run / "final-files")
    save_json(run / "capture.json", info)
    return {"raw": str(run / "raw.jsonl"), "sha256": info["sha256"], "state": args.state,
            "sidechains": len(sidechains)}


def retained(run, path, sha256):
    file = run / path
    if digest(file.read_bytes()) != sha256:
        raise ValueError(f"raw trace digest mismatch: {path}")
    return file


def claude_lines(path, label, issues):
    """One-based (line, object) pairs; a malformed or unterminated line is coverage loss."""
    # Split bytes first: a tail cut inside a multibyte character is coverage loss, not a crash.
    parts = path.read_bytes().split(b"\n")
    if parts.pop():
        issues.append(f"{label} line {len(parts) + 1}: unterminated final line")
    rows = []
    for line, text in enumerate(parts, 1):
        try:
            row = json.loads(text.decode("utf-8"))
            if not isinstance(row, dict):
                raise ValueError("not an object")
            rows.append((line, row))
        except ValueError as error:
            issues.append(f"{label} line {line}: {error}")
    return rows


def claude_session(rows, label, sid, agent, issues):
    """Index one transcript file: tool calls, their results, linked skill bodies, and lineage."""
    uses, results, bodies, starts = {}, {}, {}, {}
    seen, children = set(), Counter()
    first = None
    for line, row in rows:
        where = f"{label} line {line}"
        typ = row.get("type")
        if typ not in CLAUDE_LINE_TYPES:
            issues.append(f"{where}: unknown record type {typ!r}")
            continue
        if row.get("sessionId") != sid:
            issues.append(f"{where}: sessionId differs from the root session")
        if typ == "system" and row.get("subtype") not in CLAUDE_SYSTEM_SUBTYPES:
            issues.append(f"{where}: unknown system subtype {row.get('subtype')!r}")
        if typ == "attachment" and (row.get("attachment") or {}).get("type") not in CLAUDE_ATTACHMENT_TYPES:
            issues.append(f"{where}: unknown attachment type {(row.get('attachment') or {}).get('type')!r}")
        if typ not in {"user", "assistant", "attachment", "system"}:
            continue
        uuid = row.get("uuid")
        if not isinstance(uuid, str) or uuid in seen:
            issues.append(f"{where}: missing or duplicate uuid")
            continue
        if row.get("isSidechain") is not (agent is not None) or (agent and row.get("agentId") != agent):
            issues.append(f"{where}: isSidechain or agentId does not match the file")
        parent = row.get("parentUuid")
        if parent is None and seen:
            issues.append(f"{where}: second chain root (resume or branch)")
        elif parent is not None and parent not in seen:
            issues.append(f"{where}: parent not in this transcript (resume or compaction)")
        elif parent is not None:
            children[parent] += 1
            if children[parent] > 1:
                issues.append(f"{where}: branch in the message chain")
        seen.add(uuid)
        first = first or row
        ref = {"file": label, "line": line, "event_id": uuid}
        content = (row.get("message") or {}).get("content") if typ in {"user", "assistant"} else None
        if typ == "assistant":
            message_id = (row.get("message") or {}).get("id")
            if not isinstance(message_id, str) or not isinstance(content, list):
                issues.append(f"{where}: assistant line without message id or content blocks")
                continue
            # One API message spans several lines. Every tool call in it was decided at its first line.
            starts.setdefault(message_id, line)
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    if block.get("id") in uses:
                        issues.append(f"{where}: duplicate tool_use id")
                        continue
                    uses[block.get("id")] = {"line": line, "ref": ref, "name": block.get("name"),
                                             "input": block.get("input") or {}, "start": starts[message_id]}
        elif typ == "user" and isinstance(content, list):
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "tool_result"):
                    continue
                tool_use_id = block.get("tool_use_id")
                if tool_use_id not in uses or tool_use_id in results:
                    issues.append(f"{where}: tool_result without one earlier tool_use")
                    continue
                results[tool_use_id] = {"line": line, "ref": ref, "is_error": block.get("is_error") is True,
                                        "detail": row.get("toolUseResult")}
            texts = [b.get("text") for b in content if isinstance(b, dict) and b.get("type") == "text"]
            if row.get("isMeta") and any(isinstance(t, str) and t.startswith(CLAUDE_BASE_PREFIX) for t in texts):
                source = row.get("sourceToolUseID")
                if len(content) != 1:
                    issues.append(f"{where}: skill body in an unaudited message shape")
                elif (uses.get(source) or {}).get("name") != "Skill" or source in bodies:
                    issues.append(f"{where}: skill body not linked to one earlier Skill call (typed invocation is unsupported)")
                else:
                    bodies[source] = {"line": line, "ref": ref, "text": texts[0]}
        elif typ == "user" and row.get("isMeta") and isinstance(content, str) and content.startswith(CLAUDE_BASE_PREFIX):
            issues.append(f"{where}: skill body in an unaudited message shape")
    return {"uses": uses, "results": results, "bodies": bodies, "first": first}


def claude_load(tool_use_id, session, frozen, manifest, sid, agent, issues):
    """One load record. A root load whose identity stays unresolved is an issue, never a silent miss."""
    use = session["uses"][tool_use_id]
    result = session["results"].get(tool_use_id)
    body = session["bodies"].get(tool_use_id)
    load = {"skill": None, "skill_path": None, "status": "unavailable", "detail": None, "body_sha256": None,
            "completed_seq": None, "session_id": sid, "agent_id": agent, "ordering": "unknown",
            "evidence": [use["ref"]] + [item["ref"] for item in (result, body) if item]}
    if use["name"] == "Skill":
        requested = str(use["input"].get("skill"))
        # The Skill tool also accepts a bare name; resolve it within the declared snapshots.
        matches = {skill for skill in frozen.values() if requested in {skill, skill.split(":", 1)[1]}}
        load.update(skill=matches.pop() if len(matches) == 1 else requested, proof="skill_body_delivery",
                    transform="frontmatter_removed_leading_newlines_stripped")
    else:
        load.update(skill_path=use["input"].get("file_path"), proof="full_body_read", transform=None)
        load["skill"] = frozen[posixpath.normpath(load["skill_path"])]
    load = claude_proof(load, use, result, body, frozen, manifest)
    unresolved = load["status"] in {"partial", "unavailable"} and load["skill"] not in manifest["skills"]
    if agent is None and (unresolved or load["detail"] in CLAUDE_IDENTITY_LOSS):
        issues.append(f"{use['ref']['file']} line {use['line']}: skill identity unresolved ({load['detail']})")
    return load


def claude_proof(load, use, result, body, frozen, manifest):
    if result is None:
        load["detail"] = "no tool_result"
        return load
    if result["is_error"]:
        load.update(status="failed", detail="tool_result is_error", completed_seq=result["line"],
                    ordering="source_sequence")
        return load
    detail = result["detail"]
    if use["name"] == "Skill":
        if not (isinstance(detail, dict) and detail.get("success") is True):
            load["detail"] = "tool_result lacks toolUseResult.success"
            return load
        if body is None:
            load.update(status="partial", detail="no skill body linked by sourceToolUseID")
            return load
        base_dir, separator, text = body["text"][len(CLAUDE_BASE_PREFIX):].partition("\n\n")
        load["skill_path"] = posixpath.join(base_dir, "SKILL.md")
        skill = frozen.get(posixpath.normpath(load["skill_path"]))
        if skill is None:
            load["detail"] = "base directory outside the declared snapshot"
            return load
        if load["skill"] != skill:
            load["detail"] = "requested skill differs from the delivered base directory"
            return load
        load["skill"] = skill
        expected = manifest["skills"][skill]["body_sha256"]
        mismatch = None if separator and digest(text.encode()) == expected else "body digest mismatch"
        completed = max(result["line"], body["line"])
    else:
        file = detail.get("file") if isinstance(detail, dict) else None
        if not isinstance(file, dict) or not isinstance(file.get("content"), str):
            load["detail"] = "tool_result lacks toolUseResult.file content"
            return load
        if posixpath.normpath(str(file.get("filePath"))) != posixpath.normpath(load["skill_path"]):
            load["detail"] = "result path differs from the requested path"
            return load
        text = file["content"]
        full = file.get("startLine") == 1 and isinstance(file.get("numLines"), int) and file["numLines"] == file.get("totalLines")
        mismatch = ("sliced read" if not full else
                    None if digest(text.encode()) == manifest["skills"][load["skill"]]["sha256"] else "content digest mismatch")
        completed = result["line"]
    load.update(status="partial" if mismatch else "success", detail=mismatch, body_sha256=digest(text.encode()),
                completed_seq=completed, ordering="source_sequence")
    return load


def normalize_claude(run, manifest, capture_info, base, relevant_kind):
    """Claude Code transcript adapter; see EVIDENCE.md "Claude transcript adapter"."""
    base.update(provider="claude-code", adapter_version="claude-transcript-v1", child_loads=[])
    issues = base["issues"]
    frozen = {}
    for snapshot in capture_info["plugin_dirs"]:
        for root in {snapshot["path"], snapshot["realpath"]}:
            for skill in manifest["skills"]:
                plugin, name = skill.split(":", 1)
                if plugin == snapshot["plugin"]:
                    frozen[posixpath.normpath(posixpath.join(root, "skills", name, "SKILL.md"))] = skill
    rows = claude_lines(run / capture_info["path"], capture_info["path"], issues)
    session_ids = {row.get("sessionId") for _, row in rows}
    if len(session_ids) != 1 or not isinstance(next(iter(session_ids), None), str):
        issues.append("root transcript does not carry one sessionId")
        return base
    sid = base["session_id"] = session_ids.pop()
    root = claude_session(rows, capture_info["path"], sid, None, issues)
    first = root["first"] or {}
    base["coverage"]["start"] = first.get("type") == "user" and first.get("parentUuid") is None
    sessions = [(None, root)]
    for name, sha256 in sorted(capture_info["sidechains"].items()):
        if name.startswith("agent-") and name.endswith(".jsonl"):
            file_label = "raw-subagents/" + name
            agent = name[len("agent-"):-len(".jsonl")]
            rows = claude_lines(retained(run, file_label, sha256), file_label, issues)
            sessions.append((agent, claude_session(rows, file_label, sid, agent, issues)))
    for tool_use_id, use in root["uses"].items():
        detail = (root["results"].get(tool_use_id) or {}).get("detail")
        if use["name"] in {"Agent", "Task"} and isinstance(detail, dict) and detail.get("agentId"):
            if f"agent-{detail['agentId']}.jsonl" not in capture_info["sidechains"]:
                issues.append(f"{capture_info['path']} line {use['line']}: subagent sidechain not captured")
    for agent, session in sessions:
        for tool_use_id, use in session["uses"].items():
            path = use["input"].get("file_path") if use["name"] == "Read" else None
            if use["name"] == "Skill" or (isinstance(path, str) and posixpath.normpath(path) in frozen):
                load = claude_load(tool_use_id, session, frozen, manifest, sid, agent, issues)
                base["loads" if agent is None else "child_loads"].append(load)
    stream = capture_info["stream"]
    if stream:
        events = claude_lines(retained(run, stream["path"], stream["sha256"]), stream["path"], issues)
        ends = [row for _, row in events if row.get("type") == "result"]
        base["coverage"]["end"] = (len(ends) == 1 and ends[0].get("session_id") == sid
                                   and ends[0].get("subtype") == "success" and ends[0].get("is_error") is False)
        if not base["coverage"]["end"]:
            issues.append("stream lacks one successful result event for this session")
    label = capture_info["relevant_action"]
    if label == "none":
        base["coverage"]["relevant_actions"] = True
    elif label is not None and label not in root["uses"]:
        issues.append(f"relevant-action label {label} is not a root tool_use")
    elif label is not None:
        use = root["uses"][label]
        base["actions"].append({"kind": relevant_kind, "tool": use["name"], "tool_use_id": label,
                                "seq": use["start"], "session_id": sid, "ordering": "message_start",
                                "evidence": [use["ref"]]})
        base["coverage"]["relevant_actions"] = True
    base["coverage"]["skill_delivery"] = not issues
    complete = all(base["coverage"].values()) and not issues and capture_info["state"] == "completed"
    base["evidence_coverage"] = "complete" if complete else "partial"
    return base


def normalize(run, relevant_kind=None):
    """Dispatch to the adapter that capture.json names; unknown native formats stay unscored."""
    manifest = verify_inputs(run)
    capture_info = read_json(run / "capture.json")
    raw = retained(run, capture_info["path"], capture_info["sha256"])
    base = {"schema_version": 1, "provider": "offline", "adapter_version": "synthetic-contract-v1",
            "evidence_kind": capture_info["evidence_kind"], "session_id": None,
            "session_state": capture_info["state"], "evidence_coverage": "unavailable",
            "coverage": {key: False for key in ("start", "end", "skill_delivery", "relevant_actions")},
            "raw_trace": {"path": raw.name, "sha256": capture_info["sha256"]},
            "loads": [], "actions": [], "issues": []}
    if capture_info["format"] == "claude-transcript" and capture_info["evidence_kind"] == "native":
        return normalize_claude(run, manifest, capture_info, base, relevant_kind)
    if capture_info["format"] != "synthetic-contract-v1" or capture_info["evidence_kind"] != "synthetic":
        base["issues"].append("native_adapter_unverified")
        return base
    events = []
    ids = set()
    for line, text in enumerate(raw.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(text)
            if not isinstance(event, dict) or not isinstance(event.get("event_id"), str) or event["event_id"] in ids:
                raise ValueError("missing or duplicate event ID")
            ids.add(event["event_id"])
            events.append((line, event))
        except (ValueError, TypeError) as error:
            base["issues"].append(f"line {line}: {error}")
    starts = [(line, e) for line, e in events if e.get("type") == "session.started" and e.get("parent_session_id") is None]
    if len(starts) != 1 or not starts[0][1].get("session_id"):
        base["issues"].append("single root session not established")
        return base
    start_line, start = starts[0]
    sid = base["session_id"] = start["session_id"]
    last_root_line = max(line for line, event in events if event.get("session_id") == sid)
    base["coverage"]["start"] = start_line == 1
    requests = {}
    ended = False
    for line, event in events:
        if event.get("session_id") != sid:
            # Child events are preserved in raw capture but never score a root load.
            continue
        typ = event.get("type")
        ref = {"event_id": event["event_id"], "line": line}
        if ended:
            base["issues"].append("root event after terminal")
        if typ == "session.started":
            continue
        if typ == "skill_read.request":
            request_id = event.get("request_id")
            if not request_id or request_id in requests:
                base["issues"].append("invalid/duplicate request ID")
            else:
                requests[request_id] = (event, ref)
        elif typ == "skill_read.result":
            request = requests.pop(event.get("request_id"), None)
            if request is None:
                base["issues"].append("unmatched read result")
                continue
            req, request_ref = request
            skill = manifest["skills"].get(req.get("skill"))
            body = event.get("body")
            valid_identity = skill and req.get("path") == skill["path"]
            matched = isinstance(body, str) and skill and digest(body.encode()) == skill["sha256"]
            status = "unavailable"
            if valid_identity and type(event.get("exit_code")) is int and event["exit_code"] != 0:
                status = "failed"
            elif type(event.get("exit_code")) is int and event["exit_code"] == 0 and valid_identity:
                status = "success" if event.get("body_complete") is True and matched else "partial"
            base["loads"].append({"skill": req.get("skill"), "skill_path": req.get("path"), "status": status,
                                  "body_sha256": digest(body.encode()) if isinstance(body, str) else None,
                                  "completed_seq": line, "session_id": sid, "proof": "full_body_read",
                                  "ordering": "source_sequence", "evidence": [request_ref, ref]})
        elif typ == "action.started":
            if not isinstance(event.get("kind"), str):
                base["issues"].append("action missing semantic boundary")
            else:
                base["actions"].append({"kind": event["kind"], "seq": line, "session_id": sid,
                                         "ordering": "source_sequence", "evidence": [ref]})
        elif typ == "session.completed":
            ended = True
            base["coverage"]["end"] = line == last_root_line
            for field in ("skill_delivery", "relevant_actions"):
                base["coverage"][field] = event.get("coverage", {}).get(field) is True
        elif typ not in {"message", "skill.mention"}:
            base["issues"].append(f"unknown record: {typ}")
    for req, ref in requests.values():
        base["loads"].append({"skill": req.get("skill"), "skill_path": req.get("path"), "status": "unavailable",
                              "body_sha256": None, "completed_seq": None, "session_id": sid,
                              "proof": "full_body_read", "ordering": "unknown", "evidence": [ref]})
    if all(base["coverage"].values()) and not base["issues"] and capture_info["state"] == "completed":
        base["evidence_coverage"] = "complete"
    else:
        base["evidence_coverage"] = "partial"
    return base


def score(args):
    run = Path(args.run).absolute()
    manifest = verify_inputs(run)
    if digest(Path(args.corpus).read_bytes()) != manifest["corpus_sha256"]:
        raise ValueError("answer-key corpus changed since materialization")
    case = next(c for c in corpus(args.corpus) if c["id"] == manifest["case_id"])
    resolve = resolver(manifest["skills"])
    if excluded(case, resolve):
        raise ValueError(f"case {case['id']} is excluded on this catalog: {excluded(case, resolve)}")
    evidence = normalize(run, case["relevant_action"])
    scorer_sha256 = digest(Path(__file__).read_bytes())
    configuration = {field: manifest[field] for field in ("runtime", "plugin_versions", "source_catalog_files",
                                                         "removed_bindings", "corpus_sha256", "fixture_catalog_files",
                                                         "harness_sha256")}
    configuration.update(adapter_version=evidence["adapter_version"], scorer_sha256=scorer_sha256)
    configuration_sha256 = digest(json.dumps(configuration, sort_keys=True).encode())
    save_json(run / "evidence.json", evidence)
    observed = {load["skill"] for load in evidence["loads"] if load["status"] == "success"}
    allowed = set(map(resolve, case["expected_skills"] + case["acceptable_auxiliaries"]))
    forbidden = set(map(resolve, case["forbidden_skills"]))
    complete = evidence["evidence_coverage"] == "complete" and evidence["session_state"] == "completed"
    ambiguous_forbidden = any(l["skill"] in forbidden and l["status"] in {"partial", "unavailable"}
                              for l in evidence["loads"])
    activation = {}
    timing = {}
    actions = [a["seq"] for a in evidence["actions"] if a["kind"] == case["relevant_action"]]
    for skill in case["expected_skills"]:
        loads = [l["completed_seq"] for l in evidence["loads"] if l["skill"] == resolve(skill) and l["status"] == "success"]
        ambiguous = any(l["skill"] == resolve(skill) and l["status"] in {"partial", "unavailable"} for l in evidence["loads"])
        activation[skill] = "loaded" if loads else "miss" if complete and not ambiguous else "unavailable"
        action_coverage = evidence["coverage"]["start"] and evidence["coverage"]["relevant_actions"] and not evidence["issues"]
        timing[skill] = ("before" if min(loads) < min(actions) else "late") if loads and actions and action_coverage else "unavailable"
    result = {"schema_version": 1, "case_id": case["id"], "target": case["target"], "category": case["category"],
              "configuration_sha256": configuration_sha256, "scorer_sha256": scorer_sha256,
              "runtime": manifest["runtime"], "adapter_version": evidence["adapter_version"],
              "split": case["split"], "evidence_kind": evidence["evidence_kind"],
              "session_state": evidence["session_state"], "evidence_coverage": evidence["evidence_coverage"],
              "activation": activation, "timing": timing, "observed_skills": sorted(observed),
              "expected_skills": case["expected_skills"], "allowed_skills": sorted(allowed),
              "unresolved_skills": sorted({l["skill"] for l in evidence["loads"]
                                             if l["status"] in {"partial", "unavailable"}} - observed),
              "false_activation": True if observed & forbidden else False if complete and not ambiguous_forbidden else None,
              "unexpected_skills": sorted(observed - allowed),
              "load_status_counts": dict(Counter(l["status"] for l in evidence["loads"])),
              "raw_trace": evidence["raw_trace"], "manifest_sha256": digest((run / "manifest.json").read_bytes()),
              "measured_efficacy": False}
    save_json(run / "score.json", result)
    return result


def aggregate(args):
    if len({Path(path).resolve() for path in args.scores}) != len(args.scores):
        raise ValueError("duplicate score paths would double-count runs")
    rows = [read_json(path) for path in args.scores]
    groups = {}
    confusion = defaultdict(Counter)
    strata_rows = defaultdict(list)
    for row in rows:
        key = (row["configuration_sha256"], row["evidence_kind"], row["split"], row["target"],
               "explicit_control" if row["category"] == "explicit" else "implicit")
        group = groups.setdefault(key, Counter())
        group["runs"] += 1
        group["session_" + row["session_state"]] += 1
        group["coverage_" + row["evidence_coverage"]] += 1
        complete = row["evidence_coverage"] == "complete" and row["session_state"] == "completed"
        group["complete_sessions"] += int(complete)
        strata_rows[key].append((row, complete))
        if row["category"] == "negative":
            if row["false_activation"] is True:
                group["observed_forbidden_runs"] += 1
            if complete and row["false_activation"] is not None:
                group["negative_scorable"] += 1
                group["false_activations"] += int(row["false_activation"])
        else:
            state = row["activation"].get(row["target"], "unavailable") if complete else "unavailable"
            group["positive_" + state] += 1
            group["timing_" + row["timing"].get(row["target"], "unavailable")] += 1
        for unexpected in row["unexpected_skills"]:
            confusion[(key, tuple(row["expected_skills"]), unexpected)]["scorable" if complete else "interrupted_or_partial"] += 1
    report = []
    for key, counts in sorted(groups.items()):
        denominator = counts["positive_loaded"] + counts["positive_miss"]
        negatives = counts["negative_scorable"]
        report.append({"configuration_sha256": key[0], "runtime": strata_rows[key][0][0]["runtime"],
                       "evidence_kind": key[1], "split": key[2], "target": key[3], "experiment": key[4],
                       "counts": dict(counts), "recall": counts["positive_loaded"] / denominator if denominator else None,
                       "recall_denominator": denominator,
                       "false_activation_rate": counts["false_activations"] / negatives if negatives else None,
                       "false_activation_denominator": negatives})
    confusion_rows = []
    for (key, expected, unexpected), counts in sorted(confusion.items()):
        denominator = sum(complete and tuple(row["expected_skills"]) == expected
                          and unexpected not in row["allowed_skills"] and unexpected not in row["unresolved_skills"]
                          for row, complete in strata_rows[key])
        confusion_rows.append({"configuration_sha256": key[0], "evidence_kind": key[1], "split": key[2],
                               "target": key[3], "experiment": key[4],
                               "expected_skills": list(expected),
                               "unexpected": unexpected, "count": counts["scorable"], "denominator": denominator,
                               "rate": counts["scorable"] / denominator if denominator else None,
                               "interrupted_or_partial_observations": counts["interrupted_or_partial"]})
    return {"schema_version": 1, "groups": report, "confusion": confusion_rows,
            "warning": "Activation evidence only; no task utility is measured. Synthetic groups verify harness behavior only."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=HERE / "cases.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    prep = commands.add_parser("materialize")
    prep.add_argument("--case", required=True)
    prep.add_argument("--runtime", required=True, type=Path)
    prep.add_argument("--output", required=True, type=Path)
    cap = commands.add_parser("capture", help="retain an existing trace byte-for-byte; never invoke a provider")
    cap.add_argument("--run", required=True, type=Path)
    cap.add_argument("--source", required=True, type=Path)
    cap.add_argument("--state", choices=("completed", "timeout", "incomplete"), required=True)
    cap.add_argument("--format", choices=("native", "claude-transcript", "synthetic-contract-v1"), default="native",
                     help="native: retained but unscored; claude-transcript: a Claude Code session transcript")
    cap.add_argument("--evidence-kind", choices=("native", "synthetic"), default="native")
    cap.add_argument("--plugin-dir", action="append", default=[],
                     help="claude-transcript: each absolute --plugin-dir the session loaded")
    cap.add_argument("--stream", type=Path, help="claude-transcript: the session's stream-json output")
    cap.add_argument("--relevant-action", metavar="TOOL_USE_ID",
                     help="claude-transcript: root tool_use id that starts the case's relevant action, or 'none'")
    sc = commands.add_parser("score")
    sc.add_argument("--run", required=True, type=Path)
    ag = commands.add_parser("aggregate")
    ag.add_argument("scores", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            cases, resolve = corpus(args.corpus), resolver(catalog_skills())
            result = {"cases": len(cases), "targets": sorted(TARGETS),
                      "excluded_on_this_catalog": {c["id"]: excluded(c, resolve) for c in cases if excluded(c, resolve)}}
        else:
            result = {"materialize": materialize, "capture": capture, "score": score, "aggregate": aggregate}[args.command](args)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(2, f"skill-eval: {error}\n")


if __name__ == "__main__":
    main()
