# Design the change before you build it

This page shows how to settle the shape of a change before code locks it in. The first design an agent thinks of is rarely the best one, and a plan that no code has tested hides its weak points. You use `architect` for competing designs, `codebase-design` for one interface, `interview-user` for decisions only you can make, prototypes for questions a run can answer, and a written plan last.

## Settle the shape with architect

```text
/swe:swe-mode design the import pipeline before writing any code. i care most about how callers use it.
```

The router runs [`architect`](../skills/architect/SKILL.md) on its own when code crosses a function boundary. You can also type `/swe:architect` to start it directly. In Codex, the same commands start with `$`, such as `$swe:swe-mode` and `$swe:architect`. It runs in five phases:

1. Ground. It runs [`how`](../skills/how/SKILL.md) over every subsystem the design touches. When the design moves ownership or layers, it also runs [`why`](../skills/why/SKILL.md) on the current shape.
2. Sketch. It runs [`swarm`](../skills/swarm/SKILL.md) as a race with the `rank all` rule. At least two runners on different models (in Claude Code, `opus` and `sonnet`) each write a sketch of types, signatures, and module boundaries with `not implemented` bodies. It needs at least two structurally distinct candidates, screens each one against the [design red flags](../skills/architect/references/design-red-flags.md), picks a base, and grafts in what the others do better.
3. Agree. This phase is opt-in. By default it goes straight to code.
4. Implement. It fills in the sketch. A deviation from the sketch is a signal to report, not friction to absorb.
5. Scrap. When the same workaround shows up across unrelated code, or types need `any` and casts to compile, it throws the sketch out and runs the sketch race again.

To see the design before any code, say so:

```text
/swe:architect with checkpoint. stop and show me before implementing.
```

The output starts with the caller's usage, then the types. A rationale file follows the [rationale template](../skills/architect/references/rationale-template.md) and records the synthesis decision.

## Design one interface with codebase-design

Not every interface needs a race. For a bounded design with one obvious shape, [`codebase-design`](../skills/codebase-design/SKILL.md) in design mode is enough. It maps the real callers, then states invariants, ordering, error modes, and costs before it picks the interface. Its goal is depth, which means a lot of behavior behind a small interface.

Review mode looks at modules you already have:

```text
/swe:codebase-design review the storage layer. find shallow modules and propose deepening refactors.
```

A review only reports. It applies the deletion test to each candidate module and ranks what it finds. To build a refactor it proposes, start a new task. The router sends it to the [refactor-structure playbook](../skills/swe-mode/playbooks/refactor-structure.md).

## Settle open decisions with interview-user

Some forks are product or preference calls that no run can settle. [`interview-user`](../skills/interview-user/SKILL.md) asks them in rounds. Each round holds every decision whose prerequisites are settled, and each question comes with a recommended answer. It looks up facts in the code itself and asks you only for decisions.

```text
/swe:swe-mode interview me about the retention policy for exported files before you plan anything.
```

The build playbooks run it only on decisions you have not made. It ends with a summary of settled decisions, rejected options, and open items with an owner.

## Prototype instead of debating

When a run can show the answer, the router does not ask you. It runs the [build-prototype playbook](../skills/swe-mode/playbooks/build-prototype.md):

```text
/swe:swe-mode prototype a few options for the new dropdown menu. take screenshots for me to compare.
```

The playbook names the one decision, builds throwaway variants in a scratch directory outside production source, and puts them behind one switcher. Then it drives each variant and records screenshots, output, or timings. It works for behavior and algorithms as well as UI. It recommends a direction, hands it to the build-feature playbook or `architect`, and opens no PR.

## Fan out workers with swarm

```text
/swe:swarm check every package under packages/ against its check.sh. one worker per package. one report.
```

`swarm` runs N workers in parallel and returns one report. Its shapes are a coverage matrix, a race, a gauntlet of independent checkers, an exploration partition, and verifier lanes. For a race, it declares `first pass`, `rank all`, or `best-of` before it spawns. Each worker reports `PASS`, `ISSUES`, or `BLOCKED` with evidence. A worker that drops out becomes a gap in the report, not a pass.

In Claude Code, when you type `/swe:swarm`, ask for a workflow, or turn on ultracode, `swarm` runs the fan-out as one Workflow script: a `pipeline()` over the slices, a result schema per worker, and a log line for each dropped lane. Otherwise, and in Codex, it spawns workers with the Agent tool.

## Fan out free OpenCode Zen workers

```text
/swe:opencode-swarm find every caller of parse_config under src/ and say which ones ignore its error. one worker per package.
```

`opencode-swarm` runs three to five OpenCode workers on free OpenCode Zen models. The lead writes a JSON task list, and [opencode_swarm.py](../scripts/opencode_swarm.py) runs one `opencode run` per task in parallel, gives the tasks the free models in turn, and retries a failed task once on the next model. Workers are read-only unless you ask for edits, and then each worker gets its own worktree. The lead checks every worker claim in the code before it reports. It needs OpenCode 1.x on your computer. The OpenCode 2 preview has no `run` command. Free models can keep your prompts, so use the skill only on code you agree to send to OpenCode.

## Get an independent review

Many steps say `reviewer agent`. That is a fresh subagent that did not write the code, briefed with the [review brief](../references/review-brief.md). The brief has two modes. In review and fix mode, the default, the reviewer fixes small, sure findings and reports each fix. In verdict only mode, it edits nothing. A landing verdict and parallel reviews of one change use verdict only.

The router gives a contested design and its evidence to a reviewer before you ship. `architect` can also give its synthesized sketch to a reviewer before implementation. Ask for it when the design is expensive to reverse:

```text
/swe:swe-mode add rate limiting for external webhooks. architect it first, then have a reviewer agent attack the sketch before you implement.
```

## Write a plan after the design settles

For work that spans phases or stacked PRs, the [plan-multi-phase playbook](../skills/swe-mode/playbooks/plan-multi-phase.md) writes the plan:

```text
/swe:swe-mode turn this design into a plan. small verifiable PRs, each with its own verification steps.
```

It skips the plan for a one or two file change. Otherwise it settles open questions by prototype, explores in subagents, and fills the skeleton in the [plan rules](../skills/swe-mode/references/plan-multi-phase.md) with one section per PR. Tests alone do not verify a PR. Each PR needs unit, live, and perf boxes. The playbook runs `check_plan.py` on the plan, names the execution playbook, and stops. The plan is the deliverable, so it implements nothing until you say go.

Smaller work needs no plan file. Use plan mode, or ask for a plan in chat. Plans live in `<main checkout>/.agents/plans/`, outside Git. Delete a plan when its PR merges, because the PR and the code are the record. [Run long work](07-long-runs.md) covers where these files live.

## Match the design work to the task

Most changes need none of this. Use this list to pick:

- A change inside one function needs no design step.
- A change that crosses a function boundary gets `architect`. The router does this on its own.
- One new interface with an obvious shape gets `codebase-design` in design mode.
- A question a run can answer, such as a layout, a timing, or an approach, gets a prototype.
- A product or preference call gets `interview-user`.
- A coverage matrix or a set of parallel checks gets `swarm`.
- A contested design gets a reviewer agent before you ship.
- Work across several PRs gets a plan after the design settles.

Next: [Build and clean the change](05-build-and-clean.md).
