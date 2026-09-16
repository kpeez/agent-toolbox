"""Synthetic local fixtures and executable demo; never constructs a live adapter."""
from pathlib import Path
from types import SimpleNamespace

import core
from adapters import FakeAdapter

SPEC_ID = "11111111-1111-4111-8111-111111111111"
TASK_ID = "22222222-2222-4222-8222-222222222222"
HOST = "fixture-host"


def fixture(root):
    """Synthetic packet, operator config and external authority; no live records."""
    root = Path(root).resolve()
    (root / "knowledge").mkdir(parents=True, exist_ok=True)
    (root / "code").mkdir(exist_ok=True)
    note = root / "knowledge" / "decision.md"
    note.write_text("# Synthetic decision\nPreserve caller-supplied ordering.\n")
    packet = {
        "schema_version": 1,
        "spec": {
            "spec_id": SPEC_ID, "title": "Stable ordering",
            "markdown": "# Stable ordering\n\nPreserve caller-supplied ordering.",
            "metadata": {"tracker": "linear", "legacy_owner": "example"},
        },
        "project": {
            "name": "Stable ordering",
            "summary": "Preserve ordering for callers.",
            "closure": "Required changes delivered and reviewed; final conclusion recorded.",
        },
        "context": [{
            "id": "ordering-decision", "title": "Ordering decision", "role": "context",
            "relevance": "Explains which ordering behavior must remain stable.",
            "documentation_root": "knowledge", "path": "decision.md", "revision": "decision-v1",
            "content_hash": core.sha256_hex(note.read_bytes()), "knowledge_date": "2026-09-15",
            "standing": "current", "access": "local", "essential": True, "disclosure": "private",
        }],
        "tasks": [{
            "task_id": TASK_ID, "title": "Preserve supplied order",
            "outcome": "Callers receive their supplied order.",
            "acceptance": ["The supplied order survives a round trip; verify with the unit suite."],
            "kind": "code", "context_ids": ["ordering-decision"], "dependencies": [],
            "repository": "widget", "base_branch": "integration",
            "completion": {"required_prs": [{
                "repo": "example/widget", "number": 41, "head_sha": "a" * 40,
                "required_checks": ["unit"], "required_reviewers": ["human-reviewer"],
            }]},
        }],
    }
    config = {
        "schema_version": 1,
        "documentation_roots": {"knowledge": {"path": str(root / "knowledge"), "host": HOST}},
        "code_roots": {"widget": str(root / "code")},
        "repositories": {"widget": {
            "repo": "example/widget", "base_branch": "integration",
            "code_root": str(root / "code"), "label_ids": ["repo-widget"],
        }},
                "integration": {
            "team_id": "team-example",
            "status_ids": {"todo": "state-todo", "in_progress": "state-progress",
                           "in_review": "state-review", "done": "state-done"},
            "visibility": "private", "needs_human_label_id": "hold-example", "hold_label_ids": ["hold-example"],
        },
        "privacy": {"deny_private": ["private-example-identifier", "private excerpt used only as a fixture"]},
        "live_pilot_enabled": False,
    }
    authority = {
        "spec_approval": {
            "spec_id": SPEC_ID, "digest": core.semantic_digest(packet),
            "approved_by": "synthetic-operator", "source": "synthetic fixture only",
            "approved_at": core.now_iso(),
        },
        "permission": {
            "spec_id": SPEC_ID, "project_id": None, "create_project": True,
            "actions": ["publish", "record"], "authorized_by": "synthetic-operator",
            "source": "synthetic fixture only",
        },
    }
    return packet, config, authority


def handoff_request(root):
    return {
        "request_id": core.new_uuid4(), "task_id": TASK_ID, "kind": "handoff",
        "observed_at": core.now_iso(),
        "summary": "Hand off the synthetic task to a successor operator.",
        "facts": {
            "owner": "agent-example", "issue": "mapped issue",
            "worktree": str(Path(root).resolve() / "code"), "running_jobs": [],
            "condition": "awaiting_input",
            "what_not_repeat": "Do not create another project or repeat publication.",
        },
        "next_action": "Read the latest note, inspect the mapped issue, and verify before resuming.",
    }


def evidence_fixture():
    return {"example/widget#41": {
        "repo": "example/widget", "number": 41, "base_branch": "integration",
        "head_sha": "a" * 40, "draft": False, "merged": True, "merge_commit_sha": "b" * 40,
        "checks": [{"name": "unit", "sha": "a" * 40, "conclusion": "success"}],
        "reviews": [{"actor": "human-reviewer", "commit_sha": "a" * 40, "state": "approved"}],
    }}


def run_demo(root):
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise core.CoreError("bad_request", "Demo requires a new or empty directory; existing work is preserved")
    root.mkdir(parents=True, exist_ok=True)
    packet, config, authority = fixture(root)
    evidence_data = evidence_fixture()
    handoff = handoff_request(root)

    core.dump_json(str(root / "packet.json"), packet)
    core.dump_json(str(root / "config.json"), config)
    core.dump_json(str(root / "authority.json"), authority)
    core.dump_json(str(root / "request-handoff.json"), handoff)
    core.dump_json(str(root / "evidence.json"), evidence_data)

    adapter = FakeAdapter(str(root / "state.json.fake.json"))
    store = core.Store(str(root / "state.json"))
    try:
        validation = core.collect_validation_errors(packet, config)
        if validation:
            raise core.CoreError("validation_failed", "Synthetic fixture failed validation", details=validation)
        rendered = core.render_packet(packet, config)
        preview = core.publish(packet, config, authority, store=store, adapter=adapter)
        first = core.publish(packet, config, authority, apply=True, store=store, adapter=adapter)
        repeated = core.publish(packet, config, authority, apply=True, store=store, adapter=adapter)
        authority["permission"]["project_id"] = first["mappings"]["tracker_container"]
        core.dump_json(str(root / "authority.json"), authority)
        recorded = core.record(packet, config, handoff, apply=True, store=store, adapter=adapter, authority=authority)
        from audit import audit
        audit_result = audit(packet, config, SimpleNamespace(pull_request=lambda repo, number: evidence_data["%s#%s" % (repo, number)]),
                             store=store, adapter=adapter)
        result = {
            "ok": True, "evidence_source": "controlled_fixture", "directory": str(root),
            "validation": {"ok": True, "errors": []}, "rendered_markdown": rendered,
            "preview": preview, "first_publication": first, "repeated_publication": repeated,
            "record": recorded, "audit": audit_result,
            "note": ("Synthetic validate/render/preview/apply/repeat/record/audit. Request files are "
                     "replayable receipts. No live records, tokens, research or jobs were touched."),
        }
        core.dump_json(str(root / "demo-receipt.json"), result)
        return result
    finally:
        store.close()
