# Agent trace extraction framework

**Proposal, 2026-09-30.** Reuse agent-sessions' raw archive and derive an auditable event view beside its current conversation/search views. Start with the skill-activation pilot; do not build a general platform or bulk-ingest private sessions. No provider trials or activation baseline were produced in this design task.

## Purpose and evidence

The source chat's final eval turns call for observing successful skill loads before measuring incidental activation, separating explicit controls, and checking load timing before relevant work. A declaration of intended skill use is insufficient. The existing routing seed is a proposal, not measured activation evidence. OpenAI's [skill-eval guidance](https://developers.openai.com/blog/eval-skills) supports explicit, implicit, contextual, and negative cases and deterministic checks over captured events.

Sam Liu's [supplied X article](https://x.com/samzliu/status/2103613396625367437) frames value creation as extraction, refinement, and distribution. Its practical obstacles include mixed data, volume, ambiguous feedback, long-horizon credit assignment, qualitative judgment, and unavailable reasoning. The recommendation here applies that framing narrowly: preserve evidence, derive bounded observations, then distribute reviewed findings and eval reports. The article's strategic claims do not establish provider trace formats or access to private reasoning.

## Reuse the existing investment

agent-sessions already has `raw/**/*.tar.zst` snapshots, normalized thread JSONL and SQLite/FTS, with rebuildable derived views. Its current extraction reads vendor logs in place; the proposed evidence path must explicitly read frozen inputs for reproducible replay. Its archive includes Claude JSONL, subagent metadata and workflow manifests, and Codex JSONL. Preserve that boundary and check historical snapshots for missing sidecars; archive intent does not guarantee every old snapshot is complete. See README (`agent-sessions/README.md:6`), input behavior (`agent-sessions/README.md:123`) and archive.py (`agent-sessions/src/agent_sessions/archive.py:38`).

The current conversation projection is useful for retrieval but cannot be the sole eval evidence source:

| Surface | Verified behavior | Consequence |
|---|---|---|
| Codex | Uses canonical response items; discards most event records and session instruction content (legacy top-level instructions retain only length), retains limited turn context; merges consecutive same-role parts and overwrites their timestamp. Extractor (`agent-sessions/src/agent_sessions/extract/codex.py:37`) | Lose harness details and constituent timing boundaries. |
| Codex tool output | Defaults `is_error` to false unless a dictionary has `success=false`. Native response IDs are not copied into normalized messages, though call IDs survive. Tool handling (`agent-sessions/src/agent_sessions/extract/codex.py:140`), thread output (`agent-sessions/src/agent_sessions/extract/codex.py:171`) | Non-error guesses cannot prove successful instruction delivery. |
| Claude | Indexes UUID/parent chains across files and resumes, then omits UUID/parentUuid from normalized messages. Abandoned leaves are optional; system/harness retention is selective. Chain index (`agent-sessions/src/agent_sessions/extract/claude.py:138`), branch selection (`agent-sessions/src/agent_sessions/extract/claude.py:234`), messages (`agent-sessions/src/agent_sessions/extract/claude.py:292`) | Good reconstruction work is already present, but proof pointers and branch coverage need preservation. |
| Shared normalization/index | Removes instruction/context tags and flattens rich content; SQLite keeps flattened messages and bounded tool previews. Normalizer (`agent-sessions/src/agent_sessions/utils/normalize.py:29`), index (`agent-sessions/src/agent_sessions/index.py:74`) | These are derived search representations, not complete instruction or tool-result records. |

Use existing lineage logic, but retain join strength. Parentage (`agent-sessions/src/agent_sessions/viz/parentage.py:12`) distinguishes exact sidecar/tool joins from prompt/time heuristics and session-container fallback. Corpus-specific heuristic validation is not a universal exact join.

## Three boundaries

1. **Restricted originals:** immutable captured bytes, sidecars, file inventory, source digest, capture interval, producer/surface/version and capture completeness. For live files, freeze a snapshot and record append/truncation state; a partial last JSONL record remains evidence of an incomplete tail. Unknown record types remain addressable. Never overwrite vendor logs or rewrite originals during redaction.
2. **Versioned event projection:** one record per native event or content block, preserving source pointers, native IDs, lineage, ordering and status. Parse facts belong here; do not merge adjacent messages for convenience. Large payloads may remain behind restricted references with digest/length/type instead of duplicated text. The old conversation view remains independently rebuildable.
3. **Derived observations:** skill loads, first actions, failures, feedback labels and scores cite event IDs and rule versions. Each has evidence state and rationale. An inference never replaces a native fact. Human/model judgments carry grader identity and rubric version, with a route to inspect sanitized evidence.

## Event contract and provider adapters

Use separate adapter identities for Claude transcript, Claude stream-json, Codex persisted rollout, and Codex exec JSONL. Version the common schema, adapter, interpretation rules and content transforms separately; record observed producer versions and tested fixtures. Unknown producer versions produce compatibility warnings or unsupported fields rather than silently using guessed semantics.

The future event view needs these fields; this is a design contract, not an implemented schema:

| Group | Minimum fields |
|---|---|
| Identity/provenance | Event ID stable within a frozen source snapshot; source logical ID and SHA-256; 1-based line, byte span and block index; native record type and IDs; adapter/schema versions. IDs may derive from source digest + byte offset + block index. Across snapshots, preserve aliases/native joins rather than pretending snapshot-derived IDs are globally stable. |
| Lineage | Provider, capture surface, session/thread, agent and parent agent, turn/root turn, branch/resume/compaction boundaries, spawn/call/result IDs; join method and confidence. Unknown values remain null. |
| Ordering/time | Source stream and line sequence, native ordinal when present, block subindex, timestamp value/unit/clock kind, request/start/completion boundaries. Preserve conflicting clocks. |
| Content/status | Event kind, role/channel, native status/error, payload or restricted payload reference, body digest/length/completeness, redaction state. Keep explicit failure, success, unknown, cancelled and partial distinct. |
| Run context | Model/settings, tools/catalog/plugin versions and content digests, repository/fixture identity, permissions, captured harness/instruction refs, capture exit/state, telemetry availability. Missing context is recorded, not reconstructed from current installs. |

An inspected Codex persisted sample reports `cli_version=0.159.0`, `source=vscode`, `thread_source=agent_created_thread`; its first 15 records include top-level ordinal, native message IDs, turn/root-turn IDs, base-instruction/context fields, and `item_completed` start/completion milliseconds. These are local observations, not a CLI-format guarantee. Restricted sample: a local Codex rollout, not published. Only keys and non-sensitive IDs/version fields were examined for this observation.

Official [Codex non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode) describes `codex exec --json` with thread/turn/item events. Official [Claude programmatic documentation](https://code.claude.com/docs/en/headless) describes stream-json and subagent parent-tool IDs, with version-dependent forwarding. These capture surfaces need independent adapters. A documented event list alone does not prove complete skill-body visibility.

Order is a **partial order**: same-stream request/delivery/action-start records can establish precedence; explicit call and spawn edges can connect streams. File emission order of completion records is insufficient to order earlier action starts. Wall-clock proximity and heuristic parentage cannot prove cross-agent activation timing. Deduplicate mirrored records only by explicit native identity plus compatible payload; preserve conflicts and source aliases.

## Initial skill-activation slice

The eval peer owns [the pilot interface](../evals/skills/EVIDENCE.md), whose finalized written contract was checked for agreement with this proposal. Its compact `evidence.json` uses one session, raw path/digest, adapter version, evidence kind, session state, overall coverage plus start/end/skill-delivery/action coverage, load records, action records, issues and raw event/line references. Loads retain skill path, body hash, proof type, delivery-completion sequence and ordering state. Actions identify their start sequence. Child-session events remain in raw capture but cannot satisfy root-session activation. End coverage is checked against the last root event; trailing child data does not invalidate a completed root session. Peer implementation verification remains separate from this document review.

Count a load only when evidence proves either:

- A successful provider Skill invocation and the rendered instruction-body delivery, tied to the expected skill identity; or
- A successful read of the exact frozen `SKILL.md` path, with the complete body returned to the agent and matching the materialized catalog digest.

Mentions, catalog listings, announcements, attempted reads and partial output do not count. Missing Claude `is_error` alone proves neither failure nor success. Static file hashes require exact bytes or a documented lossless framing transform. Dynamic rendering/substitution requires original-file identity plus a separately recorded rendered-body digest and transform; an unexplained hash mismatch is unavailable evidence, not a permissive match. Claude [skill lifecycle documentation](https://code.claude.com/docs/en/skills) distinguishes description availability from full content loading and describes repeat invocation and compaction behavior. A repeat-load note needs a proven earlier delivery; it is not a new full-body proof.

Compare delivery completion against the case-defined **first relevant action start**. Preserve before/after/unknown; a correct but late load fails the timing requirement. The case author defines what counts as an implementation, diagnostic or testing action before execution. A child load stays child-scoped unless delivery to another agent is independently shown. A skill loaded before the tested conversation may be a preload observation, not evidence of incidental discovery in the tested turn.

Scorable absence requires full observable coverage for the tested skill-delivery channel and action interval. Incomplete captures, truncation, unknown adapter semantics or missing bodies are unscorable. Keep timeout/capture failure and observation coverage visible beside recall/false-activation/timing denominators. Do not turn missing telemetry into zero or hide excluded runs. Keep explicit controls and synthetic fixtures separate from implicit activation measurements.

The documented first adapter is `synthetic-contract-v1`, for sanitized request/result fixtures. Its evidence validates plumbing; it does not demonstrate either provider's natural activation. Native traces yield `native_adapter_unverified` under the pilot contract. Next, approve small real captures from each provider/surface, including a known successful load and denied/partial read, before enabling a native adapter or collecting the broader corpus.

## Privacy and interpretation limits

Keep originals in their existing restricted archive; do not copy personal prompts into tracked fixtures. Derive a separately redacted view with a transformation manifest, source/derived digests, removed-field categories, stable pseudonyms and visibility state. Secret or private payload removal can make a check unscorable. Access to the re-identification map and originals remains local/restricted; share only reviewed derivatives. Digest equality is not anonymization. Redaction must include tool inputs/results, paths, account identifiers, attachments and instruction bodies, not only user messages.

Recorded actions can support observable process claims. They cannot establish internal comprehension, hidden reasoning, causal usefulness of a skill, real-world success without outcome evidence, or user satisfaction from silence/abandonment. Exposed summaries are summaries; encrypted/absent reasoning stays opaque. Preserve tool errors separately from final outcome. Utility requires independent outcome checks and a controlled comparison, as the source chat proposed. Reviewed playbooks or candidate instructions belong downstream, with explicit human decisions before changing skills.

## Acceptance and migration

Start with the eval-local contract and fixtures. Once native proof works, add an optional evidence projection to agent-sessions reading restricted raw sources; retain current threads/index unchanged. Add SQLite evidence tables only if actual queries require them. Re-extract bounded approved raw snapshots, comparing versions and coverage; never try to recover dropped facts from normalized text alone. A rewrite is unnecessary unless the additive route demonstrably cannot meet these checks:

1. Every observation resolves to raw bytes under the recorded digest; reruns with fixed adapter/rule versions produce the same event IDs and score inputs.
2. Unknown records, malformed/interrupted tails and absent sidecars remain represented with coverage loss; no silent omission or success defaults.
3. Approved fixtures cover full/failed/partial/wrong-path reads, mentions, late/unknown timing, duplicate native records, resumes/branches, compaction, child scope and version mismatch.
4. Exact and heuristic lineage remain distinguishable. Parallel tool completion cannot masquerade as action-start order.
5. Evidence can be redacted without modifying originals; removal that destroys proof changes observability explicitly.
6. A manual raw-event audit agrees with native adapter findings on small Claude and Codex controls. No activation score is published until this gate passes.

## Source records and limits

Retrieved 2026-09-30. Source-code claims refer to agent-sessions checkout `e13b04ab6069a984d9908acf59426f7bff7c6d04`; agent-toolbox started at `9a78dead687f8606e0edbfe0030cbed27f7909ca`. Targeted code review and the first 15 records of one Codex source-chat rollout were inspected. No Claude transcript was inspected in this task; Claude code behavior was verified, while live load visibility remains unverified.

- **Source chat** (first-party record, verified): final eval turns checked through thread API, including completed turn `01a0f59f-3cb3-7b10-a637-fd0d7b0702e5`; supports scope and lack of measured baseline at that point.
- **Sam Liu X post** (first-party essay, partial metadata): supplied URL successfully extracted via Defuddle in Nu-MCP after direct web/local fetch failure. Body and relevant framing verified; no title or publication date returned. Unrelated claims in the essay were not audited or used.
- **agent-sessions files** (source code, verified): archive, extractor, normalization, parentage and index locations cited above support the reuse and fidelity findings. Historical archive completeness and corpus-wide heuristic accuracy were not remeasured.
- **Codex persisted sample** (first-party local record, verified bounded structural observation): source/version and native field inventory only; it does not prove every Codex surface exposes these fields or full skill bodies.
- **OpenAI skill eval and non-interactive docs; Claude headless and skills docs** (official docs, verified for cited behavior): opened and relevant sections checked. Documentation may describe newer producers than the inspected local rollout; adapter support must follow tested producer versions.

The open gate is native capture proof, followed by measured activation. This document proposes the extraction boundary and acceptance checks; it authorizes no archive migration, installation, live runs or skill changes.
