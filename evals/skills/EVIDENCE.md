# Activation evidence v1

This pilot uses a local interface, with no dependency on the general trace
framework. `skill_eval.py score` derives `evidence.json` from retained raw JSONL;
it does not accept an execution agent's self-report as a grade.

The normalized record has `schema_version`, `provider`, `adapter_version`,
`evidence_kind`, `session_id`, `session_state`, `evidence_coverage`, `coverage`,
`raw_trace`, `loads`, `child_loads`, `resource_reads`, `child_resource_reads`,
`unproved_reads`, `hook_deliveries`, `actions`, and `issues`. In the Claude
transcript adapter, load records add `agent_id`, `detail`, and `transform`.

`score` hashes `hook_arm` into `configuration_sha256` and writes `hook_arm` to
`score.json`. `aggregate` adds `hook_arm` to its group key and to every
`groups` and `confusion` row, so the two arms never pool.

`manifest.json` records `corpus_sha256` and `facets_sha256`, the digests of
`dataset/dev.jsonl` and `facets.json` at materialization. `score` refuses a run when
the answer-key corpus or the facet map changed since then. A manifest without
`facets_sha256` still scores. Both digests enter `configuration_sha256`, so runs
scored under different maps never pool in `aggregate`.

`raw_trace` contains a relative path and SHA-256 digest. Each evidence reference
contains a stable `event_id` and a one-based raw JSONL `line`; a Claude reference
also names its `file`, because one session spans several files. Array order is
source order; timestamps are not used to infer order. This intentionally small
interface is for one root session. Child-session reads go to `child_loads` and
`child_resource_reads`, and cannot satisfy root-session activation or timing.
In the synthetic envelope, a trailing child event does not invalidate the root
terminal; end coverage is checked against the last root event. The Claude adapter
takes end coverage from the stream `result` event instead (see "Claude
transcript adapter").

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

Resource read records (`resource_reads` and `child_resource_reads`) contain
`resource` (`<plugin>:<plugin-relative path>`), `path`, `status`, `detail`,
`body_sha256`, `completed_seq`, `session_id`, `agent_id`, `proof`
(`full_body_read`), `ordering`, and `evidence`. Resource reads never enter
`loads` or `child_loads` and do not affect activation metrics.

Unproved read records (`unproved_reads`) contain `path`, the matching `skill`
or `resource` ID, `session_id`, `agent_id`, `proof`
(`bash_command_mentions_path`), `status` (`unproved`), and `evidence`. They
never become loads or resource reads and never count as success.

Hook delivery records (`hook_deliveries`) contain `plugin`, `status` (`success`
or `mismatch`), `sha256`, `session_id`, and `evidence`. They prove whether the
frozen `hooks/session-start.md` bytes reached the model in the `hook-on` arm.

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
| `resource_read.request` | `request_id`, `resource`, exact frozen `path` |
| `resource_read.result` | matching `request_id`, integer `exit_code`, delivered `body`, Boolean `body_complete` |
| `hook.delivered` | `plugin`, `body` (in `hook-on`, `body` SHA-256 must match the frozen `session-start.md`; in `hook-off`, any `hook.delivered` is an issue) |
| `action.started` | `kind`, matching case boundary |
| `session.completed` | `coverage: {skill_delivery: true, relevant_actions: true}` |
| `message` | `role`, `text`; a root assistant message is recorded in `texts` (see "Assistant text and the final reply") |
| `skill.mention` | text ignored by scoring |

Sequence numbers are one-based lines. A successful read requires integer zero
exit status, matching skill or resource ID/path, `body_complete: true`, and an
exact digest of the delivered UTF-8 body against the materialized catalog. A
nonzero exit status is failed even if the output contains a body. Unknown
identity or missing status is unavailable. A successful but
incomplete/mismatched body is partial. A result before its request cannot count
as a load or resource read. Child sessions whose `session.started` sets
`parent_session_id` equal to the root `session_id` record their reads into
`child_loads` and `child_resource_reads`. Child-session events get the same
envelope checks as root events: an unknown child record type, duplicate child
request ID, or unmatched child read result adds an issue and makes the session
partial. Events of any other non-root session stay ignored.

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
`~/artifacts/agent-toolbox/swe-router-rewrite/probes/claude-trace-format/`
(`commands.sh`, `analyze.out`, `read-check.out`, and the copied transcripts).

Capture inputs:

- `--source`: the root transcript `<session>.jsonl`. Capture also copies every
  file in the sibling `<session>/subagents/` directory to `raw-subagents/` and
  records each digest.
- `--plugin-dir`: each absolute path given to `claude --plugin-dir`. Capture
  refuses a directory whose `skills/*/SKILL.md` files or frozen resources differ
  from the frozen catalog in name or bytes. In `hook-on`, capture also checks
  each declared plugin's frozen `hooks/session-start.md` bytes. A run that uses
  the materialized catalog passes `<run>/inputs/plugins/<plugin>` to both commands.
- `--stream`: the session's stream-json output. Only its `result` event shows
  that the session ended.
- `--relevant-action`: the root `tool_use` id where the case's relevant action
  starts, or `none` when no such action happened. A person sets this label from
  the raw trace and the case's `relevant_action` text. Without it, timing is
  unavailable and the evidence is partial.

Load and hook delivery proofs:

| Proof | Raw lines | Success needs |
|---|---|---|
| `skill_body_delivery` | An assistant `tool_use` named `Skill`; the user `tool_result` with the same `tool_use_id`; an `isMeta` user line whose `sourceToolUseID` is that id and whose only text block starts `Base directory for this skill: ` | No `is_error`; `toolUseResult.success` is `true`; the base directory plus `/SKILL.md` is a frozen path inside a declared plugin directory; the requested name is that skill (a bare name resolves to the one declared skill with that name); the text after the base-directory line and one blank line matches the manifest `body_sha256` |
| `full_body_read` | An assistant `tool_use` named `Read` whose `file_path` is a frozen `SKILL.md` or frozen resource path; its `tool_result` | No `is_error`; `toolUseResult.file.filePath` is the same path; `startLine` is 1 and `numLines` equals `totalLines`; the `content` digest matches the manifest whole-file `sha256` |
| `hook_success` (`hook-on` only) | A root `attachment` row with `attachment.type: "hook_success"` and `attachment.hookEvent: "SessionStart"` | `exitCode` is `0` (when present) and `stdout` bytes equal, byte for byte, the frozen `hooks/session-start.md` of a plugin declared with `--plugin-dir` |

Observed `hook_success` shape: Claude Code 2.1.323 (`entrypoint: "sdk-cli"`) and
interactive 2.1.326 write one `attachment` row per SessionStart hook. The first
hook row is the chain root (`parentUuid: null`), each next hook row chains on
`parentUuid`, and the first `user` row is a child of the last hook row. In those
rows, `content` holds `stdout` without its final newline, and `command` holds
`cat "$CLAUDE_PLUGIN_ROOT"/hooks/session-start.md`. Each row's `stdout` equals,
byte for byte, a `hooks/session-start.md` in the local plugin cache: swe, lab,
and uni in the 2.1.323 transcript, and swe and lab in the 2.1.326 transcript.
Hooks that return JSON context write `attachment.type: "hook_additional_context"`,
which no frozen plugin hook uses and both arms reject as an issue. This
`hook_success` shape was seen in local transcripts, not in an audited eval probe;
a native pilot must confirm it on an audited pilot trace.

`body_sha256` is the digest of `SKILL.md` with its frontmatter removed and its
leading newlines stripped. The load record names this transform.
It also accepts an appended `\n\nARGUMENTS: <args>` suffix (`_arguments_suffix_removed`) and, when the body holds `$ARGUMENTS`, replacement by `args` (`_arguments_substituted`, keeping `body_sha256` as the delivered digest).
A failed
result is `failed`. A success without proof is `partial`: no linked body, a
digest mismatch, or a sliced read. No result, no success flag, a path outside
the declared plugin directories, or a requested name that differs from the
delivered directory is `unavailable`. `completed_seq` is the later of the result
line and the body line. A root load that is not proved and whose name is not a
frozen skill keeps the name as given, so it cannot match an answer key. That
case is an issue, as listed below.

A `Bash` `tool_use` whose `command` contains a frozen `SKILL.md` or resource
path (as declared or as its real path) goes to `unproved_reads` with
`proof: "bash_command_mentions_path"` and `status: "unproved"`. The adapter
matches the path text only without parsing shell syntax.

Paths match after `posixpath.normpath`, against the declared path as given and
its real path at capture time. Scoring does not read the file system.

An action's `seq` is the first line of the assistant API message (`message.id`)
that holds the labeled `tool_use`. Claude writes one line per content block and
can write a tool result between two blocks of one message. So a call written
after a skill body can still come from a message that started before it.

Only root-file lines score. Sidechain loads go to `child_loads` and sidechain
resource reads go to `child_resource_reads`. Neither satisfies root activation
or root timing. In 2.1.296 sidechain results had no `toolUseResult`. In local
sidechain transcripts from Claude Code 2.1.316, 2.1.318, 2.1.321 to 2.1.323,
2.1.325, and 2.1.326, successful `Read` results carry `toolUseResult.file` with
`filePath`, `content`, `startLine`, `numLines`, and `totalLines`, so a child
full read can be proved there. No sidechain `Read` was seen for the other
versions in that range.

Coverage: `start` needs the first line with a `uuid` to be a user line with a
null `parentUuid`. In `hook-on`, `start` also accepts a leading run of
`SessionStart` `hook_success` attachment rows (the first with a null
`parentUuid`, each next row chained to the one before) followed by the first
`user` row. `end` needs exactly one stream `result` event for this
session with `subtype: success` and `is_error: false`. `relevant_actions` needs a
valid label. `skill_delivery` needs no issues. Each of these is an issue and
makes the session partial:

- a line type, `system` subtype, or attachment type that the audit did not see;
  the allowed sets are `CLAUDE_LINE_TYPES`, `CLAUDE_SYSTEM_SUBTYPES`, and
  `CLAUDE_ATTACHMENT_TYPES` in `skill_eval.py`;
- in `hook-off`, any `hook_success` or `hook_additional_context` attachment row
  (the isolation failed);
- in `hook-on`, any `hook_additional_context` row, any `hook_success` row whose
  `hookEvent` is not `SessionStart` or that appears in a sidechain, any
  `hook_success` row whose `stdout` bytes do not match a declared plugin's
  frozen `hooks/session-start.md` (a foreign or tampered hook), or any declared
  plugin with a frozen hook and no delivery row;
- a malformed or unterminated line, or a line from another session;
- a missing or duplicate `uuid`, a second chain root, a parent outside the
  file, or a branch (resume and compaction signs);
- an `isSidechain` or `agentId` value that does not match its file;
- a duplicate `tool_use` id, or a `tool_result` without one earlier `tool_use`;
- a skill body that is not linked to one earlier `Skill` call, which is how a
  typed slash command delivers it;
- a root `Skill` load whose body comes from outside the declared plugin
  directories or names another skill, or a root load that is `partial` or
  `unavailable` under a name that is not a frozen skill;
- a subagent call whose sidechain file was not captured;
- a stream without one successful `result` event, or an invalid label.

[README.md](README.md) lists what the adapter does not support. Two reasons
are not stated there. Only the typed form was seen to append arguments to the
body, so a `Skill` body that arguments changed is `partial`. No probe exercised
compaction or resume, so only the chain checks above detect them.

## Assistant text and the final reply

`evidence.json` carries two fields beyond the load and read lists.

- `texts`: the root assistant text in source order. Each record is
  `{"seq", "text", "session_id", "evidence"}`. Child-session text is not
  recorded.
- `final_reply`: the texts after the last root tool call, joined with a blank
  line, or `null` when none follow it.

A root tool call is a Claude `tool_use` line. In the synthetic envelope it is a
`skill_read.request`, a `resource_read.request`, or an `action.started` of the
root session. A synthetic text is a root `message` event with `role:
"assistant"`. A Claude text is each `{"type": "text"}` block of a root
(non-sidechain) `assistant` row, and its `seq` is the line. The real shape:

```json
{"type": "assistant", "message": {"id": "msg_01", "content": [
  {"type": "text", "text": "Playbook: `fix-bug`. Reason: a reported defect."}]}}
```

Real transcripts put backticks around the slug. The route scorer strips them.

## Claude transcript audit (2026-10-13)

This audit checks the adapter's mechanics against raw lines. It is not
activation evidence: the probe prompts are not corpus cases, and case `IM-01`
only supplies a frozen catalog and a label slot. The command was
`~/artifacts/agent-toolbox/swe-router-rewrite/2-native-adapter/audit/run_audit.sh`.
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

Other probe transcripts, parsed directly with the adapter's functions by
`~/artifacts/agent-toolbox/swe-router-rewrite/2-native-adapter/review/direct_parse.py`
(declared catalog: the scratch leaf skill only):

- `claude-skill-surface/transcripts/{bare,noargs,ns,snapshot}-swe` and
  `snapshot-swe-ns`: each gives the issue "skill body not linked to one earlier Skill call" at
  line 4. These are typed `/swe` loads, so this is the expected coverage loss.
- `claude-skill-surface/transcripts/skill-leaf`: the blocked `Skill` call
  (lines 20 and 21, `is_error: true`) is `failed`.
- `claude-skill-surface/transcripts/pineapple`: the `Skill` load (lines 21 to
  23) of a scratch skill outside any declared directory is `unavailable`, with
  the issue "skill identity unresolved" at line 21.
- `claude-skill-surface/transcripts/bare-swe` and `ns-swe`: the full Read of
  the scratch leaf `SKILL.md` (lines 22 and 23), checked against that file's
  digest, is `success`. No probe holds a full Read of a catalog skill, so the
  catalog case rests on these traces and the unit test.
- The other eight transcripts, including `claude-subagent-mcp/subagent-transcript.jsonl`
  as a sidechain file, give no issue.

The body transform (frontmatter removed, leading newlines stripped) matched all
four `Skill`-tool bodies in the probes. It did not match the five typed bodies,
because the typed form replaces or appends the arguments.

Deviation: item 6 of "Acceptance and migration" in the research note
`.agents/docs/research/2026-09-30-trace-framework-proposal.md` asks for a
manual raw-event audit on small Claude and Codex controls. This audit covers Claude only, because no Codex
adapter exists. The lead accepted a Claude-only audit as a recorded deviation
(resolved decision `adapter-codex-control` in the swe router rewrite plan). A
Codex score stays unpublished until a Codex adapter passes its own audit.

Seen red: the test module docstring names the regressions. The output is in
`~/artifacts/agent-toolbox/swe-router-rewrite/2-native-adapter/seen-red.out`.

## Pre-registered corpus deviation: TC-10

Case `TC-10` (testing-code explicit control) asked for `/swe:testing-code`.
testing-code is `user-invocable: false`, and Claude Code 2.1.296 rejects a typed
`user-invocable: false` plugin skill with zero model turns
(`~/artifacts/agent-toolbox/swe-router-rewrite/probes/claude-skill-surface/typed-modelonly.jsonl`).
The case now reads "Use the swe:testing-code skill to …", the form that loaded
`swe:implement` through the `Skill` tool in the `rename-explicit` probe. Its
category, fixture, split, answer key, and action boundary are unchanged, so the
family keeps 4/2/3/1 cases. The change was made before any native run of the
corpus, so every comparison arm runs the same corpus.
