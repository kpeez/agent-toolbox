# Steer with principle names

This page lists the 25 swe principles and shows how you use their names to redirect an agent in the middle of a task.

Each principle is a short skill named `principle-<slug>`. The skills are hidden from the model's skill list, so they cost no context until a step needs one. The [router](../skills/swe-mode/SKILL.md#principles) lists each slug with the moment it applies. When a playbook step names a principle, the agent reads its `SKILL.md` by path before the step. In the final reply, the agent names each principle that changed a decision and the choice it changed. It cites only the principles it loaded in that session.

You do not start principles yourself. You use their names to steer. Each name points at a complete rule, so one phrase redirects the work more precisely than a paragraph of instructions.

## Steer a run with one phrase

Say the agent is about to add a new adapter next to three old ones:

```text
use subtract before you add. delete the obsolete adapters first, then design what's left.
```

Say it claims success because the build passed:

```text
apply prove it works. run the real import flow and show me the written records.
```

Say two parallel attempts are about to write to the same branch:

```text
separate before serializing shared state. give each attempt its own worktree, no locks.
```

Say the agent found a stale doc next to the code it changed:

```text
apply ancillary fixes. fix the stale doc in this change and list it apart from the main change.
```

Each phrase works because the rule behind it is specific. The agent still must say which decision the rule changed. A citation with no decision behind it means the agent dropped the name and did not apply the rule.

## Know the core principles

The core principles decide how much to build and when to rethink the design.

- [Laziness protocol](../skills/principle-laziness-protocol/SKILL.md) applies when you refactor, size a diff, or want to add an abstraction or a layer. It prefers deletion and the smallest change that solves the problem.
- [Foundational thinking](../skills/principle-foundational-thinking/SKILL.md) applies before you write logic. It chooses the core types and data structures first, and asks what concurrent actors share.
- [Redesign from first principles](../skills/principle-redesign-from-first-principles/SKILL.md) applies when a new requirement meets an existing design. It redesigns as if the requirement had been there from the start.
- [Attack the premise](../skills/principle-attack-the-premise/SKILL.md) applies when two or more fixes that share one premise failed the same check. It writes the premise down and tests it before the next fix.
- [Subtract before you add](../skills/principle-subtract-before-you-add/SKILL.md) applies when you sequence an addition, a refactor, or a rewrite. It removes dead weight first.
- [Minimize reader load](../skills/principle-minimize-reader-load/SKILL.md) applies to code that is hard to trace. It counts layers and hidden state, and collapses layers that do not pay for themselves.
- [Outcome-oriented execution](../skills/principle-outcome-oriented-execution/SKILL.md) applies to planned rewrites and migrations. It converges on the target and keeps no throwaway compatibility states.
- [Experience first](../skills/principle-experience-first/SKILL.md) applies to product, UX, and scope tradeoffs. It chooses the user's experience over implementation convenience.
- [Exhaust the design space](../skills/principle-exhaust-the-design-space/SKILL.md) applies to a new interaction or architecture with no precedent. It builds two or three competing sketches and compares them.
- [Build the lever](../skills/principle-build-the-lever/SKILL.md) applies to many similar edits, a migration, an analysis, or a check. It builds the script, codemod, or generator that a reviewer can rerun.

```text
apply build the lever. write a codemod for the 40 call sites instead of editing them by hand.
```

## Know the architecture principles

The architecture principles decide where state, validation, and compatibility live.

- [Model the domain](../skills/principle-model-the-domain/SKILL.md) applies to stateful logic, heavy branching, or one shape assumption repeated across files. It encodes the domain in one structure.
- [Boundary discipline](../skills/principle-boundary-discipline/SKILL.md) applies to validation, error handling, and framework adapters. It guards at the system edge and trusts internal types.
- [Type system discipline](../skills/principle-type-system-discipline/SKILL.md) applies to types and signatures in a typed language. It makes illegal states unrepresentable and parses external data at the edge.
- [Make operations idempotent](../skills/principle-make-operations-idempotent/SKILL.md) applies to commands, jobs, retries, and resume paths. Every rerun reaches the same end state after a crash at any point.
- [Migrate callers then delete legacy APIs](../skills/principle-migrate-callers-then-delete-legacy-apis/SKILL.md) applies when a new internal API replaces an old one that still has callers. It migrates and deletes in one change.
- [Separate before serializing shared state](../skills/principle-separate-before-serializing-shared-state/SKILL.md) applies when two actors could write the same file, branch, key, or object. It removes the sharing before it adds a lock.

```text
make operations idempotent. a retry after a crash mid-import must not write a second row.
```

## Know the verification principles

The verification principles define what counts as proof.

- [Prove it works](../skills/principle-prove-it-works/SKILL.md) applies before you say a change works. It checks the real artifact through its real entry point and gives a VERIFIED, NOT VERIFIED, or INCONCLUSIVE verdict.
- [Fix root causes](../skills/principle-fix-root-causes/SKILL.md) applies to debugging. It traces each symptom to the first place the system went wrong and fixes it there.
- [Sequence work into verifiable units](../skills/principle-sequence-verifiable-units/SKILL.md) applies to multi-step work and to how you stack commits and PRs. It checks each unit before the next.
- [Test behavior, not implementation](../skills/principle-test-behavior-not-implementation/SKILL.md) applies when you write, change, or keep a test. It asserts what users observe, so a test fails when behavior breaks and survives a change to the internals.
- [Explain the number](../skills/principle-explain-the-number/SKILL.md) applies before you trust, report, or act on a measured number. It names what limits the number, with run count and spread. [benchmark-checklist](../skills/benchmark-checklist/SKILL.md) turns it into questions you answer from real runs.

```text
fix root causes. don't add a null check until you know why the value is null.
```

## Know the delegation principles

The delegation principles keep parallel work in order.

- [Guard the context window](../skills/principle-guard-the-context-window/SKILL.md) applies to large outputs, long files, and fan-out planning. It sends bulk reading to subagents and keeps summaries in the main thread.
- [Never block on the human](../skills/principle-never-block-on-the-human/SKILL.md) applies when the agent wants to ask "should I do X?" about reversible work. It does X, reports it, and lets you correct it.

```text
never block on the human. it's a draft branch. try both and show me the results.
```

## Know the meta principles

The meta principles change the project, not only the current task.

- [Encode lessons in structure](../skills/principle-encode-lessons-in-structure/SKILL.md) applies when the same instruction comes up a second time. It encodes the rule as a lint, flag, check, or script. The [correct](../skills/correct/SKILL.md) skill applies it to a whole repository, as [Make it yours](09-make-it-yours.md#fix-the-repository-with-correct) shows.
- [Ancillary fixes](../skills/principle-ancillary-fixes/SKILL.md) applies when the agent finds an issue outside the task, such as a stale doc, a conflict, a bug, or an unrelated failing check. A lead fixes it when the fix is small, safe, and within the task's authority, and reports it otherwise. A subagent only reports it to its caller.

Only these 25 are principles. A skill such as `testing-code` is not a principle, even when a step names it next to one.

Do not memorize the list. Skim it now. Come back when you see the agent do something that one of these names would have prevented.

Next: [Make it yours](09-make-it-yours.md).
