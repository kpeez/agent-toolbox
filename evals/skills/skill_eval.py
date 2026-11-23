#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
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
    "implement", "diagnose", "verifying-work", "test-audit", "codebase-design", "ship-pr", "interview-user",
    "swe-mode")} | {"lab:making-plots", "lab:lab-mode"}
COUNTS = {"natural": 4, "contextual": 2, "negative": 3, "explicit": 1}
# A case belongs to the family named by its `family` field, else by its target. Each family
# in MIX_FAMILIES holds exactly COUNTS. An open family holds only positive cases that set
# `expected_route`, one or two per route, so it has no fixed mix.
MIX_FAMILIES = TARGETS
OPEN_FAMILIES = {"swe-route-choice", "lab-route-choice", "hidden-skill-fallback"}
RUNTIME_FIELDS = {"model", "effort", "cli", "cli_version", "permissions", "tools",
                  "harness_deltas", "catalog_scope", "context_delivery"}
# Claude Code transcript shapes seen in the audited 2.1.296 probe traces (EVIDENCE.md), plus five
# metadata record types from 2.1.325 (session-owner, api-request, api-request-shape,
# api-request-blob, tools-used), and one attachment type from 2.1.327 (silent_turn_reminder, a fixed
# harness nudge to update the user; it carries no skill load).
# Anything else is coverage loss until a raw audit adds it here.
CLAUDE_LINE_TYPES = {"user", "assistant", "attachment", "system", "queue-operation",
                     "atis-latch", "last-prompt", "cost-state", "session-owner", "api-request-shape",
                     "api-request-blob", "api-request", "tools-used"}
CLAUDE_SYSTEM_SUBTYPES = {"stop_hook_summary"}
CLAUDE_ATTACHMENT_TYPES = {
    "advisor_tool", "agent_listing_delta", "command_permissions", "credential_org", "date",
    "deferred_tools_delta", "deferred_tools_record", "environment", "instructions",
    "mcp_instructions_delta", "model", "prompt_snapshot", "remote_session_change",
    "session_context", "silent_turn_reminder", "skill_listing", "total_tokens_reminder"}
ROUTERS = {"swe": "swe-mode", "lab": "lab-mode"}
GO_DEEPER_COPIES = {"swe:go-deeper", "lab:go-deeper", "uni:go-deeper"}
HOOK_ON_ALWAYS_ON = {"go-deeper", "swe:writing"}
# What a router-first run loads on any task its router takes, by (plugin, hook_arm).
# In hook-off, only the router text asks for anything: swe-mode asks for go-deeper, swe:writing, and
# swe:in-your-own-words; lab-mode asks for go-deeper only. In hook-on, the SessionStart hooks add
# go-deeper and swe:writing on every task. A forbidden_skills entry withholds a credit.
ALWAYS_ON = {
    ("swe", "hook-off"): {"go-deeper", "swe:writing", "swe:in-your-own-words"},
    ("lab", "hook-off"): {"go-deeper"},
    ("swe", "hook-on"): {"go-deeper", "swe:writing", "swe:in-your-own-words"},
    ("lab", "hook-on"): {"go-deeper", "swe:writing"},
}
LINE_KIND = {"Playbook": "playbook", "Route": "skill"}
ROUTE_LINE = re.compile(r"^\s*(?:[-*+]\s+)?\**(Playbook|Route)(?::\**|\*\*:)\s*`?(?:[a-z]+:)?([a-z0-9-]+)`?", re.M)
STEPS_HEADING = re.compile(r"Steps\b")
ENTRY_PREFIX = r"\s*(?:(?:[-*+]|\d+\.)\s+)?[`*]*"
STATE_WORD = re.compile(r"[\w-]+")
STATE_SEPARATORS = ":\u2014-*` \t"
REASON_SEPARATORS = ":(-\u2014 \t"
CLAUDE_BASE_PREFIX = "Base directory for this skill: "
# A delivered body that names another skill, or comes from outside the frozen catalog, breaks isolation.
CLAUDE_IDENTITY_LOSS = {"base directory outside the declared snapshot",
                        "requested skill differs from the delivered base directory"}


def canonical_skill(skill):
    """Collapse the three byte-identical go-deeper copies into one canonical skill name."""
    return "go-deeper" if skill in GO_DEEPER_COPIES else skill


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


def load_facets():
    return {f["id"]: f for f in read_json(HERE / "facets.json")["facets"]}


DATASET = HERE / "dataset" / "dev.jsonl"
FIXTURE_FILE = re.compile(r"\.\./fixtures/([^/]+)/(.+)")
SPLITS = {"development", "holdout_candidate", "holdout"}


def fixtures_root(path):
    """Fixtures sit beside the corpus file: a `../fixtures/<fixture>/<path>` value is joined to the file's own path."""
    return Path(path).absolute().parent / "fixtures"


def read_cases(path=DATASET):
    """Parse the Inspect Sample JSONL into the case dicts the rest of this module uses."""
    cases = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        sample = json.loads(line)
        if not isinstance(sample.get("input"), list) or not isinstance(sample.get("files"), dict):
            raise ValueError(f"line {number}: input must be a message list and files a path map")
        names = set()
        for rel, source in sample["files"].items():
            match = FIXTURE_FILE.fullmatch(source)
            if not match or match.group(2) != rel:
                raise ValueError(f"line {number}: file {rel!r} must map to ../fixtures/<fixture>/{rel}")
            names.add(match.group(1))
        if len(names) != 1:
            raise ValueError(f"line {number}: files must all come from exactly one fixture")
        fixture = contained(fixtures_root(path), next(iter(names)))
        present = {f.relative_to(fixture).as_posix() for f in fixture.rglob("*") if f.is_file()}
        if present != set(sample["files"]):
            raise ValueError(f"line {number}: files must list exactly the files of its fixture, "
                             f"missing {sorted(present - set(sample['files']))[:3]}, "
                             f"absent {sorted(set(sample['files']) - present)[:3]}")
        metadata = dict(sample.get("metadata", {}))
        case = {"id": sample["id"], "target": metadata.pop("target_skill"), **metadata,
                "messages": sample["input"], "fixture": names.pop()}
        if "target" in sample:
            case["expected_route"] = sample["target"]
        cases.append(case)
    return cases


def corpus(path=DATASET):
    cases = read_cases(path)
    facets = load_facets()
    ids = set()
    groups = defaultdict(Counter)
    skills = catalog_skills()
    for case in cases:
        if not re.fullmatch(r"[A-Za-z0-9-]+", case["id"]) or case["id"] in ids:
            raise ValueError("invalid or duplicate case ID")
        ids.add(case["id"])
        if case["target"] not in TARGETS or case["category"] not in COUNTS:
            raise ValueError("unknown target/category")
        family = case.get("family", case["target"])
        if family not in MIX_FAMILIES | OPEN_FAMILIES or (family in OPEN_FAMILIES and (
                case["category"] == "negative" or not case.get("expected_route"))):
            raise ValueError("unknown family, or an open-family case that is negative or sets no expected_route")
        groups[family][case["category"]] += 1
        if case["split"] not in SPLITS:
            raise ValueError("unknown split")
        for field in ("expected_skills", "acceptable_auxiliaries", "forbidden_skills"):
            if not isinstance(case[field], list) or len(set(case[field])) != len(case[field]):
                raise ValueError(f"invalid {field}")
            if set(case[field]) - skills:
                raise ValueError(f"unknown skill in {field}")
        if ({canonical_skill(s) for s in case["expected_skills"] + case["acceptable_auxiliaries"]}
                & {canonical_skill(s) for s in case["forbidden_skills"]}):
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
        route = case.get("expected_route")
        plugin = case["target"].split(":")[0]
        if route is not None and (facets.get(route, {}).get("kind") != "route" or facets[route]["plugin"] != plugin
                                  or f"{plugin}:{ROUTERS[plugin]}" in case["forbidden_skills"]):
            raise ValueError("expected_route must name a route facet of the target's plugin, and a case that forbids the router may not set it")
        modes = facets[route].get("modes", {}) if route else {}
        if case.get("expected_mode") not in (modes or {None}):
            raise ValueError("expected_mode must name a mode of the expected route, and only a route with modes takes one")
        listed = case.get("facets", [])
        if not isinstance(listed, list) or len(set(listed)) != len(listed) or any(
                facets.get(f, {}).get("evidence") not in {"skill-call", "full-read"}
                or facets[f]["kind"] == "router-contract" or load_target(facets[f]) is None for f in listed):
            raise ValueError("facets must list unique load facets with skill-call or full-read evidence")
        if not case["relevant_action"].strip() or not case["rationale"].strip():
            raise ValueError("missing oracle/action boundary")
        fixture = contained(fixtures_root(path), case["fixture"])
        if not fixture.is_dir():
            raise ValueError(f"missing fixture: {fixture}")
    splits = {case["split"] for case in cases}
    if "holdout" in splits and splits != {"holdout"}:
        raise ValueError("a holdout corpus holds only holdout cases")
    # The 4/2/3/1 family mix describes the development corpus; a holdout keeps its own mix.
    if splits != {"holdout"} and (set(groups) - OPEN_FAMILIES != MIX_FAMILIES or any(
            dict(groups[family]) != COUNTS for family in MIX_FAMILIES)):
        raise ValueError("expected the declared families, each with 4/2/3/1 cases")
    return cases


def inventory(root):
    result = {}
    for file in sorted(root.rglob("*")):
        if file.is_symlink():
            raise ValueError(f"symlink not permitted in input snapshot: {file}")
        if file.is_file() and ".git" not in file.relative_to(root).parts:
            result[file.relative_to(root).as_posix()] = digest(file.read_bytes())
    return result


def freeze_resources(inputs):
    resources = {}
    for facet in read_json(HERE / "facets.json")["facets"]:
        rel_path = facet.get("path")
        if not rel_path or facet.get("kind") == "router-contract" or rel_path.startswith(".agents/"):
            continue
        if posixpath.basename(rel_path) == "SKILL.md":
            continue
        plugin = facet["plugin"]
        res_id = f"{plugin}:{rel_path}"
        if res_id in resources:
            continue
        file = contained(inputs / "plugins" / plugin, rel_path)
        if not file.is_file():
            raise ValueError(f"missing resource in snapshot: {res_id}")
        resources[res_id] = {"path": str(file.absolute()), "sha256": digest(file.read_bytes())}
    return resources


def filter_plugin_hooks(hooks_dir, inputs, removed):
    for item in sorted(hooks_dir.iterdir()):
        if item.name == "session-start.md":
            continue
        if item.name == "hooks.json" and item.is_file():
            data = read_json(item)
            raw_hooks = data.get("hooks") if isinstance(data.get("hooks"), dict) else {}
            kept = []
            filtered_start = False
            for event_name, entries in raw_hooks.items():
                if event_name != "SessionStart":
                    removed.append(f"{item.relative_to(inputs).as_posix()}:{event_name}")
                    continue
                if not isinstance(entries, list):
                    filtered_start = True
                    continue
                for entry in entries:
                    entry_hooks = entry.get("hooks", []) if isinstance(entry, dict) else []
                    kept_cmds = [
                        h for h in entry_hooks
                        if isinstance(h, dict) and h.get("type") == "command"
                        and isinstance(h.get("command"), str) and "hooks/session-start.md" in h["command"]
                    ]
                    if len(kept_cmds) != len(entry_hooks):
                        filtered_start = True
                    if kept_cmds:
                        kept.append({**entry, "hooks": kept_cmds})
            if filtered_start:
                removed.append(f"{item.relative_to(inputs).as_posix()}:SessionStart")
            if set(raw_hooks) != {"SessionStart"} or filtered_start:
                save_json(item, {**data, "hooks": {"SessionStart": kept} if kept else {}})
            continue
        removed.append(item.relative_to(inputs).as_posix())
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def materialize(args):
    cases = corpus(args.corpus)
    case = next((c for c in cases if c["id"] == args.case), None)
    if case is None:
        raise ValueError("unknown case")
    runtime = read_json(args.runtime)
    if RUNTIME_FIELDS - runtime.keys() or any(runtime[k] is None for k in RUNTIME_FIELDS):
        raise ValueError("runtime must freeze model, effort, CLI, permissions, tools and harness deltas")
    if runtime["catalog_scope"] != "full_checkedout_catalog":
        raise ValueError("this slice requires the full checked-out competing catalog")
    if runtime["context_delivery"] != "serialized_conversation":
        raise ValueError("this slice supports serialized conversation, not native multi-turn replay")
    hook_arm = args.hook_arm
    output = Path(args.output).absolute()
    allowed = getattr(args, "output_root", None) or REPO / "artifacts" / "skill-evals"
    output.resolve().relative_to(Path(allowed).resolve())
    source_catalog_files = inventory(REPO / "plugins")
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "workspace"
    source = contained(fixtures_root(args.corpus), case["fixture"])
    inventory(source)  # Reject links before copying.
    shutil.copytree(source, workspace)
    template = output / "empty-git-template"
    template.mkdir()
    subprocess.run(["git", "-c", "init.templateDir=" + str(template), "init", "--quiet", str(workspace)],
                   check=True, capture_output=True)
    template.rmdir()
    inputs = output / "inputs"
    inputs.mkdir()
    # Full bodies and their resources survive; executable integration bindings do not (except SessionStart in hook-on).
    shutil.copytree(REPO / "plugins", inputs / "plugins", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # The copy must equal the catalog hashed above, less what copytree skipped; else plugins/ changed in between.
    expected = {rel: sha for rel, sha in source_catalog_files.items()
                if not any(part == "__pycache__" or part.endswith(".pyc") for part in rel.split("/"))}
    if inventory(inputs / "plugins") != expected:
        raise ValueError("plugins/ changed while it was copied")
    removed = []
    hooks = {}
    for plugin in sorted((inputs / "plugins").iterdir()):
        for name in (".claude-plugin", ".codex-plugin", ".antigravity-plugin"):
            manifest = plugin / name / "plugin.json"
            if not manifest.exists():
                continue
            original = read_json(manifest)
            changed = False
            for key in ("hooks", "mcpServers"):
                if key in original:
                    removed.append(str(manifest.relative_to(inputs)) + ":" + key)
                    del original[key]
                    changed = True
            if name in (".claude-plugin", ".codex-plugin") or changed:
                save_json(manifest, original)
        hooks_dir = plugin / "hooks"
        if hooks_dir.exists():
            session_start = hooks_dir / "session-start.md"
            if hook_arm == "hook-on" and session_start.is_file():
                hooks[plugin.name] = {"path": str(session_start.absolute()),
                                      "sha256": digest(session_start.read_bytes())}
                filter_plugin_hooks(hooks_dir, inputs, removed)
            else:
                removed.append(hooks_dir.relative_to(inputs).as_posix())
                shutil.rmtree(hooks_dir)
        for binding in (".mcp.json", "mcp.json"):
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
    resources = freeze_resources(inputs)
    prompt = "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in case["messages"])
    (inputs / "prompt.txt").write_text(prompt + "\n", encoding="utf-8")
    save_json(inputs / "messages.json", case["messages"])
    manifest_data = {
        "schema_version": 1, "case_id": case["id"], "corpus_sha256": digest(Path(args.corpus).read_bytes()),
        "facets_sha256": digest((HERE / "facets.json").read_bytes()),
        "hook_arm": hook_arm, "runtime": runtime, "skills": skills,
        "resources": resources, "input_files": inventory(inputs), "fixture_files": inventory(workspace),
        "fixture_catalog_files": inventory(fixtures_root(args.corpus)), "source_catalog_files": source_catalog_files,
        "removed_bindings": removed,
        "known_deltas": [
            "rules/AGENTS.md stays in the snapshot, so an Antigravity run sees the session-start text through it whatever the arm"
        ],
        "isolation": "prepared_only_not_provider_verified", "harness_sha256": digest(Path(__file__).read_bytes()),
    }
    if hook_arm == "hook-on":
        manifest_data["hooks"] = hooks
    save_json(output / "manifest.json", manifest_data)
    return {"run": str(output), "case_id": case["id"], "hook_arm": hook_arm,
            "skills": len(skills), "resources": len(resources), "state": "prepared"}


def verify_inputs(run):
    manifest = read_json(run / "manifest.json")
    if inventory(run / "inputs") != manifest["input_files"]:
        raise ValueError("frozen inputs changed")
    return manifest


def declared_snapshot(path, manifest):
    """A --plugin-dir the session loaded; its SKILL.md files and frozen resources must match the catalog."""
    if not os.path.isabs(path):
        raise ValueError(f"--plugin-dir must be the absolute path given to claude: {path}")
    root = Path(path)
    plugin = read_json(root / ".claude-plugin" / "plugin.json")["name"]
    found = {f"{plugin}:{file.parent.name}": digest(file.read_bytes()) for file in root.glob("skills/*/SKILL.md")}
    frozen = {skill: entry["sha256"] for skill, entry in manifest["skills"].items() if skill.split(":")[0] == plugin}
    if not found or found != frozen:
        raise ValueError(f"--plugin-dir does not match the frozen catalog: {path}")
    for res_id, entry in manifest.get("resources", {}).items():
        res_plugin, rel_path = res_id.split(":", 1)
        if res_plugin != plugin:
            continue
        file = contained(root, rel_path)
        if not file.is_file() or digest(file.read_bytes()) != entry["sha256"]:
            raise ValueError(f"--plugin-dir resource does not match the frozen catalog: {path} ({rel_path})")
    if manifest.get("hook_arm", "hook-off") == "hook-on" and plugin in manifest.get("hooks", {}):
        hook_file = root / "hooks" / "session-start.md"
        if not hook_file.is_file() or digest(hook_file.read_bytes()) != manifest["hooks"][plugin]["sha256"]:
            raise ValueError(f"--plugin-dir hook does not match the frozen catalog: {path} (hooks/session-start.md)")
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
                              "source": str(Path(args.stream).absolute()),
                              "appended_final_newline": bool(getattr(args, "stream_appended_final_newline", False))}
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


def is_session_start_hook_success(row):
    if row.get("type") != "attachment":
        return False
    att = row.get("attachment") or {}
    return att.get("type") == "hook_success" and att.get("hookEvent") == "SessionStart"


def claude_start_covered(chain, hook_arm):
    if not chain:
        return False
    idx = 0
    if hook_arm == "hook-on":
        while idx < len(chain) and is_session_start_hook_success(chain[idx]):
            expected_parent = None if idx == 0 else chain[idx - 1]["uuid"]
            if chain[idx].get("parentUuid") != expected_parent:
                return False
            idx += 1
    if idx >= len(chain):
        return False
    expected_parent = None if idx == 0 else chain[idx - 1]["uuid"]
    return chain[idx].get("type") == "user" and chain[idx].get("parentUuid") == expected_parent


def claude_session(rows, label, sid, agent, issues, hook_arm="hook-off"):
    """Index one transcript file: tool calls, their results, linked skill bodies, and lineage."""
    uses, results, bodies, starts, said = {}, {}, {}, {}, []
    seen, children, message_of = set(), Counter(), {}
    chain, hook_rows = [], []
    saw_non_hook = False
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
        if typ == "attachment":
            att = row.get("attachment") or {}
            att_type = att.get("type")
            if att_type == "hook_additional_context":
                issues.append(f"{where}: hook_additional_context attachment is unsupported")
            elif att_type == "hook_success":
                if hook_arm != "hook-on":
                    issues.append(f"{where}: hook_success attachment in hook-off arm (isolation failed)")
                elif agent is not None:
                    issues.append(f"{where}: hook_success attachment in sidechain")
                elif att.get("hookEvent") != "SessionStart":
                    issues.append(f"{where}: hook_success for unsupported hookEvent {att.get('hookEvent')!r}")
                elif saw_non_hook:
                    issues.append(f"{where}: SessionStart hook_success outside leading start run")
            elif att_type not in CLAUDE_ATTACHMENT_TYPES:
                issues.append(f"{where}: unknown attachment type {att_type!r}")
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
            # Parallel tool calls split one API message over several lines; each continuation
            # line is a child of the previous line, beside that line's tool_result.
            message_id = (row.get("message") or {}).get("id") if typ == "assistant" else None
            message_of[uuid] = message_id
            continuation = message_id is not None and message_of.get(parent) == message_id
            children[parent] += 0 if continuation else 1
            if children[parent] > 1:
                issues.append(f"{where}: branch in the message chain")
        seen.add(uuid)
        chain.append(row)
        ref = {"file": label, "line": line, "event_id": uuid}
        if hook_arm == "hook-on" and agent is None and is_session_start_hook_success(row) and not saw_non_hook:
            hook_rows.append((ref, row.get("attachment") or {}))
        else:
            saw_non_hook = True
        content = (row.get("message") or {}).get("content") if typ in {"user", "assistant"} else None
        if typ == "assistant":
            message_id = (row.get("message") or {}).get("id")
            if not isinstance(message_id, str) or not isinstance(content, list):
                issues.append(f"{where}: assistant line without message id or content blocks")
                continue
            # One API message spans several lines. Every tool call in it was decided at its first line.
            starts.setdefault(message_id, line)
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                    said.append({"seq": line, "text": block["text"], "session_id": sid, "evidence": [ref]})
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
    return {"uses": uses, "results": results, "bodies": bodies, "chain": chain, "hook_rows": hook_rows,
            "texts": said}


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
    load = claude_proof(load, use, result, body, frozen, manifest, sid)
    unresolved = load["status"] in {"partial", "unavailable"} and load["skill"] not in manifest["skills"]
    if agent is None and (unresolved or load["detail"] in CLAUDE_IDENTITY_LOSS):
        issues.append(f"{use['ref']['file']} line {use['line']}: skill identity unresolved ({load['detail']})")
    return load


def claude_full_read(requested_path, result, expected_sha256):
    if result is None:
        return {"detail": "no tool_result"}
    if result["is_error"]:
        return {"status": "failed", "detail": "tool_result is_error", "completed_seq": result["line"],
                "ordering": "source_sequence"}
    detail = result["detail"]
    file = detail.get("file") if isinstance(detail, dict) else None
    if not isinstance(file, dict) or not isinstance(file.get("content"), str):
        return {"detail": "tool_result lacks toolUseResult.file content"}
    if posixpath.normpath(str(file.get("filePath"))) != posixpath.normpath(requested_path):
        return {"detail": "result path differs from the requested path"}
    text = file["content"]
    full = file.get("startLine") == 1 and isinstance(file.get("numLines"), int) and file["numLines"] == file.get("totalLines")
    mismatch = ("sliced read" if not full else
                None if digest(text.encode()) == expected_sha256 else "content digest mismatch")
    return {"status": "partial" if mismatch else "success", "detail": mismatch,
            "body_sha256": digest(text.encode()), "completed_seq": result["line"], "ordering": "source_sequence"}


def claude_resource_read(tool_use_id, session, frozen_resources, manifest, sid, agent):
    use = session["uses"][tool_use_id]
    result = session["results"].get(tool_use_id)
    path = use["input"].get("file_path")
    res_id = frozen_resources[posixpath.normpath(path)]
    record = {"resource": res_id, "path": path, "status": "unavailable", "detail": None, "body_sha256": None,
              "completed_seq": None, "session_id": sid, "agent_id": agent, "proof": "full_body_read",
              "ordering": "unknown", "evidence": [use["ref"]] + ([result["ref"]] if result else [])}
    record.update(claude_full_read(path, result, manifest["resources"][res_id]["sha256"]))
    return record


def claude_proof(load, use, result, body, frozen, manifest, sid=None):
    if use["name"] != "Skill":
        load.update(claude_full_read(load["skill_path"], result, manifest["skills"][load["skill"]]["sha256"]))
        return load
    if result is None:
        load["detail"] = "no tool_result"
        return load
    if result["is_error"]:
        load.update(status="failed", detail="tool_result is_error", completed_seq=result["line"],
                    ordering="source_sequence")
        return load
    detail = result["detail"]
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
    args_value = use["input"].get("args")
    # Claude Code appends Skill call arguments to a body that has no $ARGUMENTS placeholder,
    # replaces every $ARGUMENTS placeholder when the body contains one, and replaces every
    # ${CLAUDE_SESSION_ID} with the session id.
    suffix = "\n\nARGUMENTS: " + str(args_value or "")
    substituted = False
    if args_value and text.endswith(suffix) and digest(text[:-len(suffix)].encode()) == expected:
        text = text[:-len(suffix)]
        load["transform"] += "_arguments_suffix_removed"
    elif separator and digest(text.encode()) != expected:
        skill_file = Path(load["skill_path"])
        if not skill_file.is_file() or digest(skill_file.read_bytes()) != manifest["skills"][skill]["sha256"]:
            skill_file = Path(manifest["skills"][skill]["path"])
        frozen_body = delivered_body(skill_file.read_text(encoding="utf-8"))
        if frozen_body is not None and digest(frozen_body.encode()) == expected:
            filled, tags = frozen_body, ""
            if "$ARGUMENTS" in frozen_body:
                filled, tags = filled.replace("$ARGUMENTS", str(args_value or "")), "_arguments_substituted"
            elif args_value:
                filled, tags = filled + suffix, "_arguments_suffix_removed"
            if sid and "${CLAUDE_SESSION_ID}" in frozen_body:
                filled, tags = filled.replace("${CLAUDE_SESSION_ID}", sid), tags + "_session_id_substituted"
            if tags and text == filled:
                substituted = True
                load["transform"] += tags
    mismatch = None if separator and (substituted or digest(text.encode()) == expected) else "body digest mismatch"
    load.update(status="partial" if mismatch else "success", detail=mismatch, body_sha256=digest(text.encode()),
                completed_seq=max(result["line"], body["line"]), ordering="source_sequence")
    return load


def final_reply(texts, call_seqs):
    """The root texts written after the last root tool call, or None."""
    last_call = max(call_seqs, default=0)
    tail = [t["text"] for t in texts if t["seq"] > last_call]
    return "\n\n".join(tail) if tail else None


def normalize_claude(run, manifest, capture_info, base, relevant_kind):
    """Claude Code transcript adapter; see EVIDENCE.md "Claude transcript adapter"."""
    base.update(provider="claude-code", adapter_version="claude-transcript-v1")
    issues = base["issues"]
    hook_arm = manifest.get("hook_arm", "hook-off")
    declared_plugins = {snapshot["plugin"] for snapshot in capture_info["plugin_dirs"]}
    expected_hooks = (
        {p: entry for p, entry in manifest.get("hooks", {}).items() if p in declared_plugins}
        if hook_arm == "hook-on" else {}
    )
    frozen, frozen_resources = {}, {}
    for snapshot in capture_info["plugin_dirs"]:
        for root in {snapshot["path"], snapshot["realpath"]}:
            for skill in manifest["skills"]:
                plugin, name = skill.split(":", 1)
                if plugin == snapshot["plugin"]:
                    frozen[posixpath.normpath(posixpath.join(root, "skills", name, "SKILL.md"))] = skill
            for res_id in manifest.get("resources", {}):
                plugin, rel_path = res_id.split(":", 1)
                if plugin == snapshot["plugin"]:
                    frozen_resources[posixpath.normpath(posixpath.join(root, rel_path))] = res_id
    bash_targets = [
        (kind, target_id, p, re.compile(re.escape(p) + r"(?![\w./-])"))
        for kind, target_id, p in (
            [("skill", skill_id, p) for p, skill_id in sorted(frozen.items())]
            + [("resource", res_id, p) for p, res_id in sorted(frozen_resources.items())]
        )
    ]
    rows = claude_lines(run / capture_info["path"], capture_info["path"], issues)
    session_ids = {row.get("sessionId") for _, row in rows}
    if len(session_ids) != 1 or not isinstance(next(iter(session_ids), None), str):
        issues.append("root transcript does not carry one sessionId")
        return base
    sid = base["session_id"] = session_ids.pop()
    root = claude_session(rows, capture_info["path"], sid, None, issues, hook_arm)
    base["texts"] = root["texts"]
    base["final_reply"] = final_reply(root["texts"], [use["line"] for use in root["uses"].values()])
    base["coverage"]["start"] = claude_start_covered(root["chain"], hook_arm)
    if hook_arm == "hook-on":
        seen_success = set()
        for ref, att in root["hook_rows"]:
            stdout = att.get("stdout")
            exit_ok = att.get("exitCode") in (None, 0)
            sha = digest(stdout.encode("utf-8")) if isinstance(stdout, str) else None
            matched = (
                next((p for p in sorted(expected_hooks) if expected_hooks[p]["sha256"] == sha), None)
                if exit_ok and sha is not None else None
            )
            if matched is not None:
                if matched in seen_success:
                    issues.append(f"{ref['file']} line {ref['line']}: duplicate hook delivery for {matched}")
                seen_success.add(matched)
                base["hook_deliveries"].append({
                    "plugin": matched, "status": "success", "sha256": sha, "session_id": sid, "evidence": [ref],
                })
            else:
                base["hook_deliveries"].append({
                    "plugin": None, "status": "mismatch", "sha256": sha, "session_id": sid, "evidence": [ref],
                })
                issues.append(f"{ref['file']} line {ref['line']}: hook_success does not match any declared plugin's frozen session-start.md")
        for plugin in sorted(expected_hooks):
            if plugin not in seen_success:
                issues.append(f"declared plugin {plugin} has a frozen hook but no hook_success delivery row")
    sessions = [(None, root)]
    for name, sha256 in sorted(capture_info["sidechains"].items()):
        if name.startswith("agent-") and name.endswith(".jsonl"):
            file_label = "raw-subagents/" + name
            agent = name[len("agent-"):-len(".jsonl")]
            rows = claude_lines(retained(run, file_label, sha256), file_label, issues)
            sessions.append((agent, claude_session(rows, file_label, sid, agent, issues, hook_arm)))
    for tool_use_id, use in root["uses"].items():
        detail = (root["results"].get(tool_use_id) or {}).get("detail")
        if use["name"] in {"Agent", "Task"} and isinstance(detail, dict) and detail.get("agentId"):
            if f"agent-{detail['agentId']}.jsonl" not in capture_info["sidechains"]:
                issues.append(f"{capture_info['path']} line {use['line']}: subagent sidechain not captured")
    for agent, session in sessions:
        for tool_use_id, use in session["uses"].items():
            path = use["input"].get("file_path") if use["name"] == "Read" else None
            norm_path = posixpath.normpath(path) if isinstance(path, str) else None
            if use["name"] == "Skill" or norm_path in frozen:
                load = claude_load(tool_use_id, session, frozen, manifest, sid, agent, issues)
                base["loads" if agent is None else "child_loads"].append(load)
            elif norm_path in frozen_resources:
                rec = claude_resource_read(tool_use_id, session, frozen_resources, manifest, sid, agent)
                base["resource_reads" if agent is None else "child_resource_reads"].append(rec)
            elif use["name"] == "Bash" and isinstance(use["input"].get("command"), str):
                command = use["input"]["command"]
                seen_targets = set()
                for kind, target_id, match_path, pattern in bash_targets:
                    if pattern.search(command) and (kind, target_id) not in seen_targets:
                        seen_targets.add((kind, target_id))
                        base["unproved_reads"].append({
                            "path": match_path, kind: target_id, "session_id": sid, "agent_id": agent,
                            "proof": "bash_command_mentions_path", "status": "unproved", "evidence": [use["ref"]]})
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


SYNTHETIC_TARGETS = {
    ("skill", True): "loads",
    ("skill", False): "child_loads",
    ("resource", True): "resource_reads",
    ("resource", False): "child_resource_reads",
}


def synthetic_read_status(entry, req_path, event):
    body = event.get("body")
    body_sha = digest(body.encode()) if isinstance(body, str) else None
    valid_identity = bool(entry and req_path == entry["path"])
    matched = isinstance(body, str) and bool(entry) and body_sha == entry["sha256"]
    exit_code = event.get("exit_code")
    if valid_identity and type(exit_code) is int and exit_code != 0:
        return "failed", "nonzero exit_code", body_sha
    if type(exit_code) is int and exit_code == 0 and valid_identity:
        if event.get("body_complete") is True and matched:
            return "success", None, body_sha
        detail = "body_complete is not true" if event.get("body_complete") is not True else "content digest mismatch"
        return "partial", detail, body_sha
    detail = "unknown identity or path mismatch" if not valid_identity else "missing or non-integer exit_code"
    return "unavailable", detail, body_sha


def synthetic_record(kind, req, event_sid, status, detail, body_sha, completed_seq, evidence):
    ordering = "source_sequence" if completed_seq is not None else "unknown"
    if kind == "skill":
        return {"skill": req.get("skill"), "skill_path": req.get("path"), "status": status,
                "body_sha256": body_sha, "completed_seq": completed_seq, "session_id": event_sid,
                "proof": "full_body_read", "ordering": ordering, "evidence": evidence}
    return {"resource": req.get("resource"), "path": req.get("path"), "status": status,
            "detail": detail, "body_sha256": body_sha, "completed_seq": completed_seq,
            "session_id": event_sid, "agent_id": None, "proof": "full_body_read",
            "ordering": ordering, "evidence": evidence}


def normalize(run, relevant_kind=None):
    """Dispatch to the adapter that capture.json names; unknown native formats stay unscored."""
    manifest = verify_inputs(run)
    hook_arm = manifest.get("hook_arm", "hook-off")
    capture_info = read_json(run / "capture.json")
    raw = retained(run, capture_info["path"], capture_info["sha256"])
    base = {"schema_version": 1, "provider": "offline", "adapter_version": "synthetic-contract-v1",
            "evidence_kind": capture_info["evidence_kind"], "session_id": None,
            "session_state": capture_info["state"], "evidence_coverage": "unavailable",
            "coverage": {key: False for key in ("start", "end", "skill_delivery", "relevant_actions")},
            "raw_trace": {"path": raw.name, "sha256": capture_info["sha256"]},
            "loads": [], "child_loads": [], "resource_reads": [], "child_resource_reads": [],
            "unproved_reads": [], "hook_deliveries": [], "actions": [], "issues": [],
            "texts": [], "final_reply": None}
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
    child_sids = {
        e["session_id"] for _, e in events
        if e.get("type") == "session.started" and e.get("parent_session_id") == sid
        and isinstance(e.get("session_id"), str) and e["session_id"] and e["session_id"] != sid
    }
    last_root_line = max(line for line, event in events if event.get("session_id") == sid)
    base["coverage"]["start"] = start_line == 1
    requests = {}
    root_calls = []
    ended = False
    for line, event in events:
        event_sid = event.get("session_id")
        is_root = event_sid == sid
        if not is_root and event_sid not in child_sids:
            continue
        typ = event.get("type")
        ref = {"event_id": event["event_id"], "line": line}
        if is_root and ended:
            base["issues"].append("root event after terminal")
        if typ == "session.started":
            continue
        if typ == "hook.delivered":
            if not is_root:
                base["issues"].append("hook.delivered in child session")
                continue
            plugin = event.get("plugin")
            body = event.get("body")
            body_sha = digest(body.encode()) if isinstance(body, str) else None
            if hook_arm != "hook-on":
                base["issues"].append(f"unexpected hook.delivered in {hook_arm} arm")
                continue
            entry = manifest.get("hooks", {}).get(plugin) if isinstance(plugin, str) else None
            matched = entry is not None and body_sha == entry["sha256"]
            base["hook_deliveries"].append({
                "plugin": plugin, "status": "success" if matched else "mismatch",
                "sha256": body_sha, "session_id": sid, "evidence": [ref],
            })
            if not matched:
                base["issues"].append(f"hook.delivered mismatch for {plugin!r}")
        elif typ in {"skill_read.request", "resource_read.request"}:
            kind = "skill" if typ == "skill_read.request" else "resource"
            request_id = event.get("request_id")
            req_key = (event_sid, request_id)
            if not request_id or req_key in requests:
                base["issues"].append("invalid/duplicate request ID")
            else:
                requests[req_key] = (kind, event, ref)
                if is_root:
                    root_calls.append(line)
        elif typ in {"skill_read.result", "resource_read.result"}:
            kind = "skill" if typ == "skill_read.result" else "resource"
            req_key = (event_sid, event.get("request_id"))
            pending = requests.get(req_key)
            if pending is None or pending[0] != kind:
                base["issues"].append("unmatched read result")
                continue
            requests.pop(req_key)
            _, req, request_ref = pending
            if kind == "skill":
                entry = manifest["skills"].get(req.get("skill"))
            else:
                entry = manifest.get("resources", {}).get(req.get("resource"))
            status, detail, body_sha = synthetic_read_status(entry, req.get("path"), event)
            base[SYNTHETIC_TARGETS[(kind, is_root)]].append(
                synthetic_record(kind, req, event_sid, status, detail, body_sha, line, [request_ref, ref]))
        elif typ == "action.started":
            if not is_root:
                continue
            root_calls.append(line)
            if not isinstance(event.get("kind"), str):
                base["issues"].append("action missing semantic boundary")
            else:
                base["actions"].append({"kind": event["kind"], "seq": line, "session_id": sid,
                                         "ordering": "source_sequence", "evidence": [ref]})
        elif typ == "session.completed":
            if not is_root:
                continue
            ended = True
            base["coverage"]["end"] = line == last_root_line
            for field in ("skill_delivery", "relevant_actions"):
                base["coverage"][field] = event.get("coverage", {}).get(field) is True
        elif typ == "message":
            if is_root and event.get("role") == "assistant" and isinstance(event.get("text"), str):
                base["texts"].append({"seq": line, "text": event["text"], "session_id": sid, "evidence": [ref]})
        elif typ != "skill.mention":
            base["issues"].append(f"unknown record: {typ}")
    base["final_reply"] = final_reply(base["texts"], root_calls)
    for (req_sid, _), (kind, req, ref) in requests.items():
        detail = None if kind == "skill" else "no resource_read.result"
        base[SYNTHETIC_TARGETS[(kind, req_sid == sid)]].append(
            synthetic_record(kind, req, req_sid, "unavailable", detail, None, None, [ref]))
    if all(base["coverage"].values()) and not base["issues"] and capture_info["state"] == "completed":
        base["evidence_coverage"] = "complete"
    else:
        base["evidence_coverage"] = "partial"
    return base


def load_target(facet):
    """The evidence list and key that prove a load facet, or None when no scorer can see it."""
    plugin, path = facet["plugin"], facet.get("path")
    if facet.get("name_class") == "project-skill":
        return None
    if path and path.endswith("/SKILL.md"):
        return "skill", f"{plugin}:{posixpath.basename(posixpath.dirname(path))}"
    if facet["evidence"] == "skill-call":
        return "skill", f"{plugin}:{facet.get('name') or facet['subject']}"
    if facet["evidence"] == "full-read" and path:
        return "resource", f"{plugin}:{path}"
    return None


def load_status(evidence, facet, complete):
    target = load_target(facet)
    if target is None:
        return None
    kind, key = target
    field, name = ("loads", "skill") if kind == "skill" else ("resource_reads", "resource")
    records = [r for r in evidence[field] if r[name] == key]
    if facet["scope"] == "delegate-allowed":
        records += [r for r in evidence["child_" + field] if r[name] == key]
    if any(r["status"] == "success" for r in records):
        return "loaded"
    ambiguous = any(r["status"] in {"partial", "unavailable"} for r in records)
    return "miss" if complete and not ambiguous else "unavailable"


def route_line(texts, route, complete):
    for text in texts:
        found = ROUTE_LINE.search(text["text"])
        if found:
            same = LINE_KIND[found.group(1)] == route["route_type"] and found.group(2) == route["subject"]
            return {"status": "match" if same else "wrong", "observed": found.group(2)}
    return {"status": "missing" if complete else "unavailable", "observed": None}


def steps_entry(line, handles):
    for handle in sorted(handles, key=len, reverse=True):
        found = re.match(ENTRY_PREFIX + re.escape(handle) + r"(?![\w-])", line)
        if not found:
            continue
        rest = line[found.end():].lstrip(STATE_SEPARATORS)
        word = STATE_WORD.match(rest)
        state = word.group() if word else ""
        if state == "done":
            return handle, "done", None
        if state == "skip":
            raw = rest[word.end():]
            tail = raw.lstrip(REASON_SEPARATORS)
            reason = tail.rstrip()
            if "(" in raw[:len(raw) - len(tail)]:
                reason = reason.removesuffix(")").rstrip()
            return (handle, "skip", reason) if reason else (handle, "unclear", None)
        return handle, "unclear", None
    return None


def steps_section(reply, handles, complete):
    lines = (reply or "").split("\n")
    headings = [i for i, line in enumerate(lines) if not line[:1].isspace() and STEPS_HEADING.match(line.strip("#* \t"))]
    starts = [0, *(i + 1 for i in headings)]
    ends = [*headings, len(lines)]
    segments = [[e for e in (steps_entry(line, handles) for line in lines[a:b]) if e] for a, b in zip(starts, ends)]
    entries = max(reversed(segments), key=len)
    result = {"status": "missing" if complete else "unavailable", "heading": bool(headings), "done": [],
              "skipped": {}, "unclear_handles": [], "missing_handles": [], "out_of_order": False}
    if not entries:
        return result
    seen = [handle for handle, _, _ in entries]
    first_seen = list(dict.fromkeys(seen))
    result.update(
        done=[h for h, state, _ in entries if state == "done"],
        skipped={h: reason for h, state, reason in entries if state == "skip"},
        unclear_handles=[h for h, state, _ in entries if state == "unclear"],
        missing_handles=[h for h in handles if h not in seen],
        out_of_order=first_seen != [h for h in handles if h in first_seen])
    whole = (not result["missing_handles"] and not result["unclear_handles"] and not result["out_of_order"]
             and len(seen) == len(handles))
    result["status"] = "complete" if whole else "incomplete"
    return result


def route_facets(facets, route):
    return [f for f in facets.values() if f["plugin"] == route["plugin"] and f["subject"] == route["subject"]]


def route_allowed(facets, route):
    """The skills a run on this route may load: the router, the routed skill, the skills its steps and reply line
    name, and the skills its router's Triggers name, which hold in every route."""
    router = ROUTERS[route["plugin"]]
    allowed = {f"{route['plugin']}:{router}"}
    if route["route_type"] == "skill":
        allowed.add(f"{route['plugin']}:{route['subject']}")
    triggers = [f for f in facets.values()
                if f["kind"] == "trigger-load" and f["plugin"] == route["plugin"] and f["subject"] == router]
    for f in route_facets(facets, route) + triggers:
        target = load_target(f) if f["kind"] in {"step-load", "reply-load", "trigger-load"} else None
        if target and target[0] == "skill":
            allowed.add(target[1])
    return allowed


def route_score(case, facets, evidence, complete):
    route = facets[case["expected_route"]]
    plugin, slug = route["plugin"], route["subject"]
    own = route_facets(facets, route)
    playbook = route["route_type"] == "playbook"
    read = next(f for f in own if f["kind"] == ("playbook-read" if playbook else "route-load"))
    status = load_status(evidence, read, complete)
    handles = route["modes"][case["expected_mode"]] if route.get("modes") else route["handles"]
    section = steps_section(evidence["final_reply"], handles, complete)
    required, one_of, transitive = {}, {}, {}
    for f in own:
        if f["kind"] != "step-load" or f["handle"] not in section["done"]:
            continue
        found = load_status(evidence, f, complete)
        if found is None:
            continue
        if f["requirement"] == "one-of":
            group = one_of.setdefault(f["handle"], [])
            group.append(found)
        elif f["requirement"] == "transitive" and f["conditional"]:
            transitive.setdefault(f["name"], found)
        else:
            required.setdefault(f["name"], found)
    one_of = {h: "loaded" if "loaded" in found else "unavailable" if "unavailable" in found else "miss"
              for h, found in one_of.items()}
    transitive = {n: v for n, v in transitive.items() if n not in required}
    line = route_line(evidence["texts"], route, complete)
    checks = [line["status"], section["status"], status, *required.values(), *one_of.values()]
    failed = {"wrong", "missing", "miss", "incomplete"} & set(checks)
    unknown = {"unavailable"} & set(checks)
    return {"expected": case["expected_route"], "type": route["route_type"], "line": line,
            "playbook_read": {"loaded": "read"}.get(status, status) if playbook else None,
            "route_load": None if playbook else status,
            "steps_section": section,
            "step_loads": {"required": required, "one_of": one_of, "transitive": transitive},
            "followed": False if failed else None if unknown else True}


def score(args):
    run = Path(args.run).absolute()
    manifest = verify_inputs(run)
    if digest(Path(args.corpus).read_bytes()) != manifest["corpus_sha256"]:
        raise ValueError("answer-key corpus changed since materialization")
    facets_sha256 = manifest.get("facets_sha256")
    if facets_sha256 is not None and digest((HERE / "facets.json").read_bytes()) != facets_sha256:
        raise ValueError("facet map changed since materialization")
    case = next(c for c in corpus(args.corpus) if c["id"] == manifest["case_id"])
    evidence = normalize(run, case["relevant_action"])
    scorer_sha256 = digest(Path(__file__).read_bytes())
    hook_arm = manifest.get("hook_arm", "hook-off")
    configuration = {field: manifest[field] for field in ("runtime", "source_catalog_files",
                                                         "removed_bindings", "corpus_sha256", "fixture_catalog_files",
                                                         "harness_sha256")}
    configuration.update(hook_arm=hook_arm, facets_sha256=facets_sha256, adapter_version=evidence["adapter_version"], scorer_sha256=scorer_sha256)
    configuration_sha256 = digest(json.dumps(configuration, sort_keys=True).encode())
    save_json(run / "evidence.json", evidence)
    observed = {canonical_skill(load["skill"]) for load in evidence["loads"] if load["status"] == "success"}
    forbidden = {canonical_skill(s) for s in case["forbidden_skills"]}
    plugin = case["target"].split(":")[0]
    facets = load_facets()
    route_allowed_skills = set()
    if case.get("expected_route"):
        route_skills = {canonical_skill(s) for s in route_allowed(facets, facets[case["expected_route"]])}
        route_allowed_skills = (route_skills | ALWAYS_ON[(plugin, hook_arm)]) - forbidden
    else:
        if "swe:swe-mode" in case["expected_skills"] + case["acceptable_auxiliaries"]:
            route_allowed_skills |= {"swe:writing"}
        if hook_arm == "hook-on":
            route_allowed_skills |= HOOK_ON_ALWAYS_ON
        route_allowed_skills -= forbidden
    allowed = {canonical_skill(s) for s in case["expected_skills"] + case["acceptable_auxiliaries"]} | route_allowed_skills
    complete = evidence["evidence_coverage"] == "complete" and evidence["session_state"] == "completed"
    ambiguous_forbidden = any(canonical_skill(l["skill"]) in forbidden and l["status"] in {"partial", "unavailable"}
                              for l in evidence["loads"])
    activation = {}
    timing = {}
    actions = [a["seq"] for a in evidence["actions"] if a["kind"] == case["relevant_action"]]
    for skill in case["expected_skills"]:
        target = canonical_skill(skill)
        loads = [l["completed_seq"] for l in evidence["loads"]
                 if canonical_skill(l["skill"]) == target and l["status"] == "success"]
        ambiguous = any(canonical_skill(l["skill"]) == target and l["status"] in {"partial", "unavailable"}
                        for l in evidence["loads"])
        activation[skill] = "loaded" if loads else "miss" if complete and not ambiguous else "unavailable"
        action_coverage = evidence["coverage"]["start"] and evidence["coverage"]["relevant_actions"] and not evidence["issues"]
        timing[skill] = ("before" if min(loads) < min(actions) else "late") if loads and actions and action_coverage else "unavailable"
    route = route_score(case, facets, evidence, complete) if case.get("expected_route") else None
    result = {"schema_version": 1, "case_id": case["id"], "target": case["target"], "category": case["category"],
              "hook_arm": hook_arm, "configuration_sha256": configuration_sha256, "scorer_sha256": scorer_sha256,
              "runtime": manifest["runtime"], "adapter_version": evidence["adapter_version"],
              "split": case["split"], "family": case.get("family", case["target"]), "evidence_kind": evidence["evidence_kind"],
              "session_state": evidence["session_state"], "evidence_coverage": evidence["evidence_coverage"],
              "activation": activation, "timing": timing, "observed_skills": sorted(observed),
              "expected_skills": case["expected_skills"], "allowed_skills": sorted(allowed),
              "unresolved_skills": sorted({canonical_skill(l["skill"]) for l in evidence["loads"]
                                             if l["status"] in {"partial", "unavailable"}} - observed),
              "false_activation": True if observed & forbidden else False if complete and not ambiguous_forbidden else None,
              "unexpected_skills": sorted(observed - allowed),
              "observed_resources": sorted({r["resource"] for r in evidence["resource_reads"] if r["status"] == "success"}),
              "child_observed_skills": sorted({l["skill"] for l in evidence["child_loads"] if l["status"] == "success"}),
              "child_observed_resources": sorted({r["resource"] for r in evidence["child_resource_reads"] if r["status"] == "success"}),
              "unproved_read_count": len(evidence["unproved_reads"]),
              "load_status_counts": dict(Counter(l["status"] for l in evidence["loads"])),
              "raw_trace": evidence["raw_trace"], "manifest_sha256": digest((run / "manifest.json").read_bytes()),
              "route": route, "route_allowed_skills": sorted(route_allowed_skills),
              "facets": {f: load_status(evidence, facets[f], complete) for f in case.get("facets", [])},
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
    others = defaultdict(lambda: defaultdict(Counter))
    for row in rows:
        key = (row["configuration_sha256"], row.get("hook_arm", "hook-off"), row["evidence_kind"],
               row["split"], row["target"], "explicit_control" if row["category"] == "explicit" else "implicit",
               row.get("family", row["target"]))
        group = groups.setdefault(key, Counter())
        group["runs"] += 1
        group["session_" + row["session_state"]] += 1
        group["coverage_" + row["evidence_coverage"]] += 1
        complete = row["evidence_coverage"] == "complete" and row["session_state"] == "completed"
        group["complete_sessions"] += int(complete)
        strata_rows[key].append((row, complete))
        if row.get("route"):
            route = row["route"]
            group[f"route_followed_{str(route['followed']).lower() if route['followed'] is not None else 'null'}"] += 1
            group["route_line_" + route["line"]["status"]] += 1
            group["route_steps_" + route["steps_section"]["status"]] += 1
            group["route_read_" + (route["playbook_read"] or route["route_load"])] += 1
        if complete:
            for skill in row["expected_skills"]:
                if skill != row["target"]:
                    others[key][skill][row["activation"].get(skill, "unavailable")] += 1
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
        report.append({"configuration_sha256": key[0], "hook_arm": key[1], "runtime": strata_rows[key][0][0]["runtime"],
                       "evidence_kind": key[2], "split": key[3], "target": key[4], "experiment": key[5], "family": key[6],
                       "counts": dict(counts),
                       "other_expected": [{"skill": skill, **{state: found[state] for state in
                                                              ("loaded", "miss", "unavailable")}}
                                          for skill, found in sorted(others[key].items())],
                       "recall": counts["positive_loaded"] / denominator if denominator else None,
                       "recall_denominator": denominator,
                       "false_activation_rate": counts["false_activations"] / negatives if negatives else None,
                       "false_activation_denominator": negatives})
    confusion_rows = []
    for (key, expected, unexpected), counts in sorted(confusion.items()):
        denominator = sum(complete and tuple(row["expected_skills"]) == expected
                          and unexpected not in row["allowed_skills"] and unexpected not in row["unresolved_skills"]
                          for row, complete in strata_rows[key])
        confusion_rows.append({"configuration_sha256": key[0], "hook_arm": key[1], "evidence_kind": key[2],
                               "split": key[3], "target": key[4], "experiment": key[5], "family": key[6],
                               "expected_skills": list(expected),
                               "unexpected": unexpected, "count": counts["scorable"], "denominator": denominator,
                               "rate": counts["scorable"] / denominator if denominator else None,
                               "interrupted_or_partial_observations": counts["interrupted_or_partial"]})
    return {"schema_version": 1, "groups": report, "confusion": confusion_rows,
            "warning": "Activation evidence only; no task utility is measured. Synthetic groups verify harness behavior only."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    prep = commands.add_parser("materialize")
    prep.add_argument("--case", required=True)
    prep.add_argument("--runtime", required=True, type=Path)
    prep.add_argument("--output", required=True, type=Path)
    prep.add_argument("--output-root", type=Path, help="folder that --output must sit under; default artifacts/skill-evals")
    prep.add_argument("--hook-arm", choices=("hook-off", "hook-on"), default="hook-off",
                      help="hook-off removes all plugin hooks; hook-on keeps each plugin's SessionStart hook")
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
    cap.add_argument("--stream-appended-final-newline", action="store_true",
                     help="claude-transcript: the caller added the final newline the stream file lacked")
    cap.add_argument("--relevant-action", metavar="TOOL_USE_ID",
                     help="claude-transcript: root tool_use id that starts the case's relevant action, or 'none'")
    sc = commands.add_parser("score")
    sc.add_argument("--run", required=True, type=Path)
    ag = commands.add_parser("aggregate")
    ag.add_argument("scores", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            cases = corpus(args.corpus)
            result = {"cases": len(cases), "targets": sorted(TARGETS)}
        else:
            result = {"materialize": materialize, "capture": capture, "score": score, "aggregate": aggregate}[args.command](args)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(2, f"skill-eval: {error}\n")


if __name__ == "__main__":
    main()
