---
name: create-formal-verification-skill
description: "Formally verify one property where a bug costs the most and tests reach the least, then generate a project-local skill that rechecks it. Use for /create-formal-verification-skill, \"model-check this race\", \"prove this invariant\", or when concurrency, retries, state machines, parsers, or unsafe code need more than tests."
argument-hint: "[area or bug]"
disable-model-invocation: true
---

# /create-formal-verification-skill

A test checks the cases that someone thought to write. Formal verification checks every case in a stated scope: every order of steps in a model, every input up to a bound, or every input. This skill finds the part of the repository where that matters most, verifies one property of it, and leaves a project-local skill that lets the next agent check a change against that property. Write that skill for an agent who reads it cold, mid-change, with no knowledge of your work. The user must be able to trust the result and act on it without learning the verification language.

## Choose the target from the code

Answer from the codebase. Ask the user only what you cannot observe. If the user named an area or a bug, start there.

A good target is a promise that the code makes, where a break harms users and tests rarely reach the case that breaks it. Choose the strongest such target in the repository, not the one that is easiest to verify.

## Let the question choose the tool

Pick the tool that answers the question at the lowest cost: a model checker, a proof assistant, an SMT-backed verifier, or another tool.

- Whether events can happen in a bad order usually suits a model checker over a small model of the design. For concurrent and distributed designs, TLA+ is often the best place to start.
- Whether the code itself behaves for every input, as with memory safety, overflow, or a data-structure invariant, usually suits a verifier that runs on the code.
- A property that must hold at every size, where a bound is not enough, can need a proof.

Prefer a tool that the repository's developers can install and run. Tell the user why you chose it.

## What makes it good

- **True to the code.** Every part of the model or proof points to code that a reviewer can open. What the verification treats as one indivisible step is one indivisible step in the code. Names come from this repository.
- **Able to fail.** A check that you never saw fail proves nothing. Show each property failing on a broken variant of the code it guards, such as a removed check or a reordered step.
- **Findings stay findings.** When the current code breaks the property, report it with the counterexample in the code's terms. Do not weaken the property or the model until it passes. Do not change product code unless the user asks.
- **Honest about scope.** Say what is verified, under which bounds and assumptions, and what is left out. A pass covers the model or the bound, not the whole system.
- **Readable without the tool.** State the property and the harm in one plain sentence each. Tell a counterexample as a short sequence of steps in the code's words.
- **Cheap to rerun.** One command, a pinned tool version, and a run short enough that the next agent uses it on every relevant change.
- **Kept in step with the code.** When verified code changes, something tells the next agent that the verification needs another look.

## Generate the verify skill

Write a project-local skill in `.claude/skills/` for Claude Code or `.agents/skills/` for Codex. Give it frontmatter that names the area and says when to use it. Without frontmatter, the skill never registers. From the skill alone, the next agent must be able to:

- tell whether a change touches the verified code,
- run the check,
- tell a real bug from a modeling error,
- update the verification when a change is intended.

Use this repository's real commands, paths, and nouns. Leave no placeholders.

## Prove it before you hand off

Follow the generated skill once, as the next agent would, on a scratch change that breaks the property in the real code. It must catch the break. Then drop the scratch change and confirm that the check is back where it started: passing, or failing only on the findings you will report. A verify skill that never ran is a draft. If the skill misses the break or a step does not run, fix the skill or the verification, not the scratch change.

## Hand off

Tell the user what you verified, which tool you used and why, the bounds, what the check found in plain words, how to run it, and what it does not cover. Suggest a second target only if you found a close one.
