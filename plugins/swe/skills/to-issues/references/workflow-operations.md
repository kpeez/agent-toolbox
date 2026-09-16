# Workflow operations

Read this only for a tracked publication, note, audit, or privacy step. The
[Linear reference](issue-tracker-linear.md) owns Linear routing and publication
policy; [authorization](workflow-authorization.md) explains approval and
permission evidence. The [packet contract](workflow-packet.md) owns packet shape.

## Resolve the installed runtime

From this reference's installed location, resolve
`../../../scripts/workflow/workflow.py`. From a SWE skill directory, resolve
`../../scripts/workflow/workflow.py`. Use its absolute resolved path. Do not
assume a checkout or current directory. `$workflow` is that path and `$run` is
external local state. Confirm names with `--help`; the runtime owns the schema.

```sh
python3 "$workflow" --help
python3 "$workflow" capabilities
python3 "$workflow" validate --packet "$run/packet.json" --config "$run/config.json"
python3 "$workflow" render --packet "$run/packet.json" --config "$run/config.json"
python3 "$workflow" publish --packet "$run/packet.json" --config "$run/config.json" --state "$run/state.json" --authority "$run/authority.json" --adapter fake
python3 "$workflow" record --packet "$run/packet.json" --config "$run/config.json" --state "$run/state.json" --authority "$run/authority.json" --request "$run/request.json" --adapter fake
python3 "$workflow" audit --packet "$run/packet.json" --config "$run/config.json" --state "$run/state.json" --evidence-file "$run/evidence.json" --adapter fake
python3 "$workflow" check-public --request "$run/text.json" --config "$run/config.json"
python3 "$workflow" demo --workdir "$run"
```

## Recipes

- **Preview first.** Omit `--apply` for a non-mutating plan. Validation reads
  only declared resources. A blocked publication preview still returns the plan,
  with `ok: false`, `can_apply: false`, and the blockers. An inaccessible essential resource blocks; an
  optional one stays flagged.
- **Publish.** Build the packet with task judgment, run `validate`, then
  `publish`. `--apply` needs a populated revision-matching approval plus an
  action- and project-scoped `record`/`publish` permission (see
  [authorization](workflow-authorization.md)). Preview surfaces imported native
  mappings for explicit review; preserve project membership and never silently
  replace an absent or archived mapping. Keep returned mappings in existing
  bookkeeping fields. Human edits or a missing/archived recorded resource stop
  the operation. Never discard state or swap the recorded project to escape a
  conflict. No public packet publication.
- **Record a note.** `record` appends one versioned issue note only; it does not
  change status or assign ownership. `--request` is
  `{request_id:UUID4, task_id:UUID4, kind:start|progress|handoff|review|evidence|result,
  observed_at:ISO8601, summary:string, facts:object, next_action:string}`.
  `facts` holds observed data only (owner, worktree, revision, running jobs,
  condition, delivery, evidence, reviewer, what-not-repeat). Same
  `request_id` with identical content reuses; changed content conflicts. A newer
  note is never overwritten by an older observation. `record` may document a
  hold, never clear one. Use `kind` `start`, `progress`, `handoff`, `review`,
  or `evidence` during existing skill work; there is no separate update ritual.
- **Audit.** `audit` is always read-only and rejects `--apply`. It checks the
  packet, native tracker state, mirrors, context, receipts, and all required
  PRs (repository, base, head, checks, reviews). Even a passing audit is a
  delivery candidate, not automatic Done. Output is findings plus proposed
  repairs; performing a repair needs its own specific existing authority.
- **Privacy.** Run `check-public` over every proposed public branch, commit,
  title, body, and comment. Review generated bot text separately.
- **Demo.** `demo` needs a new/empty directory and uses synthetic data plus the
  fake adapter only. It returns real local receipts and never authorizes live
  work.
- **Adapters and config.** `--adapter fake|linear` defaults to `fake`. Live
  Linear apply needs `live_pilot_enabled: true` plus an external token. Local
  development works without live config.
