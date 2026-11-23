---
name: verify-pr-lifecycle
description: Model-check the swe pull-request lifecycle with TLA+ (TLC) - publication authority, the patch-id verdict, ready and merge, the stack frontier, and the tracker issue status - for one PR and for a stack. Use when a change touches the Publish, Land, or Finalize rules in plugins/swe/skills/ship-pr, its stacked reference, or the babysit-pr, ship-stack, autopilot-full, or autopilot-stack playbooks, or when the check fails.
paths:
  - plugins/swe/skills/ship-pr/SKILL.md
  - plugins/swe/skills/ship-pr/references/stacked.md
  - plugins/swe/skills/ship-pr/references/verdict-brief.md
  - plugins/swe/skills/swe-mode/playbooks/babysit-pr.md
  - plugins/swe/skills/swe-mode/playbooks/ship-stack.md
  - plugins/swe/skills/swe-mode/playbooks/autopilot-full.md
  - plugins/swe/skills/swe-mode/playbooks/autopilot-stack.md
---

# Verify the pull-request lifecycle

The swe plugin writes the pull-request lifecycle as prose: `ship-pr`
publishes drafts, Land merges with an independent verdict keyed to the
patch-id, Finalize marks a draft ready, and the playbooks land a stack from
the bottom. No code runs these rules. An agent follows them. `PrLifecycle.tla`
models the written protocol, and TLC checks each rule in every order of steps
that the protocol allows, with pushes by other people at any time.

## The rules

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `MergedPatchVerified` | A merged PR has a PASS verdict whose patch-id is the patch that GitHub merged. | Code that no verifier judged lands on trunk. |
| `DoneOnlyAfterMerge` | The issue is Done only when every PR for it has merged. | The tracker says the work shipped while a PR still waits. |
| `IssueNeverBackward` | The issue status never moves back (In Progress, In Review, Done). | The tracker reopens finished work. |
| `DraftUntilLandOrFinalize` | A PR leaves draft only through Land or Finalize. | A PR looks review-ready with no verdict or re-verification. |
| `ActsWithAuthority` | A PR exists only under a request that authorizes publication, and merges only under one that authorizes a merge. | A question or a local-only request ends in a public PR or a merge. |
| `MergeAtFrontier` | In a stack, a PR merges only after every PR below it merged. | A child lands on trunk without its parent. |

## Run it

From the repository root:

```sh
uv run .agents/skills/verify-pr-lifecycle/scripts/check.py
```

It needs uv and mise. It uses the statechart skill's pinned TLC and Java
through `.github/scripts/statechart_tlc.py`, or `TLA2TOOLS` and `JAVA` when
they are set. It runs the 12 runs in `RUNS` in parallel, in about 4 s. It
exits 0 only when each run gives its expected result:

- `holds`: each rule holds on the current protocol.
- `finding`: a known hole in the current protocol still breaks its rule.
- `past bug`: the protocol before a past fix breaks the rule that the fix
  restored.
- `mutant`: a broken variant breaks a rule that no past bug broke.

For each rule that breaks, it prints TLC's shortest path as a list of
actions. `--keep` keeps the TLC configs and output.

Read every result, and draw the lifecycle, with the `statechart` skill. Give
it `PrLifecycle.tla`, `chart.cfg`, and the view `chart-view.mjs`.
`chart.mmd` and `report.md` are its output for `chart.cfg`: one PR, each
request, and one push, 41 states. The view hides the FAIL verdict steps; a
FAIL leaves the PR in a "no PASS for this patch" state. The check also runs
`chart.cfg` as a run, so a constant that the config leaves out fails the
check. After a change to the model or the view, draw the chart again and
replace both files.

## Findings in the current protocol

Each finding is a `finding` run. When a fix lands, move its run to `holds`,
and remove the finding from this file.

- **`gh stack merge` lands a head that was pushed after the recheck.**
  `MergedPatchVerified`. Path: `Publish -> GetVerdict -> GetVerdict ->
  Recheck -> Push -> Recheck -> MarkReady -> MarkReady -> StackMerge`. The
  Land stack paragraph (`ship-pr/SKILL.md:273-280`), `stacked.md:36-41`, and
  `ship-stack.md:12` land a fully verified stack with
  `gh stack merge <stack> --yes`. `gh stack merge --help` says that it
  checks only that each PR is open and not a draft, and it takes no head
  SHA. A push to any PR between the last recheck and the merge lands a patch
  that no verdict judged. A single PR merges with `--match-head-commit`,
  which GitHub refuses when the head moved, so it is safe.
- **ship-stack step 3 keeps a verdict across a push that changes only tests
  or docs.** `MergedPatchVerified`. Path: `Publish -> GetVerdict -> Push ->
  Recheck -> MarkReady -> Merge`. `ship-stack.md:11` lets "a lane's result
  stand" when only tests, docs, or lint config differ, and step 4 merges once
  "its verdict survives step 3". Land step 3 (`ship-pr/SKILL.md:243-245`)
  says that a changed patch-id needs a new verdict. The two rules disagree.

## How the model maps to the protocol

Each action is one step that the protocol allows. Lines are at the sync
commit below.

| Action | Protocol |
| --- | --- |
| `Init` (`request`) | Publication authority, `ship-pr/SKILL.md:12-29`. `hold` is a question, a review, a local-only request, or a hold point; `publish` is `/ship-pr`; `finalize` is `/ship-pr finalize`; `implement` is an implementation request or a request to merge. |
| `Publish` | Publish 1-7, `ship-pr/SKILL.md:95-166`; a stack is one `gh stack submit --auto`, `stacked.md:16-25`. |
| `Push` | Any push to an open PR's branch: a fix wave (Drive to green 4), a conflict move (`ship-stack.md:12`), an owner's fix round (`autopilot-full.md:11`), a bot, or a person. `MaxPushes` bounds them. |
| `GetVerdict` | Land 1-2, `ship-pr/SKILL.md:227-242`, and `verdict-brief.md`: the verdict names the head it judged. |
| `Recheck` | Land 3, `ship-pr/SKILL.md:243-249`; `ship-stack.md:11`. |
| `MarkReady` | Land 4, `ship-pr/SKILL.md:250-258`. It acts on the last recheck, not on the live head. |
| `Merge`, `MergeRefused` | Land 5, `ship-pr/SKILL.md:259-271`: `gh pr merge --match-head-commit <head-sha>`; `ship-stack.md:12` for each PR of a partial run. |
| `MergeAtFrontier`, the `Frontier` guard | `ship-stack.md:10` and `:12`, `babysit-pr.md:8`, `ship-pr/SKILL.md:276-280`. |
| `StackMerge` | `ship-pr/SKILL.md:273-276`, `stacked.md:36-41`, `ship-stack.md:12`. |
| `FinalizeReady` | Finalize 1-4, `ship-pr/SKILL.md:284-297`, with no merge authority. |
| `IssueToReview`, `IssueToDone` | Finalize 5, `ship-pr/SKILL.md:298-305`. |
| `TrackerClosesIssue` | Publish 6, `ship-pr/SKILL.md:153-164`: the top PR carries `Closes <key>`, and the tracker closes the issue when it merges. |
| `DraftUntilLandOrFinalize` | `ship-pr/SKILL.md:83-85`. |

`Variant` selects the current protocol or a past or broken one. Each past
bug was replayed against the protocol text at the commit before its fix:

- `proactivePublish`, fixed by `c491b05` (2026-09-07). From `566458c`
  (2026-08-12), `ship-pr` ran "proactively by default ... never wait for the
  user to ask" (description and line 14 at `c491b05^`). Path:
  `Init -> Publish` with a `hold` request.
- `finalizeMovesDone`, fixed by `c491b05`. Finalize at `c491b05^` ran
  `gh pr ready` (line 147), then "move them to review/done per the tracker's
  states" (line 148), and merging was "not part of this skill" (line 134).
  Path: `Publish -> FinalizeReady -> OldFinalizeMovesIssue`.
- `readyOnRequest`, fixed by `c57bc85` (2026-10-29). At `c57bc85^`, lines
  78-80 let a request change the draft state in any mode. Path:
  `Publish -> ReadyOnRequest`.
- `noiseCarry` is the ship-stack finding above.

The mutants: `unpinnedMerge` (Land merges without `--match-head-commit`),
`anyVerifiedMerges` (a verified PR above the frontier merges), and
`reviewAfterMerge` (Finalize 5 without "waits for merge" or "never
backward"). Since `4561e00` (2026-10-13) every written agent merge was
pinned, and before it the merge was a human action, so no past protocol
breaks `MergedPatchVerified` through an unpinned `gh pr merge`.

### Bounds

One PR with each request and two pushes, a stack of three with two pushes
(about 5,600 states), and a stack of two with one push for the
`gh stack merge` finding.

### Left out

CI and mergeability (Land 3 and 4 check them), review threads, commit
grouping, the PR-body hook, force-push rules, worktrees, branch cleanup, and
the release or deploy approval in Land 5. A clean restack keeps the
patch-id, so the model leaves it out; a restack that resolves a conflict is
a `Push`. A ready PR that gets a FAIL verdict stays ready, because the
protocol says nothing else. The tracker's GitHub integration is modeled only
for the `Closes` link on the top PR. Independent PRs for one issue
(`autopilot-full`) are not modeled.

## Coverage

`plugins/swe/skills/ship-pr/SKILL.md` (Publication authority, Shared rules on
drafts and merges, Publish 5-6, Land, Finalize),
`plugins/swe/skills/ship-pr/references/stacked.md`, `verdict-brief.md`, and
the playbooks `babysit-pr.md` (step 2), `ship-stack.md` (steps 2-4),
`autopilot-full.md` (steps 2, 8), and `autopilot-stack.md` (steps 2-3).

Sync commit: `70183a0`. At that commit the model describes the protocol.
Move it forward only after you confirm that the model describes the protocol
at the new commit.

The check does not read the protocol. A change to a covered file passes the
check until someone changes the model to match. So after a change to a
covered rule, update the action first, then run the check.

## When the check fails

1. Run the check on the base commit and on your change.
2. A `holds` run that fails: read the path with the `statechart` skill.
   Walk it through the protocol text, one step for each action. When the
   text allows every step, the change opened a hole, or the rule changed on
   purpose. When the text forbids a step, the model is wrong: fix the
   action, not the rule.
3. A `finding` run that fails: the change closed the hole. Move the run to
   `holds`, and remove the finding from this file.
4. A `past bug` or `mutant` run that fails: the model no longer reaches that
   bug. Check that the variant still matches the old text.
5. Change a rule only when the promise changed, and say why in the same
   change. Never flip an expected result only to make the check pass.
6. "TLC failed": a parse or config error. Read the output that it prints.
