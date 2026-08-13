---
name: start-loop
description: Run an approved spec to a shipped PR — the lead dispatches one implementer subagent per unblocked task, runs the verification gates and merges itself, then dispatches a single reviewer before shipping. Use only when the user explicitly invokes /start-loop.
---

# /start-loop — run an approved spec

You (the lead) orchestrate the run directly. There is no Workflow tool, no
conductor, no planner or plumbing agents — you dispatch implementers and a
reviewer, run gates and merges yourself, and ship.

On a host with no forwarder subagents (Codex), follow `/implement`'s
"Manual fallback (no forwarder subagents)" section instead: call the three
plugin-delivered OpenCode delegate tools directly per task.

## Handoff discipline

Sharpening and spec-writing happen in a prior session. Start the run in a
**fresh session** (a new session, or `/clear`) — never compact into a run.
The spec is the distilled handoff; if the run needs something the spec
lacks, fix the spec, don't carry stray context forward.

The spec's frontmatter must carry `approved: true`. A spec without it is a
stop — say so and point at `/write-spec` or `/sharpen` instead of proceeding.

## Run procedure

1. **Read the spec.** Parse its `## Tasks` section: lines of the form
   `- [ ] Tn: title — brief`, optionally suffixed `(after: Tm[, Tk])`. A
   malformed task line is a stop. Create the integration branch (the spec's
   slug) from the default branch.
2. **Dispatch implementers.** One implementer subagent per unblocked task —
   parallel when tasks are independent, in `after:` order otherwise — each in
   its own isolated worktree. The prompt carries the spec text verbatim
   (worktrees can't see `docs/agents`) and the contract: create branch
   `change/Tn-<slug>`, implement, test, commit, and report
   `{status, branch, summary}`. Give every worker a hard turn/effort cap; one
   that stalls or exceeds it is a failed dispatch to redispatch or escalate,
   never something to wait on. Prompt contract and cost discipline:
   [references/delegation.md](references/delegation.md).
3. **Gate and merge, yourself.** On each completion report, run the
   verification gates (lint, types, tests) on the task branch with shell
   commands — zero model invocations — then `git merge --no-ff` it into the
   integration branch. This step is serial. Gates red → redispatch that task
   once with the failure output appended. Red again → escalate to the user
   and continue the rest of the frontier.
4. **Review once.** When the frontier is drained, dispatch **one** reviewer
   subagent — a different model family from the implementers — with the
   assembled diff and the spec text, redacting PR metadata and any claims
   about the code's quality. Findings get one fixer round, then a re-review.
   At most two fix rounds total. Rationale for these constants:
   [references/review-loop.md](references/review-loop.md).
5. **Ship.** Write the PR body yourself from the reports you've held and run
   `gh pr create` (draft). One PR; only stack when the task graph is a
   declared chain and the spec asks for it.
6. **Tracker, minimally.** If the spec's frontmatter names a tracker
   container: exactly one `tracker.py sync` plus one summary comment, at run
   end. Nothing else touches the tracker.
7. **Final report.** Tasks landed, escalations, PR URL, and agent accounting
   — which agents ran. The accounting must show zero plumbing invocations.

## The lead never reads code

Reports, gate output, and merge results are your whole context diet. Never
open an implementer's diff yourself — anything that needs human-grade diff
reading belongs to the reviewer in step 4.

## Model policy

| Role | Default | Escalation / notes |
| --- | --- | --- |
| Explorer | Haiku (repo), OpenCode (deepseek-v4-flash) (web) | Reports only |
| Sharpen + spec | The premium model | The one place it earns its price |
| Implementer / fixer | OpenCode (gpt-5.6-luna) when the Go subscription is flat-rate; else Sonnet, high effort | Fails gates twice → redispatch that task on Opus with the failure history. Never pre-buy Opus for tasks the spec already made bounded: ~5× the price dwarfs any thinking-token savings. |
| Reviewer | A different family from the implementer: deepseek-v4-pro, or Sonnet/Opus | One invocation, on the assembled diff |
| Orchestrator (you) | The fresh session's model; Opus suffices | Reads reports and runs git |

## Resume

If the run session dies, a fresh session re-derives state from
`git branch --list 'change/*'` plus the spec's task list: merged branches are
done, everything else redispatches.

Warn the user when a spec exceeds ~10-12 tasks — that's the context-growth
trigger for the deferred supervisor (see ADR-0014).

## Escalation, not gates

Once the spec is approved, the run proceeds to completion without prompting.
Problems reach you as data, from implementer and reviewer reports — never a
live worker interruption.

1. Read each report's findings when it lands; check them against the spec's
   Scope before trusting the task is covered.
2. **Resolve** anything answerable from the spec, ADRs, or the codebase; log
   the decision as an issue comment (when a tracker is in play) and
   redispatch. A logged judgment call beats a stalled run.
3. **Interrupt the user only for**: a scope change, a spec contradiction, a
   blocking `ready-for-human` task, or a destructive/irreversible action.

## Fail loud

If a required skill (`/sharpen`, `/write-spec`) can't be activated, or the
tracker can't be reached, name it and stop before changing state — do not
improvise a substitute.
