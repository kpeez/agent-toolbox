# Lab and SWE skill audit — Astra guidance

Status: approved proposal implemented, including the autoresearch iteration-unit
refinement below. Installed caches remain unchanged.

Reviewed on 2026-09-12 against working tree based on
`c9e6739eaef43523079c06ae26ad9d28427588b8`, on
`codex/astra-skills-agents-review`. Coverage: all 18 current skill entrypoints,
four Lab and fourteen SWE. Supporting resources were inspected where they affect
routing or repeat the root instructions. No installed caches were changed.

The existing uncommitted move from `data-viz/` to `visualizing-data/` is user-owned.
This review uses the latter path; implementation completes its frontmatter name
as `visualizing-data` without reverting the move.
This proposal lives directly under `docs/` so it can travel with the requested
review branch; the repository's usual `docs/agents/` is a link into llmOS.

## Recommendation

Keep the portable Lab/SWE split and the existing skill names, subject to resolving
the in-progress visualization rename. Change routing and unnecessary procedure
before considering deletions or mergers. Preserve useful constraints for all
configured models, not only Astra.

The article recommends concise, discriminating descriptions; conditional
reference loading; outcomes rather than rigid recipes; task-specific document
reading; proportionate verification; and explicit safe continuation/completion
boundaries. It also warns that repository instructions serve other models.
These are design criteria, not evidence that a particular local rewrite improves
performance. [OpenAI, Eric Provencher, 2026-09-11; retrieved 2026-09-12](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)

The findings and changes below describe the pre-implementation audit, not claims
that the article reviewed these plugins. Root files totaled 1,798 lines at audit;
that is an inventory, not the amount loaded on every task or a token-savings estimate.

## Priority and boundaries

1. Fix scope and stopping rules: diagnosis must not imply permission to fix;
   conflict resolution must not stage unrelated work; drafting must not silently
   become execution; a failing check should prevent a false completion claim,
   not forbid authorized investigation and repair.
2. Reduce overlapping triggers and mandatory loads around implementation,
   testing, design, and research.
3. Move substantial conditional procedures out of long roots. Keep short,
   single-purpose skills self-contained. Do not create routers for their own sake.
4. Validate realistic selection and completion behavior before claiming improvement.

Preserve explicit spec approval, external publication authority, private-source
boundaries, dirty-work preservation, experiment identities and evaluator integrity,
and the distinction between evidence, inference, and uncertainty. Do not replace
configured model roles, add automatic publication, or mandate Astra everywhere.

## Lab: each skill

### autoresearch — retain invariants; split operating modes

Evidence: [entrypoint](../plugins/lab/skills/autoresearch/SKILL.md), especially
Setup, Resume an approved run, and Evaluate and record attempts. Its 173-line root
mixes first-run setup, recovery, and the repeated experiment loop. The description
also catches ordinary empirical comparisons that need only a bounded probe.

Proposed description: “Run a bounded autonomous experiment loop against an approved
metric and evaluator. Use for autoresearch or repeated optimization runs.”

Keep the loop and stop conditions in the root. Route setup/program approval and
interrupted-run reconciliation to separate references. Keep the committed-state
identity, read-only evaluator, append-only ledger, clean-state reset checks, and
budget continuity mandatory. Reuse an already-approved program instead of repeating
the interview. Do not loosen destructive reset checks or import the historical
Karpathy prompt as active instructions.

Before optimizing, define the iteration unit: how much work each candidate gets
before its result can support a keep/discard decision. Seek the best useful signal
per unit of elapsed time or compute, not simply the shortest run. A full training
run may be too expensive; one epoch may be too noisy or too early to distinguish
changes. The unit may instead be a step/token budget, several epochs, a data subset,
or another workload-specific evaluation horizon.

Use existing evidence or a simple bounded pilot when it can establish that unit.
If the choice remains unclear, the first experiment is calibration: compare a
small set of plausible units for cost, variability, and whether their conclusions
track the intended objective. Choose a practical unit supported by that evidence,
not a claimed global optimum. Define the calibration budget and selection criteria
in the approved program; do not tune the evaluator to favor a candidate. Record
calibration separately from candidate improvements, then establish a comparable
baseline and hold the chosen unit fixed during the optimization loop. Recalibration
requires comparable evidence and must not mix incompatible measurements.

### deep-research — retain evidence contract; reduce repeated procedure

Evidence: [entrypoint](../plugins/lab/skills/deep-research/SKILL.md) and its
[packet guide](../plugins/lab/skills/deep-research/references/evidence-packet.md).
The 177-line root loads both supporting guides up front and repeats packet fields,
source checks, privacy rules, and completion records across seven stages.

Proposed description: “Produce repository-retained research briefs, lane evidence,
and an audited Markdown report. Use for multi-lane project research requiring those artifacts.”

Keep question/scope, lane ownership, privacy, evidence reconciliation, and the stop
condition in the root. Route packet format and citation-audit mechanics when those
artifacts are produced. Consolidate repeated requirements into their existing
owner rather than create another evidence layer. Preserve retained lane evidence,
deduplication, contradictions, incomplete-source records, and coordinator judgment.
Do not turn a generic request for a proposal into an automatic deep-research run.
Distinguish this retained project workflow from the installed Work Deep Research
skill for general comprehensive artifacts or explicit Work-mode selection. A bare
“deep research” request should not load both workflows solely because their names match.

### research — narrow activation to a research deliverable

Evidence: [entrypoint](../plugins/lab/skills/research/SKILL.md), description and
Run one read-only researcher / Write the single memo. A simple current-fact lookup
can trigger delegation, a source-record process, and a mandatory private file.

Proposed description: “Produce one retained, cited memo for a bounded research
question or explicit source audit.”

Keep this as the memo workflow rather than a universal web-search wrapper. Allow
the host to handle a small question directly; delegate when useful. Keep source
quality, private-context boundaries, adjacent support, and uncertainty. Use the
existing source protocol for record details without restating it in the root.
Ordinary quick factual answers should not need this skill or a saved memo.

### data-viz / visualizing-data — compact root and route by plotting concern

Evidence: [current entrypoint](../plugins/lab/skills/visualizing-data/SKILL.md),
especially Default Workflow and the repeated reference lists. It already has
useful reference files, but repeats chart choices, perception, labeling, and review
guidance in a seven-step root. The description lists many task and library variants.

Proposed description: “Design or review statistical plots and plotting code for
honest scales and accessibility. Not for conversational diagrams, simulations, or UI mockups.”

Keep the analytical question, meaningful scales/baselines, uncertainty, and
non-color cues. Route chart selection, perceptual rationale, accessibility, and
final review to the existing references with explicit applicability. A small label
edit need not repeat chart-family selection. Inspect the rendered result when the
task changes visual output. Resolve folder/frontmatter naming only as part of the
user’s existing rename; do not independently rename or add an alias now.

## SWE: each skill

### codebase-design — small, useful; narrow the trigger

Evidence: [entrypoint](../plugins/swe/skills/codebase-design/SKILL.md), description
and Design for testability. Merely choosing a test surface can activate a broader
module-design discussion. Dependency injection and pure returns are stated as
unqualified directions rather than design choices.

Proposed description: “Evaluate module boundaries and interfaces using depth,
information hiding, and caller complexity. Use for substantive interface design.”

Keep the compact vocabulary, deletion test, and adapter-count caveat. Present
testability advice as trade-offs, not universal architecture requirements. Do not
split this 53-line skill into more files or require it for routine test changes.

### diagnose — rewrite around evidence and requested outcome

Evidence: [entrypoint](../plugins/swe/skills/diagnose/SKILL.md), lines 8, 24–51,
and 86–112. It mandates phases, ranks nine reproduction methods, bars hypotheses
without a runnable loop, and proceeds to a fix even for diagnosis-only requests.

Proposed description: “Investigate bugs and performance regressions using focused
evidence. Use when asked to diagnose, debug, or explain a failure.”

Keep symptom fidelity, falsifiable hypotheses, measured performance, and honest
verification limits. Allow logs, traces, static reasoning, and partial evidence
when reproduction is unavailable. Move specialized harness suggestions into an
optional reference. Distinguish diagnosis-only completion (cause/evidence/uncertainty)
from authorized repair (fix, cleanup, verification). A hard-to-reproduce issue is
not automatically a reason to stop all useful investigation.

### execute-spec — keep; clarify continuation

Evidence: [entrypoint](../plugins/swe/skills/execute-spec/SKILL.md). Its 50-line
root already separates approved intent from task state and rejects a fixed pipeline.

Proposed description: “Execute or resume an approved spec across tracked tasks.
Not for drafting, status checks, or isolated edits.”

Retain ownership/dependency reconciliation, existing approval reuse, assembled
acceptance evidence, and publication boundaries. Make continued authorized work
through verification explicit. Keep downstream skills conditional on the task;
do not force delegation or a fresh approval gate for every task.

### external-subagents — keep narrow authority; simplify metadata

Evidence: [entrypoint](../plugins/swe/skills/external-subagents/SKILL.md).
The body is short and already routes ACP details. Its description includes runtime
transport choices that do not help determine whether external delegation was requested.

Proposed description: “Delegate bounded work to an explicitly requested external
provider such as OpenCode or GitHub Copilot.”

Keep transport selection in the body, provider-specific disclosure authority,
permission enforcement, and separate host/bridge identities. Do not generalize a
provider's auto-approval behavior into permission to broaden access. Provider CLI
claims require their own live documentation/configuration check if changed;
this audit does not validate or change those claims.

### implement — keep one lightweight implementation contract

Evidence: [entrypoint](../plugins/swe/skills/implement/SKILL.md), lines 12–22
and 36–47. It duplicates testing-code's admission criteria and directs every
implementation through that skill. “A failure ... stops the task” can halt repair
of the very failure that the task authorizes.

Proposed description: “Implement an authorized feature or fix through relevant
verification. Use for scoped code changes.”

Keep scope, minimal justified implementation, proportionate evidence, and useful
handoff state. Route to testing-code only for test design, uncertain behavior, or
an explicit probe; avoid repeating its full contract. Required failures block
completion/publication, while in-scope diagnosis and correction continue. Report
unrelated baseline failures without silently fixing unrelated code.

### improve-codebase-architecture — separate review from design follow-through

Evidence: [entrypoint](../plugins/swe/skills/improve-codebase-architecture/SKILL.md),
Vocabulary and Process. It requires another skill and context documents first, then
forbids interfaces and requires a user choice even when a specific candidate was
already supplied.

Proposed description: “Review existing module boundaries and propose refactors
that reduce coupling or caller complexity.”

Keep concrete friction, code evidence, before/after reasoning, and ranked value.
Read relevant rationale where it can affect the recommendation. Route to existing
deepening/interface references only when designing a chosen change. Ask for a
selection only when genuinely unresolved; a request for review remains a review,
not authorization to implement. Do not replace project vocabulary unnecessarily.

### merge-conflicts — targeted correction, not a new framework

Evidence: [entrypoint](../plugins/swe/skills/merge-conflicts/SKILL.md), especially
lines 24–25: unconditional staging and committing.

Proposed description: “Resolve conflicts in an active Git merge, rebase, or
cherry-pick while preserving intended behavior.”

Keep operation inspection and semantic resolution. Stage only reviewed resolution
paths, preserving unrelated staged and unstaged work. Continue/commit when the
requested operation authorizes that finish; otherwise leave the resolution ready
for the caller. Use applicable checks rather than inventing a full test stack.
The existing short root needs no supporting procedure files.

### orchestrate — retain structure; trim description

Evidence: [entrypoint](../plugins/swe/skills/orchestrate/SKILL.md). The 39-line root
already states ownership, bounded briefs, disjoint writes, review, and stop criteria
without a fixed pipeline.

Proposed description: “Coordinate bounded agents for substantial parallel work
or independent review.”

Keep the current body substantially intact. Preserve configured roles and
lead-owned decisions. Independent review is useful for substantive changes;
avoid forcing it for trivial edits or making a worker report stand in for verification.

### qmd — retain retrieval contract; extract the CLI manual

Evidence: [entrypoint](../plugins/swe/skills/qmd/SKILL.md). Its 200-line root mixes
targeted lookup, structured hybrid queries, vector search, browsing, diagnostics,
and index maintenance. “The workflow is always” adds a search even if the document
identity is already known; `Bash` unnecessarily fixes the host tool.

Proposed description: “Find and retrieve documents from local Markdown collections
indexed by qmd.”

Keep lexical/semantic selection, retrieval before factual claims, source location,
and read-versus-maintenance authority. Permit direct retrieval of known documents.
Move advanced query syntax and maintenance to conditional references; use the
available shell tool. Do not turn an ordinary repository code search into a vault search.

### sharpen — retain; make examples and recording conditional

Evidence: [entrypoint](../plugins/swe/skills/sharpen/SKILL.md), During the session.
The entrypoint already reuses settled answers but includes extended conversational
examples and immediate glossary edits for every pinned term.

Proposed description: “Stress-test a plan or design to resolve material ambiguity
in scope, terminology, and acceptance criteria.”

Keep focused questions, code-backed answers, relevant ADR freshness, and the
high-value ADR threshold. Wait for answers before dependent decisions; a small
batch of independent questions need not be forbidden. Record terminology only
when reusable and documentation edits are within the request or established
workflow; a conversation-only critique should not silently edit project docs.
Examples need not load every time. Do not repeat an interview for already-approved intent.

### ship-pr — keep publication invariants; route secondary modes

Evidence: [entrypoint](../plugins/swe/skills/ship-pr/SKILL.md), Workflow, Finalize,
and Stacked pull requests. The 122-line root repeats verification and lifecycle
rules across modes.

Proposed description: “Commit, push, and open a draft PR for authorized work.
Use when asked to ship; finalize only on explicit request.”

Keep the default draft workflow, intentional staging, verified base, privacy,
force-push limits, and review-versus-delivery distinction. Route finalize and
stack-specific details when requested. Avoid asking again for authority already
established by an invocation; never broaden it to merging or deployment.

### testing-code — specialize and remove duplicate admission procedure

Evidence: [entrypoint](../plugins/swe/skills/testing-code/SKILL.md) and
[tests reference](../plugins/swe/skills/testing-code/references/tests.md).
The description overlaps all implementation. Admission criteria and a technique
ladder appear in both files; Plan before probing adds design/ADR preflight.

Proposed description: “Design behavioral tests or disposable probes for uncertain
code. Use for testing strategy, regression coverage, TDD, or spikes.”

Keep independent oracles, meaningful public boundaries, nonduplicated coverage,
and proportionate cost. Choose a suitable technique rather than the first item
in a rigid hierarchy. Keep the admission explanation in one place; load property,
mutation, and ML-specific substitution details only when relevant. Scratch work
should use a safe available location, not require a repository ignore-file edit.
No test quotas, automatic refactors, or permanent tests for every change.

### to-issues — keep task ownership; expose tracker routes

Evidence: [entrypoint](../plugins/swe/skills/to-issues/SKILL.md), Select the tracker,
Process, and the inline issue template. It says to read the matching reference but
does not link the three existing provider files. The generic template and triage
labels need not precede every tracker operation.

Proposed description: “Turn an approved plan into independently verifiable tasks
and dependencies on the selected tracker.”

Keep established tracker linkage, authority, native dependencies, reuse, and
minimal slices. Add explicit conditional links to local, GitHub, and Linear
references; put optional template/label detail with the applicable route. Read
current context and ADRs only where they bear on task boundaries. Do not silently
fallback from an inaccessible configured tracker or publish without authority.

### write-spec — end at the requested planning artifact

Evidence: [entrypoint](../plugins/swe/skills/write-spec/SKILL.md), lines 42–61.
Crossing files or entering unfamiliar code is enough to recommend a spec, and the
workflow continues into task creation and execution.

Proposed description: “Draft or revise a durable feature spec with scope, design
decisions, and observable acceptance criteria.”

Keep complete-proposal approval, authority records, spec/tracker ownership,
non-overwriting numbering, and the existing template. Drafting finishes with the
requested spec and any unresolved decisions; route task creation/execution only
when requested. Multi-file work alone does not require a spec. Move resume/execution
coordination to execute-spec, retaining only editing-relevant spec context here.

## Approval and verification plan

Approve the descriptions and scope/stopping corrections first, then the conditional
reference moves. Keep names and invocation-policy fields unchanged unless separately
approved. Do not refresh installed plugins or publish as part of a proposal review.

After approved edits, check frontmatter and same-plugin references, then use a small
independent selection/forward-test sample across configured roles:

| Request | Expected behavior |
| --- | --- |
| One-line implementation fix | No spec, architecture audit, or elaborate testing plan by default. |
| Explain a failure; do not fix | Diagnose and report evidence without editing implementation. |
| Fix a reproduced bug | Continue through relevant verification; stop only for a real blocker. |
| Resolve a conflict with unrelated staged work | Preserve unrelated index/worktree state; finish only the authorized operation. |
| Draft a spec only | Return the spec; do not create remote tasks or implement it. |
| Resume approved tracked work | Reconcile live state and continue without repeating settled approval. |
| Find a known qmd document | Retrieve directly; no index mutation or unnecessary query modes. |
| Answer a quick current-fact question | No mandatory Lab memo/delegation workflow. |
| Produce a bounded research memo | Supported citations and uncertainty; no extra report bundle. |
| Reconcile conflicting research sources | Retain independent evidence and contradictions; no false corroboration. |
| Make a chart-label adjustment | Review affected output without repeating the whole design itinerary. |
| Resume an interrupted experiment | Preserve identities/budget; no reset from guessed state or modified evaluator. |
| Start optimization with an unclear evaluation horizon | First calibrate the iteration unit within budget, then baseline and optimize at the selected unit. |

Compare selection, unnecessary loads, correct completion, and authority preservation
against the current baseline. Static validation does not prove these behaviors.
No paired behavioral or cost/latency benchmark has been run for the proposed rewrites.

## Implementation and verification — 2026-09-12

Implemented all 18 entrypoints on `codex/astra-skills-agents-review`. Descriptions
now distinguish task intent; conditional setup, recovery, search, publishing,
diagnostic, and testing details live behind relevant references. Scope boundaries
preserve diagnosis-only and draft-only requests, publication authority, and
unrelated staged work. The visualization metadata follows the existing
`visualizing-data/` move.

Autoresearch now selects a useful iteration unit from prior evidence or a bounded
pilot. When that is insufficient, the first experiment calibrates the unit under
approved cost and signal criteria. Calibration has a separate ledger; the
candidate ledger starts with the comparable baseline at the selected unit.
Resume checks require the retained calibration decision, baseline log, and
recorded candidate units to agree. Missing or inconsistent evidence stops the
run. The existing ledger runtime is unchanged.

Fresh checks:

- All 18 names, descriptions, invocation policies, and same-plugin Markdown
  links pass structural checks. The bundled validator passes 16 skills; it
  rejects the pre-existing `user-invocable: false` field in `merge-conflicts`
  and `qmd`. Those policies were preserved and independently checked.
- Both provider manifests and marketplace catalogs parse as JSON, resolve local
  plugin paths, and retain matching provider versions. `git diff --check` passes.
- A synthetic ledger smoke check confirms separate calibration records do not
  replace the candidate baseline or latest keep.
- Independent forward checks in disposable fixtures reproduced a failure
  without fixing it; drafted a spec without implementation or tracker work;
  resolved a merge without committing or changing an unrelated staged blob;
  and drafted a calibration-first program without launching training.
  The primary session inspected artifacts, source hashes, and merge index/HEAD.

These checks do not establish model-selection accuracy, training performance,
cost or latency improvements, or all configured-model behavior. Runtime scripts,
model roles, installed caches, and versions are unchanged. No commit, push, or
installation was performed during implementation verification. The earlier
cross-repository AGENTS audit remains local and is not part of this publication;
only this repository's instruction change is included.
