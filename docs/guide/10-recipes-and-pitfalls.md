# Recipes and pitfalls

This page gives prompts you can copy, then the mistakes most people make once. Swap in your own paths and done checks. The prompts are informal on purpose, because that is how people type them, and the router reads intent from plain words. In Codex, type `$swe:playbook` and `$swe:<skill>` where these prompts say `/swe:`.

## Understand an unfamiliar subsystem

```text
/swe:how how does session initialization work? then /swe:why to find out why it broke last week.
```

Mechanics first, history second. Each report says which sources it searched, so you know what the answer rests on.

## Restate a noisy report before you touch code

```text
/swe:in-your-own-words read this thread and restate the underlying issue. don't change any code yet.
```

A misreading shows up in the restatement, where it costs one message to correct. Keep your own theory to yourself until the agent has stated its own.

## Prototype before you pick

```text
/swe:playbook prototype a few options for the settings layout. put them behind a switcher and send me screenshots of each.
```

The [build-prototype](../../plugins/swe/skills/playbook/playbooks/build-prototype.md) playbook builds throwaway variants in a scratch directory and opens no PR. You pick from things that run, not from descriptions.

## Turn a settled design into a plan

```text
/swe:playbook turn this design into a plan. small verifiable PRs, each with its own proof.
```

Ask only after the design settles. The [plan-multi-phase](../../plugins/swe/skills/playbook/playbooks/plan-multi-phase.md) playbook settles open questions by prototype, runs `check_plan.py` on the plan, and names the playbook that will run it. It stops there until you say go.

## Check independent slices in parallel

```text
/swe:swarm check every package under packages/ against its check.sh. one worker per package. one report.
```

Each worker owns one package. The parent waits for every slice and returns one report with `PASS`, `ISSUES`, or `BLOCKED` per slice, not raw worker output.

## Find what a branch could break

```text
/swe:blast-radius this branch changes the cache key format. what else could it break? don't change anything.
```

You get the one or two facts the change is safe because of, each with the evidence rung it reached. A fact that stopped at `asserted` is not proof.

## Fix a bug through a failing test

```text
/swe:playbook the export writes duplicate rows when a retry lands mid-run. repro first. if there's a cheap test path, commit the failing test before the fix.
```

"if there's a cheap test path" matters. The [fix-bug](../../plugins/swe/skills/playbook/playbooks/fix-bug.md) playbook skips the failing-test commit when the test would be expensive or unclear. A test forced through brittle mocks proves less than the real command.

## Vet a number before you post it

```text
/swe:benchmark-checklist vet this 40% speedup before it goes in the pr description
```

You get faster, slower, no measurable difference, or inconclusive, with the run count, the spread, and what limits the number.

## Stop correcting the same mistake

```text
/swe:correct agents keep adding config flags without registering them in the schema
```

The fix lands in the repository as architecture, a type, a check, or a test, so the next agent cannot make the mistake.

## Keep a run going while you are away

```text
/swe:playbook i'm going to bed. keep going until every fixture passes. do not stop. keep a decision log i can audit in the morning.
```

"going to bed" is a session override. The agent decides each call the grant covers and reports it. [Run long work and hand it off](./07-long-runs.md) covers the decision log and handoffs.

## Redirect a drifting run

Steering prompts are one line:

```text
i said the goal is to repro. i did not ask for a fix yet.
```

```text
apply prove it works. show me the real output, not the build log.
```

```text
new task. the export bug is done. now look at the import timeout.
```

"new task" makes the router match again instead of continuing the earlier playbook. You rarely need more words. You need the right name, and [the principles page](./08-principles.md) is the vocabulary.

## Get the reply in plain words

```text
/swe:wait-what
```

That is the whole prompt. [wait-what](../../plugins/swe/skills/wait-what/SKILL.md) restates the last message in simpler words, with a little context and the project's own terms.

## Avoid these pitfalls

- **Listing skills in the prompt.** "use how, then architect, then swarm" reorders steps the playbook already sequences. State the goal and the constraints. Name a skill only to override a default.
- **A vague done check.** "make it better" gives the agent nothing to check. Give a command or an artifact that can pass or fail.
- **Leading with your theory of the cause.** The agent searches where you point. Ask it to restate the problem first, then share your hunch.
- **Taking the first design.** One attempt locks in the first shape the model thought of. Ask for prototypes or `architect` and pick from evidence.
- **Polishing an abstract plan.** A review of a plan with no code behind it invents risks that never happen. Settle open questions with prototypes, then review what got built.
- **Parallel agents in one worktree.** They overwrite each other's files. Say "own worktree per attempt".
- **Looping before you trust the loop.** A loop that cannot verify its own work only makes unchecked work faster. Get the [verification skill](../../plugins/swe/skills/verification-skill/SKILL.md) working first.
- **Trusting an unvetted number.** A warm cache or a skipped code path can fake a speedup. Run `benchmark-checklist` before the number goes anywhere.
- **Correcting the same mistake by hand.** A correction in chat helps one run. `correct` fixes the repository so no later run repeats it.
- **Accepting every review comment.** Review bots file real catches and noise in one list. The router triages each bot finding on its merits by the [bot triage](../../plugins/swe/skills/ship-pr/references/bot-triage.md) rules.
- **Reporting success off a green build.** A build proves it compiles. Ask for the real command, flow, stored value, or profile, and expect the evidence in the reply.
- **Writing a `SKILL.md` freehand.** Route it through the [author-skill](../../plugins/swe/skills/playbook/playbooks/author-skill.md) playbook so the checks run.
- **Editing a skill mid-task.** Fix a broken skill in its own PR and keep the task moving.

That is the guide. If you skipped ahead, go back to [Set up swe](./01-setup.md) and run one real task. The habits stick from use, not from reading.

Back to the [guide index](./README.md).
