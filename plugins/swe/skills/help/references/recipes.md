# Prompts worth copying

Put in the real paths, skills, and done checks. Informal wording works. In
Codex, type `$swe:` in place of `/swe:`.

## Understand

- `/swe:swe-mode read <thread>. restate the underlying issue in your own words, in plain english.`
- `/swe:in-your-own-words <long or messy ask>`
- `/swe:go-deeper <your task>`
- `/swe:swe-mode investigate why <symptom>. give me what we know, what data you used, and your best hypotheses. don't change any code yet.`
- `use how to understand <subsystem>. then use why to find out why it broke recently.`
- `/swe:recall my work on <topic> from last week, then read <issue>.`
- `/swe:swe-mode take over this branch. read the handoff and the decision log, find what's done, and continue. don't redo finished work.`

## Build

- Bug: `/swe:swe-mode <symptom>. repro first, then fix and verify.`
- Bug in an app: `/swe:swe-mode repro this with the project's verification skill. if it repros on main, fix it and show me a video as proof.`
- Feature: `/swe:swe-mode add <behavior>. <current output> stays byte-identical. verify both.`
- Refactor: `/swe:swe-mode move <code> into one module, zero behavior change. record the current output first and prove it's unchanged after.`
- Perf: `/swe:swe-mode <operation> takes <time> on <fixture>. trace it, fix the measured cause, show me before and after.`

## Design and plan

- `/swe:swe-mode prototype a few options for <feature>. take screenshots or videos for me to compare.`
- `/swe:swe-mode we need <feature>. architect it first, and answer open questions with prototypes. let me review before proceeding.`
- `/swe:swe-mode turn this design into a plan. small verifiable PRs, each with its own verification steps.`

## Review and ship

- `/swe:blast-radius the whole branch. don't change anything yet.`
- `/swe:swarm check every package under <dir> against its check script. one worker per package. one report.`
- `/swe:swe-mode open the pr. small ordered commits, evidence in the description.`
- `/swe:swe-mode babysit this pr. get it green.` For status only: `/swe:swe-mode check on pr <number>. anything outstanding?`
- `/swe:swe-mode land the stack.`

## Away and back

- `/swe:swe-mode im stepping away. <goal> in a fresh worktree off <base>. done means <checks>. keep a decision log. don't ask me before committing. if you're truly stuck after a few hours, stop and write up why.`
- `/swe:ketchup` after time away.
- `/swe:swe-mode full autopilot on this queue. each item is independent.`
- `/swe:swe-mode autopilot these changes but stack them, don't ship. i'll land the stack.`
- `/swe:reflect capture what we learned so the next run doesn't repeat it.` Approve only edits that change a future decision.
- `/swe:wait-what` restates the last reply in plain words.
