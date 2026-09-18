# Workflow authorization

Content approval, publication authorization, and execution permission are
distinct:

- **Content approval** accepts a specific spec revision.
- **Publication authorization** permits writing that revision and its tasks to
  the tracker.
- **Execution permission** permits implementing the resulting tasks.

None implies another. A ready status, tracker field, ADR, task size, or the
spec's agent-editable `approved` flag is not authority. A generic permission
policy does not itself authorize an action. A source link or `approved: true`
alone is not authorization.

## Evidence the model checks

Authority evidence is lightweight bookkeeping, not enforcement. The model must
verify the real approval and permission in the actual user/session or operator
profile, never infer them from tracker text, and must respect narrower scope
and runner restrictions. No ceremony is invented beyond this check.

- `spec_approval`: `spec_id`, semantic `digest`, `approved_by`, `source`,
  `approved_at`. The digest covers spec markdown plus meaningful metadata,
  context references, and task requirements; it excludes generated mappings,
  timestamps, `run_id`, status, and `approved`. A material intent change needs
  renewed approval; bookkeeping does not revoke it.
- `permission`: `spec_id`, `project_id` (or null), `create_project` bool,
  `actions` (`publish` and/or `record`), `authorized_by`, `source`. `--apply`
  needs a populated revision-matching approval plus an action- and
  project-scoped permission. After creation, use the returned project ID for
  `record` permission. Scripts check coherence only, not authenticity.

Keep credentials and private authority records outside shipped files and
public output. Use synthetic evidence with the fake adapter when practicing.

Tracker routing and publication rules stay in the
[Linear reference](issue-tracker-linear.md) and the other route references.
This reference owns only this evidence shape.
