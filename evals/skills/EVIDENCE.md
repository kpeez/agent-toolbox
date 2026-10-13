# Activation evidence v1

This pilot uses a local interface, with no dependency on the general trace
framework. `skill_eval.py score` derives `evidence.json` from retained raw JSONL;
it does not accept an execution agent's self-report as a grade.

The normalized record has `schema_version`, `provider`, `adapter_version`,
`evidence_kind`, `session_id`, `session_state`, `evidence_coverage`, `coverage`,
`raw_trace`, `loads`, `actions`, and `issues`.

`raw_trace` contains a relative path and SHA-256 digest. Each evidence reference
contains a stable `event_id` and a one-based raw JSONL `line`; a Claude reference
also names its `file`, because one session spans several files. Array order is
source order; timestamps are not used to infer order. This intentionally small
interface is for one root session. Child-session events remain in the raw trace
but cannot satisfy root-session activation. A trailing child event does not
invalidate the root terminal; end coverage is checked against the last root event.

Load records contain:

- `skill`: fully qualified ID, such as `swe:implement`.
- `skill_path`: exact frozen `SKILL.md` path, independently of body identity.
- `status`: `success`, `failed`, `partial`, or `unavailable`.
- `body_sha256`, `completed_seq`, `session_id`, and `evidence` references.
- `proof`: `full_body_read` (a complete read of the frozen file) or
  `skill_body_delivery` (a successful invocation result and the delivered
  instruction body). The synthetic adapter uses only `full_body_read`.
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
`evidence_kind: synthetic` to enable this adapter. A trace captured as
`--format native` is retained unchanged and yields `native_adapter_unverified`,
with unavailable metrics. Synthetic success is never reported as measured model
activation or utility.

## Native pilot gate

Before an adapter scores a new provider or surface, capture a small authorized fresh-session
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

## Claude transcript adapter

`--format claude-transcript` selects adapter `claude-transcript-v1`. It reads
the Claude Code session transcript, not stream-json. The audited producer is
Claude Code 2.1.296 in headless `-p` mode. The probe evidence is in
`/home/kylep/artifacts/agent-toolbox/swe-router-rewrite/probes/claude-trace-format/`
(`analyze.out`, `read-check.out`, and the copied transcripts).

Capture inputs:

- `--source`: the root transcript `<session>.jsonl`. Capture also copies every
  file in the sibling `<session>/subagents/` directory to `raw-subagents/` and
  records each digest.
- `--plugin-dir`: each absolute path given to `claude --plugin-dir`. Capture
  refuses a directory whose `skills/*/SKILL.md` files differ from the frozen
  catalog in name or bytes. A run that uses the materialized catalog passes
  `<run>/inputs/plugins/<plugin>` to both commands.
- `--stream`: the session's stream-json output. Only its `result` event shows
  that the session ended.
- `--relevant-action`: the root `tool_use` id where the case's relevant action
  starts, or `none` when no such action happened. A person sets this label from
  the raw trace and the case's `relevant_action` text. Without it, timing is
  unavailable and the evidence is partial.

Load proofs:

| Proof | Raw lines | Success needs |
|---|---|---|
| `skill_body_delivery` | An assistant `tool_use` named `Skill`; the user `tool_result` with the same `tool_use_id`; an `isMeta` user line whose `sourceToolUseID` is that id and whose only text block starts `Base directory for this skill: ` | No `is_error`; `toolUseResult.success` is `true`; the base directory plus `/SKILL.md` is a frozen path inside a declared plugin directory; the requested name is that skill; the text after the base-directory line and one blank line matches the manifest `body_sha256` |
| `full_body_read` | An assistant `tool_use` named `Read` whose `file_path` is a frozen `SKILL.md` path; its `tool_result` | No `is_error`; `toolUseResult.file.filePath` is the same path; `startLine` is 1 and `numLines` equals `totalLines`; the `content` digest matches the manifest whole-file `sha256` |

`body_sha256` is the digest of `SKILL.md` with its frontmatter removed and its
leading newlines stripped. The load record names this transform. A failed
result is `failed`. A success without proof is `partial`: no linked body, a
digest mismatch, or a sliced read. No result, no success flag, a path outside
the declared plugin directories, or a requested name that differs from the
delivered directory is `unavailable`. `completed_seq` is the later of the result
line and the body line.

Paths match after `posixpath.normpath`, against the declared path as given and
its real path at capture time. Scoring does not read the file system.

An action's `seq` is the first line of the assistant API message (`message.id`)
that holds the labeled `tool_use`. Claude writes one line per content block and
can write a tool result between two blocks of one message. So a call written
after a skill body can still come from a message that started before it.

Only root-file lines score. Sidechain loads go to `child_loads` and never
satisfy root activation. In the audited version, sidechain `tool_result` lines
carry no `toolUseResult`, so every child load is `unavailable`.

Coverage: `start` needs the first line with a `uuid` to be a user line with a
null `parentUuid`. `end` needs exactly one stream `result` event for this
session with `subtype: success` and `is_error: false`. `relevant_actions` needs a
valid label. `skill_delivery` needs no issues. Each of these is an issue and
makes the session partial:

- a line type, `system` subtype, or attachment type that the audit did not see;
  the allowed sets are `CLAUDE_LINE_TYPES`, `CLAUDE_SYSTEM_SUBTYPES`, and
  `CLAUDE_ATTACHMENT_TYPES` in `skill_eval.py`;
- a malformed or unterminated line, or a line from another session;
- a missing or duplicate `uuid`, a second chain root, a parent outside the
  file, or a branch (resume and compaction signs);
- an `isSidechain` or `agentId` value that does not match its file;
- a duplicate `tool_use` id, or a `tool_result` without one earlier `tool_use`;
- a skill body that is not linked to one earlier `Skill` call, which is how a
  typed slash command delivers it;
- a subagent call whose sidechain file was not captured;
- a stream without one successful `result` event, or an invalid label.

Not supported: typed slash-command loads; `Skill` calls with arguments (only
the typed form was seen to append them, so a changed body is `partial`);
compaction and resume, which no probe exercised and which only the checks above
detect; repeat-load notes; Codex; and step-list extraction.

## Claude transcript audit (2026-10-13)

This audit checks the adapter's mechanics against raw lines. It is not
activation evidence: the probe prompts are not corpus cases, and case `IM-01`
only supplies a frozen catalog and a label slot. The command was
`/home/kylep/artifacts/agent-toolbox/swe-router-rewrite/2-native-adapter/audit/run_audit.sh`.
It materialized one `IM-01` run per probe trace, then ran `capture --format
claude-transcript --plugin-dir <probe>/plugin/swe --stream <probe stream>` and
`score`. The probe snapshot's `SKILL.md` files equal the frozen catalog
(`declared_snapshot` passed). Each row was checked by hand against the cited
raw lines.

| Trace | Adapter result | Raw lines checked by hand |
|---|---|---|
| `rename-plain` (no skill named; label: Edit `toolu_011mbBnD2FetcMUL2R9mDCwX`) | No loads; complete coverage; activation `miss`; action `seq` 32 | No `Skill` call and no `SKILL.md` read in 43 lines; line 32 is the Edit and the only line of its message |
| `rename-explicit` (label: Edit `toolu_01WfenAS2yK1rzWeJU25HU4P`) | `swe:implement` success, `skill_body_delivery`, completed at 21; action `seq` 35; timing `before` | Line 19 `Skill` call; line 20 result with `success: true`; line 21 `isMeta` body with `sourceToolUseID` of line 19; body digest `0ce0f8d5…` equals the manifest `body_sha256`; lines 35, 36, and 38 share `message.id` `msg_011CfyoWKm7xDvjgapGGiVhB`, and the Edit is on line 36 |
| `relread` (label: `none`) | `swe:implement` success at 21; `swe:testing-code` `partial`, detail `sliced read`; timing unavailable | Line 29 Read of the frozen `testing-code/SKILL.md` with `limit: 30`; line 30 result `startLine` 1, `numLines` 30, `totalLines` 128 |
| `subagent` (label: `none`) | No root loads; activation `miss`; one child load, `unavailable`, detail `tool_result lacks toolUseResult.success`; two sidechain files captured | Root line 19 Agent call, line 20 result with `agentId` `ac805767b100cd127`; sidechain lines 12 (`Skill`) and 17 (`Read`) share `message.id` `msg_011CfyodWD7K3xLkeuH3ypVH`, with the result on line 13 and the body on line 14; line 13 has no `toolUseResult` |

Other probe transcripts, parsed directly with the adapter's functions:

- `claude-skill-surface/transcripts/{bare,noargs,ns,snapshot,snapshot-ns}-swe`:
  each gives the issue "skill body not linked to one earlier Skill call" at
  line 4. These are typed `/swe` loads, so this is the expected coverage loss.
- `claude-skill-surface/transcripts/skill-leaf`: the blocked `Skill` call
  (lines 20 and 21, `is_error: true`) is `failed`.
- `claude-skill-surface/transcripts/pineapple`: the `Skill` load (lines 21 to
  23) of a scratch skill outside any declared directory is `unavailable`.
- `claude-skill-surface/transcripts/bare-swe`: the full Read of the scratch
  leaf `SKILL.md` (lines 22 and 23), checked against that file's digest, is
  `success`. No probe holds a full Read of a catalog skill, so the catalog
  case rests on this trace and the unit test.
- The other eight transcripts, including `claude-subagent-mcp/subagent-transcript.jsonl`
  as a sidechain file, give no issue.

The body transform (frontmatter removed, leading newlines stripped) matched all
four `Skill`-tool bodies in the probes. It did not match the five typed bodies,
because the typed form replaces or appends the arguments.

Deviation: item 6 of "Acceptance and migration" in
`docs/trace-framework-proposal.md` asks for a manual raw-event audit on small
Claude and Codex controls. This audit covers Claude only, because no Codex
adapter exists. The lead accepted a Claude-only audit as a recorded deviation
(resolved decision `adapter-codex-control` in the swe router rewrite plan). A
Codex score stays unpublished until a Codex adapter passes its own audit.

Seen red: the Claude transcript test failed under each of four single
mutations of `skill_eval.py`, and passed after a byte-for-byte restore. The
mutations were: action `seq` from the tool_use line; a body-less `Skill` result
counted as success; a sliced Read counted; and the whole-file digest used for a
delivered body. The output is in
`/home/kylep/artifacts/agent-toolbox/swe-router-rewrite/2-native-adapter/seen-red.out`.

## Pre-registered corpus deviation: TC-10

Case `TC-10` (testing-code explicit control) asked for `/swe:testing-code`.
testing-code is `user-invocable: false`, and Claude Code 2.1.296 rejects a typed
`user-invocable: false` plugin skill with zero model turns
(`/home/kylep/artifacts/agent-toolbox/swe-router-rewrite/probes/claude-skill-surface/typed-modelonly.jsonl`).
The case now reads "Use the swe:testing-code skill to …", the form that loaded
`swe:implement` through the `Skill` tool in the `rename-explicit` probe. Its
category, fixture, split, answer key, and action boundary are unchanged, so the
family keeps 4/2/3/1 cases. The change was made before any native run of the
corpus, so every comparison arm runs the same corpus.
