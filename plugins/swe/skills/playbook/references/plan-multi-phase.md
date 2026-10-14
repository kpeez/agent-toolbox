# Multi-phase plan rules and skeleton

Read this reference from the [plan-multi-phase](../playbooks/plan-multi-phase.md)
playbook. It holds the verification rule, the verification surface, and the
plan skeleton. The checker
[check_plan.py](../../../scripts/check_plan.py) enforces the skeleton.

## Verification rule

Tests alone are not sufficient verification. A PR is verified only when its
unit, live, and perf boxes are all checked
([prove-it-works](../../principle-prove-it-works/SKILL.md)). That sentence is
the verification rule. Every verification block opens with it.

- **Live block.** The live block is mandatory. Ten lanes at the PR head drive
  the real surface through the verification surface below, per the
  [swarm](../../swarm/SKILL.md) skill, on the swarm workers' model (in Claude
  Code `sonnet` by default; in Codex a set reasoning effort). Each lane is
  one box with a concrete scenario, the screenshot it saves, and its pass
  predicate.
- **Regression lane against trunk.** One lane runs the same load-bearing
  scenario on trunk and on the head. When trunk does not have the feature,
  the lane records that fact. It then gates the behavior the diff adds plus
  the end state the user waits for. It never invents a trunk result.
- **Perf gate.** The perf gate is dual-sided. Trunk and the head must both
  produce the named metric. When trunk lacks the feature, also isolate the
  work the diff adds, and set an absolute budget for that work plus the
  end-to-end state the user waits for. Do not claim a ratio between unlike
  scenarios. The perf block names the metric, the interleaved probe, the
  trunk baseline measured first, and the rule with the number that fails.
- **Review gate.** A PR that changes an interaction is review-gated. The
  operator reviews it in chat with screenshots and a video before merge. A
  PR that changes no interaction writes
  `**Review gate.** None. <PR id> is not review-gated.` and no boxes under it.

## Verification surface

Pick it by surface. Use the project's verification skill (see
[verification-skill](../../verification-skill/SKILL.md)) when one exists.
Otherwise drive the real entry point: a browser driver for a web or Electron
UI, the binary for a CLI or TUI, and the repository's simulator skill for
native mobile. A PR that touches two surfaces gets lanes on both. A surface
with no way to drive it is a risk in Appendix C, and its live block still
names how each lane drives it.

## Plan skeleton

Copy this skeleton into the plan file and fill every placeholder. Keep every
heading and every sub-block in the order shown. Write one section per PR.

````markdown
# <Program> plan

<Under ten lines. What changes, for whom, the rule the program enforces, and the PR ids in order.>

## How to read this

One box is one unit of work. Every box names the evidence that checks it. A nested box is a sub-step of the box above it. Check a box only when its evidence exists, a file, a log line, a screenshot, a test run, or a SHA. The body is a how-to. The appendices explain and record.

The program runs the swe playbook `playbooks/<execution playbook>.md`. <Who merges, and which PR ids are the operator's items that stop at merge-ready.>

Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

## Program checklist

### Arm the program

- [ ] State the protocol and this plan to the operator, then stop. Start execution only on the operator's explicit go.
- [ ] Re-read these at program start and at every tick.
  - [ ] The execution playbook `playbooks/<execution playbook>.md` of the swe playbook skill.
  - [ ] The swe `swarm` skill.
  - [ ] `<verification skill path>`
  - [ ] The swe `ship-pr` skill.
  - [ ] <Each other skill the program uses.>
- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below. In Codex, run the tick prompt by hand each hour. Never leave the cadence to memory.
- [ ] Use this tick prompt, verbatim. "Re-read the execution playbook. Audit the operation against it and fix drift in this tick. Probe every active lane and judge progress by side effects only. Stand down a stuck lane and dispatch its replacement now. Then post a short status message to the operator in chat only when the audit found a tracked change that no earlier status message reported, such as a PR opened, a code-ready head, a round launched or closed, a verdict, a merge, a stuck agent and the action taken, a blocker added or cleared, or a decision only the operator can make. Name every such change and nothing else. Do not repeat a table, the merged list, or an unchanged blocker. If the audit found none, end the turn with no reply text. Either way, log this tick's row in the decision log. The row names the items reported, or none."
- [ ] On the operator's hold or stand-down, send every owner a zero-writes order at once.

### Spawn owners

- [ ] Spawn one owner per PR with the full lifecycle the execution playbook names.
- [ ] Follow this dependency graph. Start dependent work only after its parent merges, or base it on the parent branch when the execution playbook stacks.
  - [ ] <PR id> and <PR id> are independent and first. Both branch from `main`.
  - [ ] <PR id> after <PR id>.
- [ ] Hold the file boundaries. <PR id or class> touches only `<glob>`.
- [ ] Hold the review gate. <PR ids> change an interaction. They wait for the operator's review in chat with screenshots and a video before merge.

### PR mechanics, for every PR

- [ ] Use `gh` for every PR operation. Never require `gt`.
- [ ] Open the PR as a draft per the swe `ship-pr` skill, with `gh pr create --draft --base <base-branch>`. A stack child targets its parent branch.
- [ ] Run the repo's lint and typecheck once before the PR-facing push. Push with hooks on.
- [ ] Run `unslop` and a self-review of the diff before each commit, and `no-comments` before review.
- [ ] Triage every review-bot and security-reviewer comment per the `ship-pr` bot-triage reference.
- [ ] Rebase onto current trunk before the code-ready report and the babysit. Keep that merge base in fix rounds. Rebase again only at merge prep, on a `git merge-tree` conflict with trunk, or on a CI failure that comes from a change on trunk.

### Verdict and merge, for every PR

- [ ] A full swarm runs once, at the code-ready head. Another full swarm runs only for new behavior, a redesign, or a large new diff. A rebase, a merge-conflict resolution, or a minor fix gets a single verifier at the new head. Run each full swarm per the swe `swarm` skill. One gates lane. The ten live lanes from the PR's **Verify, live** block. The perf lane from its **Verify, perf** block. Two or more audit lanes, each with its own focus, that read the diff and the receipts and distrust the PR body. The root audits the receipts in the merge-ready report before the verdict.
- [ ] Clean only when every lane is `PASS`. Findings go back to the owner, including a defect that a lane filed as a note. A new head gets a fresh verdict, except for results that stay valid under the patch-id rule in the `ship-stack` playbook.
- [ ] <The merge or append rule from the execution playbook, with the patch-id rule from the `ship-stack` playbook.>

### Boot recipe, for every live lane

Each live lane runs in its own worktree or cloud session at the PR head. Drive through `<verification skill or driver>`.

- [ ] `git fetch origin <head-branch> && git checkout <head SHA>`.
- [ ] <Start the backend and the surface. Wait for ready.>
- [ ] <Deliver input only through the verification skill's commands. Name the read-only diagnostics.>
- [ ] Save every screenshot to `/tmp/swarm-<pr-id>/worker-<n>/<slug>.png` and return the paths with the report.

## <Task as a verb phrase> (<PR id>)

**Depends on.** <PR id, or None.>

**Files.**

- [ ] Edit `<path>`.
- [ ] Create `<path>`.
- [ ] Delete `<path>`.

**Build.**

- [ ] <One change. Name the symbol and the file.>

**You see.**

- [ ] <One observable result, with the exact log line or screen state.>

**Verify, unit.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] <Test file and the case it gains.> Run `<command>`.

**Verify, live.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked. Ten lanes on `<swarm workers model>` at the PR head, per the boot recipe.

- [ ] Lane 1. Regression lane against trunk. Run <the same load-bearing scenario> at trunk and head. If trunk lacks the feature, record that and gate <the behavior the diff adds plus the end state the user waits for>. Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 2. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 3. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 4. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 5. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 6. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 7. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 8. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 9. <Scenario.> Save `<slug>.png`. Pass when <predicate>.
- [ ] Lane 10. <Scenario.> Save `<slug>.png`. Pass when <predicate>.

**Verify, perf.** Tests alone are not sufficient verification. A PR is verified only when its unit, live, and perf boxes are all checked.

- [ ] Metric. <What is measured at both trunk and head. If trunk lacks the feature, also name the diff-added work and the end-to-end state the user waits for.>
- [ ] Probe. <The command or procedure, run at trunk and at the head, interleaved. Both sides must produce the metric.>
- [ ] Baseline. Record the trunk <value> first.
- [ ] Rule. <Head against trunk, with the number that fails. If the scenarios differ, add absolute budgets for the diff-added work and the user-visible end state instead of an invalid ratio.>

**Review gate.** The operator reviews before merge.

- [ ] Copy lane <n> screenshots into `<media path>/<pr-id>-review-<slug>.png`.
- [ ] Record a 30 to 60 second video of the change in a lane session. Save it as `<media path>/<pr-id>-review.mp4`.
- [ ] Post the screenshots and the video in chat. Stop at merge-ready. Wait for the operator's click.

**Merge.**

- [ ] Root's clean verdict at the exact head SHA.
- [ ] Review-bot triage done.
- [ ] Rebased onto current trunk after the verdict, patch-id unchanged.
- [ ] <The owner squash-merges its own PR, or the root appends it to the base-branch stack and the operator lands it bottom-up.>

## Close the program

- [ ] Every box above is checked with its evidence.
- [ ] Reply to the operator with the report the execution playbook names.

## Appendix A. Prototype evidence

<Each open question a prototype answered, with the branch, the SHA, and the artifact links. Each question that stays unproven.>

## Appendix B. Alternatives rejected

<Each approach weighed and why it lost.>

## Appendix C. Risks

<Each risk with the PR it lands in and what the owner watches.>

## Appendix D. Links and reading list

<Docs to read before editing. Which PRs get the `how` and `interrogate` skills. The decision log per the `log-decisions` skill.>
````
