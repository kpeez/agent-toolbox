# Design the change before you build it

This page shows how to settle the shape of a change before code locks it in. The first design an agent thinks of is rarely the best one, and a plan that no code has tested hides its weak points. You use `architect` to pick a shape, `codebase-design` for one interface, `interview-user` for decisions only you can make, prototypes for questions a run can answer, and a written plan last.

## Settle the shape with architect

```text
/swe:swe-mode design the import pipeline before writing any code. i care most about how callers use it.
```

The router runs [`architect`](../skills/architect/SKILL.md) on its own when code crosses a function boundary. You can also type `/swe:architect` to start it directly. In Codex, the same commands start with `$`, such as `$swe:swe-mode` and `$swe:architect`. It works from one short brief. It traces every system the change touches. Then it sketches two different shapes, each with types, signatures, and module boundaries. It picks the shape where each piece of state has one owner, each task has one way to do it, and callers need to know least.

The design is not sacred once code starts. When the same workaround keeps coming back, `architect` redesigns instead of patching around it. A large or contested design uses [`codebase-design`](../skills/codebase-design/SKILL.md) in design mode. To see the design before any code, say so in the prompt.

## Design one interface with codebase-design

For a bounded design with one obvious shape, [`codebase-design`](../skills/codebase-design/SKILL.md) in design mode is enough. It maps the real callers, then states invariants, ordering, error modes, and costs before it picks the interface. Its goal is depth, which means a lot of behavior behind a small interface.

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

## Review a plan in your browser

```text
/swe:swe-mode show me a plan for quiet hours per notification channel that i can review on my phone.
```

The router runs [`html-plan`](../skills/html-plan/SKILL.md). The agent writes one HTML page. It holds a tree of claims, and one exhibit proves each claim: a mockup, a state machine, a call stack, a schema, or code. Each decision you must make sits on the claim it changes. Open the tree one level at a time, pick options, edit a schema, and comment on any claim. Then press **Respond**, press **Copy response**, and paste the response into the session. The agent applies your answers and builds nothing before you sign off.

The agent saves the page in `.agents/docs/plans/`. If the `tailnet-share` command exists, the agent runs it and gives you a link. Otherwise the agent gives you the file path. Ask for a private published page when you want one. After you sign off, the agent links the plan on the tracker issue and starts work. The skill is a copy of Thariq Shihipar's `html-plan`. The [credits](../../../README.md#credits) name its source.

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

## Run workers on another agent CLI

```text
/swe:external-agents find every caller of parse_config under src/ and say which ones ignore its error. one worker per package.
```

`external-agents` runs three to five workers on another agent CLI, OpenCode or Antigravity (`agy`), and checks every answer in the code before it reports. Name the CLI in your prompt; with no name, it uses OpenCode. There is no runner script: the lead starts each worker with the command in the CLI's reference. An agy worker runs its commands in agy's OS sandbox with no network. OpenCode has no sandbox. Its scout cannot edit files or run shell commands, so it reads the lead's current directory, including uncommitted changes. Other questions workers use a throwaway worktree. In Claude Code auto mode, see [host-permissions.md](../skills/external-agents/references/host-permissions.md) first.

For a large task, hand one worker a whole spec:

```text
/swe:external-agents give antigravity the spec in docs/specs/csv-import.md to implement, then review it
```

In delegate mode, the lead starts from a clean base. An OpenCode builder commits on the task branch; the lead commits an agy worker's changes after each round. The lead reviews each commit against the spec and runs the checks itself. For gaps, it resumes the worker's session with only the findings. After three review rounds, the lead finishes any gaps or brings them to the user. The report lists requirements, rounds, commits, checks, and the branch.

Each CLI has a reference in [references/](../skills/external-agents/references/):

- [OpenCode](../skills/external-agents/references/opencode.md): needs OpenCode 2.x (`@opencode/cli`) and the `scout` and `builder` agents. Each role uses its fallback list in `~/.config/swe/opencode.json`, or its agent's configured model when the list is absent.
- [Antigravity](../skills/external-agents/references/antigravity.md): needs `agy`, signed in once in an interactive session. The workers use your agy model unless you name model slugs.

Providers can keep your prompts, so use the skill only on code you agree to send to them.

## Get an independent review

Many steps say `reviewer agent`. That is a fresh subagent that did not write the code, briefed with the [review brief](../references/review-brief.md). The brief has two modes. In review and fix mode, the default, the reviewer fixes small, sure findings and reports each fix. In verdict only mode, it edits nothing. A landing verdict and parallel reviews of one change use verdict only.

The router gives a contested design and its evidence to a reviewer before you ship. `architect` can also give its chosen sketch to a reviewer before implementation. Ask for it when the design is expensive to reverse:

```text
/swe:swe-mode add rate limiting for external webhooks. architect it first, then have a reviewer agent attack the sketch before you implement.
```

## Write a plan after the design settles

For work that spans phases or stacked PRs, the [plan-multi-phase playbook](../skills/swe-mode/playbooks/plan-multi-phase.md) writes the plan:

```text
/swe:swe-mode turn this design into a plan. small verifiable PRs, each with its own verification steps.
```

It has five steps. It skips the plan for a one or two file change. Otherwise it settles open questions by prototype. Then it writes the plan file. The file lists what changes, the PR ids in landing order, and a dependency graph. Then it has one section per PR with checkboxes: depends on, files, the one change, the result you see, and verification. A PR is verified only when its unit, live, and perf boxes are checked. The playbook hands back the plan path and stops. The plan is the deliverable, so it implements nothing until you say go.

Smaller work needs no plan file. Use plan mode, or ask for a plan in chat. A plan's HTML source lives in `.agents/docs/plans/`, or in `.agents/scratch/<branch-slug>/` when the project has no `.agents/docs` folder. Keep a plan in `.agents/docs/plans/` after its PR merges, because it states the intent of the work. Delete a scratch plan when its PR merges. [Plan storage](../references/plan-storage.md) covers where these files live.

## Match the design work to the task

Most changes need none of this. Use this list to pick:

- A change inside one function needs no design step.
- A change that crosses a function boundary gets `architect`. The router does this on its own. A large or contested design adds `codebase-design` in design mode.
- One new interface with an obvious shape gets `codebase-design` in design mode.
- A question a run can answer, such as a layout, a timing, or an approach, gets a prototype.
- A product or preference call gets `interview-user`.
- A plan or design you want to review and answer in a browser gets `html-plan`.
- A coverage matrix or a set of parallel checks gets `swarm`.
- A contested design gets a reviewer agent before you ship.
- Work across several PRs gets a plan after the design settles.

Next: [Build and clean the change](05-build-and-clean.md).
