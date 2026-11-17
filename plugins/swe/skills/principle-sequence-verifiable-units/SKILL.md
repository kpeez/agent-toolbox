---
name: principle-sequence-verifiable-units
description: "When work has several steps, such as a sweep, a migration, or a run of similar edits, or when you stack commits and PRs, split it into small units and check each before the next."
disable-model-invocation: true
---

# Sequence work into verifiable units

Order work as small units. Each unit ends in a state that you can check. Do
not advance until the current unit is green.

In a sweep, a migration, or a run of similar edits, each unit is a bracket.
Start from a known-good state, make one change, run the check, then proceed.
Run the per-unit check even when a tool makes the edits, per
[build-the-lever](../principle-build-the-lever/SKILL.md).

Deliver in the order that proves the work. Put the failing test before the
fix, the subtraction before the reshape, and the baseline before the
treatment. Each commit lands on its own.
