#!/usr/bin/env python3
"""Offline activation corpus materialization, evidence capture and scoring.

No provider invocation, network dependency, or user configuration mutation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
TARGETS = {"swe:" + name for name in (
    "implement", "diagnose", "testing-code", "test-audit",
    "improve-codebase-architecture", "write-plan")}
COUNTS = {"natural": 4, "contextual": 2, "negative": 3, "explicit": 1}
RUNTIME_FIELDS = {"model", "effort", "cli", "cli_version", "permissions", "tools",
                  "harness_deltas", "catalog_scope", "context_delivery"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


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


def corpus(path=HERE / "cases.json"):
    data = read_json(path)
    if data.get("schema_version") != 1:
        raise ValueError("unsupported corpus schema")
    cases = data["cases"]
    ids = set()
    groups = defaultdict(Counter)
    skills = catalog_skills()
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
            if set(case[field]) - skills:
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
        raise ValueError("expected six targets, each with 4/2/3/1 cases")
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
        skills[skill] = {"path": str(file.absolute()), "sha256": digest(file.read_bytes())}
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


def capture(args):
    run = Path(args.run).absolute()
    verify_inputs(run)
    raw = run / "raw.jsonl"
    data = Path(args.source).read_bytes()
    inventory(run / "workspace")  # Reject model-created links before copytree can dereference them.
    # Retain bytes even if a provider trace is not parseable by the offline adapter.
    with raw.open("xb") as handle:
        handle.write(data)
    shutil.copytree(run / "workspace", run / "final-files", ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
    save_json(run / "capture.json", {"schema_version": 1, "sha256": digest(data), "path": raw.name,
                                     "source": str(Path(args.source).absolute()), "state": args.state,
                                     "format": args.format, "evidence_kind": args.evidence_kind,
                                     "final_files": inventory(run / "final-files")})
    return {"raw": str(raw), "sha256": digest(data), "state": args.state}


def normalize(run):
    """Only the documented synthetic trace envelope is supported in this slice."""
    manifest = verify_inputs(run)
    capture_info = read_json(run / "capture.json")
    raw = run / capture_info["path"]
    if digest(raw.read_bytes()) != capture_info["sha256"]:
        raise ValueError("raw trace digest mismatch")
    base = {"schema_version": 1, "provider": "offline", "adapter_version": "synthetic-contract-v1",
            "evidence_kind": capture_info["evidence_kind"], "session_id": None,
            "session_state": capture_info["state"], "evidence_coverage": "unavailable",
            "coverage": {key: False for key in ("start", "end", "skill_delivery", "relevant_actions")},
            "raw_trace": {"path": raw.name, "sha256": capture_info["sha256"]},
            "loads": [], "actions": [], "issues": []}
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
    evidence = normalize(run)
    scorer_sha256 = digest(Path(__file__).read_bytes())
    configuration = {field: manifest[field] for field in ("runtime", "plugin_versions", "source_catalog_files",
                                                         "removed_bindings", "corpus_sha256", "fixture_catalog_files",
                                                         "harness_sha256")}
    configuration.update(adapter_version=evidence["adapter_version"], scorer_sha256=scorer_sha256)
    configuration_sha256 = digest(json.dumps(configuration, sort_keys=True).encode())
    save_json(run / "evidence.json", evidence)
    observed = {load["skill"] for load in evidence["loads"] if load["status"] == "success"}
    allowed = set(case["expected_skills"]) | set(case["acceptable_auxiliaries"])
    forbidden = set(case["forbidden_skills"])
    complete = evidence["evidence_coverage"] == "complete" and evidence["session_state"] == "completed"
    ambiguous_forbidden = any(l["skill"] in forbidden and l["status"] in {"partial", "unavailable"}
                              for l in evidence["loads"])
    activation = {}
    timing = {}
    actions = [a["seq"] for a in evidence["actions"] if a["kind"] == case["relevant_action"]]
    for skill in case["expected_skills"]:
        loads = [l["completed_seq"] for l in evidence["loads"] if l["skill"] == skill and l["status"] == "success"]
        ambiguous = any(l["skill"] == skill and l["status"] in {"partial", "unavailable"} for l in evidence["loads"])
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
            "warning": "Synthetic records verify harness behavior only; no native model efficacy measured."}


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
    cap.add_argument("--format", choices=("native", "synthetic-contract-v1"), default="native")
    cap.add_argument("--evidence-kind", choices=("native", "synthetic"), default="native")
    sc = commands.add_parser("score")
    sc.add_argument("--run", required=True, type=Path)
    ag = commands.add_parser("aggregate")
    ag.add_argument("scores", nargs="+", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            result = {"cases": len(corpus(args.corpus)), "targets": sorted(TARGETS)}
        else:
            result = {"materialize": materialize, "capture": capture, "score": score, "aggregate": aggregate}[args.command](args)
        print(json.dumps(result, indent=2, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError, StopIteration, subprocess.CalledProcessError) as error:
        parser.exit(2, f"skill-eval: {error}\n")


if __name__ == "__main__":
    main()
