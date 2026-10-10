# Activation evidence v1

This pilot uses a local interface, with no dependency on the general trace
framework. `skill_eval.py score` derives `evidence.json` from retained raw JSONL;
it does not accept an execution agent's self-report as a grade.

The normalized record has `schema_version`, `provider`, `adapter_version`,
`evidence_kind`, `session_id`, `session_state`, `evidence_coverage`, `coverage`,
`raw_trace`, `loads`, `actions`, and `issues`.

`raw_trace` contains a relative path and SHA-256 digest. Each evidence reference
contains a stable `event_id` and a one-based raw JSONL `line`. Array order is
source order; timestamps are not used to infer order. This intentionally small
interface is for one root session. Child-session events remain in the raw trace
but cannot satisfy root-session activation. A trailing child event does not
invalidate the root terminal; end coverage is checked against the last root event.

Load records contain:

- `skill`: fully qualified ID, such as `swe:implement`.
- `skill_path`: exact frozen `SKILL.md` path, independently of body identity.
- `status`: `success`, `failed`, `partial`, or `unavailable`.
- `body_sha256`, `completed_seq`, `session_id`, and `evidence` references.
- `proof`: `full_body_read` for this adapter. A future native Skill adapter must
  establish `skill_body_delivery` with both a successful invocation result and
  the delivered instruction body.
- `ordering`: `source_sequence` or `unknown`. Completion means delivery ended,
  rather than the read request started.

Action records contain `kind`, `seq`, `session_id`, `ordering`, and `evidence`.
`seq` is the start of the first case-defined relevant action. Each case's
`relevant_action` is a semantic boundary, not a substring in a shell command.
Load completion must strictly precede action start. Missing action evidence is
unavailable timing; no inferred timing from a final answer or skill mention.

`coverage` separately records `start`, `end`, `skill_delivery`, and
`relevant_actions`. A byte-complete file does not prove observable instruction
delivery or action coverage. Unknown records, malformed events, interrupted
sessions, or missing coverage make the session partial/unavailable. Failed
read attempts remain failed; partial bodies and pending reads remain distinct.
Absence of a provider error flag alone cannot establish success.

## Synthetic offline envelope

This is a **sanitized synthetic fixture protocol**, not the native Codex or
Claude JSONL schema. Its only purpose is to test the evidence/scoring contract.
Every event has a unique string `event_id`, `session_id`, and `type`.

| Type | Required payload |
|---|---|
| `session.started` | root `session_id`, optional `parent_session_id` |
| `skill_read.request` | `request_id`, `skill`, exact frozen `path` |
| `skill_read.result` | matching `request_id`, integer `exit_code`, delivered `body`, Boolean `body_complete` |
| `action.started` | `kind`, matching case boundary |
| `session.completed` | `coverage: {skill_delivery: true, relevant_actions: true}` |
| `message`, `skill.mention` | text ignored by activation scoring |

Sequence numbers are one-based lines. A successful read requires integer zero
exit status, matching skill ID/path, `body_complete: true`, and an exact digest
of the delivered UTF-8 body against the materialized catalog. A nonzero exit
status is failed even if the output contains a skill body. Unknown identity or
missing status is unavailable. A successful but incomplete/mismatched body is
partial. A result before its request cannot count as a load.

Capture metadata must identify both `format: synthetic-contract-v1` and
`evidence_kind: synthetic` to enable this adapter. Native traces are retained
unchanged and yield `native_adapter_unverified`, with unavailable metrics.
Synthetic success is never reported as measured model activation or utility.

## Native pilot gate

Before implementing a provider adapter, capture a small authorized fresh-session
pilot and verify the native request/result/body-delivery surface, exact skill
identity, completeness/truncation, terminal status, root/child boundaries, and
load-completion versus action-start ordering. Codex `exec --json` may omit body
output needed for this proof; a command mentioning a skill path cannot replace
it. A Claude `Skill` result must be paired with delivered-body evidence.

Freeze the complete effective competitor catalog, provider/model/effort,
CLI version, prompts/context delivery, fixtures, permissions, available tools,
configuration and hook deltas. Verify fresh session and read/write/network
isolation. The prepared directory and stripped bindings alone do not establish
provider isolation. No live model matrix is authorized in this slice.
