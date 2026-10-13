---
name: principle-sequence-verifiable-units
description: "When work has several steps, such as a sweep, a migration, or a run of similar edits: finish and check each unit before you start the next."
user-invocable: false
---

# Sequence verifiable units

Split the work into small units. Each unit ends in a state that you can check.
A break found at the unit that caused it is cheap to locate; a break found
after a batch is not.

1. Start from a known-good state: a clean baseline on the current trunk.
2. Make one unit of change.
3. Run its check. When the check fails, fix or revert this unit before you
   continue.
4. Repeat. When a script makes the edits, still run the check after each unit.

Order the commits so that they argue for the change: a deletion before a
reshape, a baseline before a treatment, a scaffold before a feature.
