# Build the change and clean the diff

This page shows what to put in the prompt for each build task, and how swe keeps the diff small and clean before review. You say what you observed and what must not change. The playbook supplies the steps you did not type and asks for the evidence.

## Prompt each build playbook with what you know

A bug prompt states the symptom and asks for a reproduction first:

```text
/swe:swe-mode this command emits two records after a retry. repro first, then fix and verify.
```

A feature prompt states the new behavior and what must stay the same:

```text
/swe:swe-mode add a --json flag. text output stays byte-identical. verify both forms.
```

A refactor prompt pins behavior before the structure moves:

```text
/swe:swe-mode move parsing into one module, zero behavior change. record the current output first and prove it is unchanged after.
```

A performance prompt states a measurement:

```text
/swe:swe-mode startup takes 1.8s on this fixture. measure it, fix the measured cause, show me before and after.
```

Each prompt routes to its playbook:

| Playbook | What it adds to your prompt |
| --- | --- |
| [`fix-bug`](../../plugins/swe/skills/swe-mode/playbooks/fix-bug.md) | Reproduce on the reported surface, binary search the cause, sweep for the same pattern, apply the smallest fix, run the original repro again |
| [`build-feature`](../../plugins/swe/skills/swe-mode/playbooks/build-feature.md) | Map the subsystem, name the data shape, explore designs, write a throughput checkpoint, build and verify one unit at a time |
| [`refactor-structure`](../../plugins/swe/skills/swe-mode/playbooks/refactor-structure.md) | Pin behavior with a characterization test or snapshot, subtract first, move every caller and delete the old API, prove equivalence, revert if reader load did not fall |
| [`improve-performance`](../../plugins/swe/skills/swe-mode/playbooks/improve-performance.md) | Capture a baseline with run count and spread, name the limiting resource, try the performance mantras cheapest first, change one thing at a time |

The four playbooks end the same way. They check the blast radius when the change touches shared state, a wire format, or a public interface. An agent that did not write the diff reviews it. They update the docs the change makes obsolete. Then they push and update the draft PR when publication is authorized. [Verify and ship](./06-verify-and-ship.md) covers those steps.

In `build-feature` and `fix-bug`, the lead delegates the code to the `daedalus` agent and reviews its diff. The gain is the separation between the agent that writes and the agent that reviews.

## Improve one number with hillclimb-metric

For sustained work on one metric, the [hillclimb-metric playbook](../../plugins/swe/skills/swe-mode/playbooks/hillclimb-metric.md) runs a loop. Give it the metric, the target, and a floor on attempts:

```text
/swe:swe-mode hillclimb p50 parse time on the 60k-row fixture. target 400ms. try at least 15 ideas before you stop.
```

It freezes one measurement command, records a baseline, and then tests one hypothesis per attempt. It keeps a change only when the metric moves past noise and the regression gate stays green. Otherwise it reverts the change in full. Each attempt gets a row in a gitignored `decision.tsv`. When the `lab:autoresearch` skill is installed, the playbook runs its loop through that skill.

Both performance playbooks vet their numbers with [`benchmark-checklist`](../../plugins/swe/skills/benchmark-checklist/SKILL.md). [Verify and ship](./06-verify-and-ship.md) shows when to run it yourself.

## Build a scoped change with implement

[`implement`](../../plugins/swe/skills/implement/SKILL.md) makes one authorized, scoped change with evidence. The build playbooks load it for their build steps. It also starts on its own for a small, clear task. It makes the smallest justified change, names the behavior check before it writes code, and runs the repository gates. A failing required gate blocks completion.

`implement` also updates documentation the change makes obsolete, without asking you. When you name a plan file, it reads the plan first and works to it:

```text
Implement the plan in .agents/plans/feature-export-json.md
```

## Write the failing test first with testing-code

[`testing-code`](../../plugins/swe/skills/testing-code/SKILL.md) owns every decision about tests. Its default is no new permanent test. A new test must pass a six-question admission gate (behavior, failure, oracle, owner, seam, and cost), and you must see it fail before you keep it.

For a bug with a cheap local test path, ask for the failing test first:

```text
/swe:testing-code failing test first for the duplicate-record bug, then fix it.
```

It writes the smallest test that fails for the intended reason, makes the smallest fix, and runs the test again. When a test needs broad harness setup or brittle mocks, it uses the closest executable check instead, such as a script or a reproduction command. In the `fix-bug` playbook, the failing repro is committed before the fix when the test is cheap.

To prune an existing suite, ask for audit mode:

```text
/swe:testing-code audit the tests under src/export/. delete what does not earn its cost.
```

## Load the TypeScript rules by name

[`typescript-best-practices`](../../plugins/swe/skills/typescript-best-practices/SKILL.md) turns the type-system principle into rules such as discriminated unions and branded types. It does not start on its own. Type `/swe:typescript-best-practices` when a task touches `.ts` or `.tsx` files.

## Clean the diff before you commit

[`ship-pr`](../../plugins/swe/skills/ship-pr/SKILL.md) sets the cleanup rules. Before each commit, the agent applies the `writing` prose rules to new prose and reviews its own diff for slop. Before review, it runs `no-comments`. The router holds the same rule for comments in every file it writes. A comment stays only for a non-obvious why that the code cannot show.

If the diff feels padded, say so before you commit:

```text
/swe:swe-mode clean the diff. remove narrating comments, unneeded guards, dead paths, and unrelated edits.
```

## Strip the comments with no-comments

The agent that wrote a comment defends it. So comments go to a reviewer that did not write them:

```text
/swe:no-comments the diff
```

[`no-comments`](../../plugins/swe/skills/no-comments/SKILL.md) spawns [Comment Sicko](../../plugins/swe/agents/comment-sicko.md), a reviewer that deletes comments and never edits application code. Its keep list is short. It keeps license headers, doc comments on a public API, issue or RFC links, and notes on behavior forced by a dependency you cannot change. A surprise in your own code gets no pass. Comment Sicko deletes the comment and flags the symbol `MUST KILL`, so the code gets a rename, a type, or a reshape instead. `no-comments` then fixes the flags it accepts at the root cause. When a comment claims a constraint such as `do not remove`, it offers to encode the constraint as a type, check, test, or lint, and waits for your approval.

## Write prose with writing

[`writing`](../../plugins/swe/skills/writing/SKILL.md) owns every prose surface. It sends a README or docs page to the human-docs rules, a skill or `AGENTS.md` to `writing-for-agents`, and a PR body or commit message to the PR-body rules. The [prose rules](../../plugins/swe/skills/writing/references/prose.md) apply to all of them. The router runs `writing` on every reply as well.

```text
/swe:writing tighten the readme changes. no long dashes.
```

Next: [Verify and ship](./06-verify-and-ship.md).
