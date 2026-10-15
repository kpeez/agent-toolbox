# Understand the code before you change it

This page shows you how to make the agent understand the code, and you, before it edits anything. Agents usually fail in one of two ways. They misread what you want, or they lack the context to do the work right. [Put up to five things in a prompt](./02-route-work.md#put-up-to-five-things-in-a-prompt) handles the first. This page handles the second.

swe gives you several ways in. `how` explains what the code does now. `why` finds the reasons it has this shape. `recall` and `ketchup` rebuild context you lost. `in-your-own-words`, `sharpen`, and `wait-what` check that you and the agent mean the same thing. Each one makes the agent explain itself in words you can check.

## Start with a read-only investigation

When the cause is unclear, ask for findings, not a fix:

```text
/swe:swe-mode investigate why background jobs time out every few hours. give me what we know, what data you used, and your best hypotheses. don't change any code yet.
```

A read-only question routes to the [`investigate-question`](../../plugins/swe/skills/swe-mode/playbooks/investigate-question.md) playbook. It restates the question, runs `how` over the code paths, and adds `why` when the question is about motivation. The answer has an Overview, Key Concepts, How It Works, Where Things Live, and Gotchas. For a choice between options, it gives a recommendation with a tradeoffs table instead. Every claim carries its source and a confidence tier.

The playbook changes no code and opens no PR. When the findings point at a fix, start the fix as a new task.

## Trace behavior with how

```text
/swe:how do we dedupe notifications? is there an n+1 when we look up subscribers?
```

Ask the question you have. [`how`](../../plugins/swe/skills/how/SKILL.md) answers at the level of a senior engineer who onboards you onto the subsystem. For a single module or a narrow question, one explainer reads and explains in one pass. For a subsystem across several files or services, it first starts two to four read-only explorers on `sonnet`, one per angle. Then an explainer on `opus` writes the answer from their findings.

`how` is hidden from the model's skill list, so the router and the playbook steps load it by path. You can still type it. In Codex, type `$swe:how`. The router also runs `how` by itself before any nontrivial change.

## Find the history with why

```text
/swe:why why was the retry limit set to five? does the reason still hold?
```

[`why`](../../plugins/swe/skills/why/SKILL.md) first builds a code anchor from `git blame`, `git log`, and the PR bodies. Then it starts one read-only investigator per source, all at once:

- git and gh history
- GitHub Issues, plus Linear when its tools exist
- the project's docs folder, such as `.agents/docs/`
- Slack, when its search tools exist

The answer names each source it could not search and why. It also reports a null result, because "nobody wrote down why" is an answer.

Each claim carries one of five tiers from [epistemics](../../plugins/swe/skills/why/references/epistemics.md): direct, supported, inferred, speculative, or unknown. When the question comes before a change, the answer ends with what the change must preserve, what it can change, what to avoid, and the risk.

The two skills combine well. "do why first, then how" is a good prompt when you suspect the history explains the code.

## Rebuild your context with recall

```text
/swe:recall catch me up on the export work from last week
```

[`recall`](../../plugins/swe/skills/recall/SKILL.md) reads three records. The handoff file and decision log in `.agents/plans/` hold the last written state. Your Claude Code or Codex transcripts for this repository hold what you did and decided. The shared record (PRs, issues, and chat) holds what happened around the same code. `recall` defaults to the last 7 days and states its scope back to you.

The brief has a short summary, one line per thread with a status tag such as `[open PR #N]`, the recurring problems, and the next move. Load old context first, then give the new input:

```text
/swe:recall my work on the virtualized list from yesterday, then read this bug report.
```

To resume one specific session, use the `pick-up-session` playbook instead. [Run long work](./07-long-runs.md) covers it.

## Catch up with ketchup

When you come back to a chat after the agent worked for a while, type:

```text
/swe:ketchup
```

[`ketchup`](../../plugins/swe/skills/ketchup/SKILL.md) tells you what changed since your last message, in under 150 words. It opens with how many things need you. It shows screenshots and diagrams first, then one line for each thing you asked for, then each decision only you can make with its recommendation. It changes nothing while it reports.

## Ask for a simpler answer with wait-what

When a reply loses you, type:

```text
/swe:wait-what
```

[`wait-what`](../../plugins/swe/skills/wait-what/SKILL.md) restates the last message with more context, in shorter and plainer sentences, with the project's own terms. It does not start new work.

## Check the agent's reading with in-your-own-words

For a noisy report, such as a long thread or a vague bug, make the restatement the first step:

```text
/swe:in-your-own-words read this thread and restate the underlying issue. don't change any code yet.
```

[`in-your-own-words`](../../plugins/swe/skills/in-your-own-words/SKILL.md) restates your goals and the problem you want to solve. A misreading shows up in the restatement, before any code exists. Correct it there, and it costs you one message instead of one wrong fix.

## Sharpen a vague ask

```text
/swe:sharpen make the search page feel faster
```

[`sharpen`](../../plugins/swe/skills/sharpen/SKILL.md) asks how a top expert would approach the task, what you are really after, and whether the task is over or under specified. It keeps one outside check that the result is right. It does not hand back a rewritten prompt. It does the work with the sharper framing.

## Avoid skipping this page

Do not skip these skills because "the agent will read the code anyway". An agent that edits without a traced model of the code tends to fix the symptom at the first plausible spot. Running `how` first costs less than the second bug.

Next: [Design the change](./04-design.md).
