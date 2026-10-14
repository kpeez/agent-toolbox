---
name: principle-sequence-verifiable-units
description: "When work has several steps, such as a sweep, a migration, or a run of similar edits, or when you stack commits and PRs, split it into small units and check each before the next."
disable-model-invocation: true
---

# Sequence work into verifiable units

Order work as a sequence of small units. Each unit ends in a state that you can
check. Do not advance until the current unit is green.

A break caught at the unit that caused it is cheap to locate. A break caught
after a batch is buried, and you have already built on a broken base. When
you sequence those same units into a delivery that a reviewer can replay,
"trust me" becomes "watch it go red, then green".

## Execution

In a sweep, a migration, or any run of similar edits, verify each change
before you start the next. Each unit is a before and after bracket.

1. Start from a known-good state. Rebase onto a clean trunk first, so that
   every check measures against the real baseline.
2. Make one change.
3. Run its check. When the check fails, fix or revert this unit before you
   continue.
4. Repeat.

When a lever makes the edits, the per-unit check is nearly free. Run it
anyway.

## Delivery

Stack commits and PRs in the order that proves the work. The canonical shape is
the failing test first, then the fix on top. Other story orders are a
subtraction before the reshape, a baseline capture before the treatment, and
the scaffold before the feature. Each commit lands on its own, and the
sequence reads as an argument.

This is the sequencing complement to [prove-it-works](../principle-prove-it-works/SKILL.md), which keeps
each check real, and to [build-the-lever](../principle-build-the-lever/SKILL.md), which makes the per-unit
check cheap.
