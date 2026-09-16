"""Read current mapped resources and PR evidence; propose, never apply, repairs."""
import core


def audit(packet, config, evidence, *, store=None, adapter=None):
    findings = list(core.collect_validation_errors(packet, config))
    mappings = store.list_mappings() if store else []
    if not mappings:
        findings.append({"code": "publication_unverified"})
    observed = {}
    for mapping in mappings:
        key = mapping["logical_key"]
        if mapping.get("status") != "active":
            findings.append({"code": "publication_pending", "logical_key": key})
            continue
        try:
            value = core.remote_get(adapter, mapping["kind"], mapping["native_id"], key)
            if value is None:
                findings.append({"code": "mapping_missing", "logical_key": key})
            elif value.get("archived"):
                findings.append({"code": "mapping_archived", "logical_key": key})
            else:
                observed[key] = value
                if value.get("id") != mapping["native_id"] or (
                    mapping.get("readback_hash") and
                    core.owned_hash(mapping["kind"], value) != mapping["readback_hash"]
                ):
                    findings.append({"code": "human_edit_conflict", "logical_key": key})
        except core.CoreError as exc:
            findings.append({"code": exc.code, "logical_key": key})
    if store and store.get_meta("last_publish:" + packet["spec"]["spec_id"], {}).get("digest") != core.semantic_digest(packet):
        findings.append({"code": "publication_revision_unverified"})
    project = observed.get("project:" + packet["spec"]["spec_id"])
    hold_ids = set(config.get("integration", {}).get("hold_label_ids", []))
    hold_id = config.get("integration", {}).get("needs_human_label_id")
    if hold_id:
        hold_ids.add(hold_id)
    tasks = []
    for task in packet["tasks"]:
        issue = observed.get("issue:" + task["task_id"])
        reasons = []
        if not issue:
            reasons.append({"code": "issue_unverified"})
        elif not project or issue.get("project_id") != project["id"]:
            reasons.append({"code": "project_membership_unverified"})
        if issue and hold_ids.intersection(issue.get("label_ids", [])):
            reasons.append({"code": "human_hold", "action": "Preserve the hold; ask its owner if clarification is needed."})
        if task["kind"] == "code":
            reasons.extend(core.verify_code_completion(task, config, evidence))
        else:
            reasons.append({"code": "human_result_review_required", "action": "Inspect the issue's result, provenance, acceptance evidence and independent review."})
        if findings:
            reasons.append({"code": "publication_requires_reconciliation"})
        tasks.append({
            "task_id": task["task_id"], "findings": reasons,
            "code_delivery_evidence_satisfied": task["kind"] == "code" and not reasons,
            "current_status": (issue or {}).get("state_name"),
            "next_action": "Review task acceptance, latest issue handoff, unresolved jobs and required human approval. Change status only within explicit authority." if not reasons else "Resolve the listed evidence gaps; preserve current human changes.",
        })
    return {
        "ok": not findings and all(not task["findings"] for task in tasks),
        "operation": "audit", "applied": False, "observed_at": core.now_iso(),
        "findings": findings, "tasks": tasks,
        "note": "One-shot observations. Passing PR evidence is a delivery candidate; this report never marks work Done or proves scientific validity, task ownership, or background execution.",
    }
