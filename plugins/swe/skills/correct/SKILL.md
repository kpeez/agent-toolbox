---
name: correct
description: "Stop a repeated agent mistake by fixing its class at the highest level that works: architecture, types, lint or check, test, docs last. Use when the user corrects a mistake agents have made before, or asks to encode a lesson."
argument-hint: "<repeated mistake>"
---

# Correct

Change the repository so that the next agent cannot make the same mistake.

Contributor model: every contributor is an agent that sees only the files it
opened, copies the nearest example, and takes the shortest path that passes.
Design the repository so that a change that looks right from one file is
right for the whole repository.

This skill applies
[encode-lessons-in-structure](../principle-encode-lessons-in-structure/SKILL.md).
Run it again each time the user corrects you.

## Find the mistake classes

Read the current correction, recent commits and reverts, review comments,
agent instruction files, and comments that explain workarounds. Group the
mistakes into classes. A class counts at its second occurrence. A first
occurrence gets its fix and nothing more.

## Fix each class at the highest level that works

1. `architecture`: remove the mistake. Give each piece of state one owner and
   each task one supported path. Hide internals so that a wrong import fails.
   Replace hand-synced lists with one source of truth. Delete old paths and
   dead code that an agent would copy.
2. `types`: make the bad state impossible to write.
3. `lint-or-check`: when bad code still builds, add a lint or check whose
   error names the file, type, or function to use instead. When the pattern is
   already common, fail only on new instances.
4. `test`: test the behavior. Fix or delete any test that still passes when
   the behavior it checks breaks, or that fails when only the internals
   change. Every new permanent test goes
   through the admission gate in [testing-code](../testing-code/SKILL.md).
5. `docs-last`: write a doc or agent rule only for a judgment call. Nothing
   fails when an agent skips a doc, so make the rule prominent and add an
   example of the mistake.

When a structural fix works, remove the instruction that it replaces. The
instruction was the symptom.

## Fix and prove

- Fix the most frequent classes first, one commit per class, when commits are
  authorized.
- Prove that each new enforcer fails on a real past mistake: run it against
  that mistake, see it fail, then see it pass on the fix.
- Run the same command locally, and in CI where CI exists.
- An exception sits on the offending line with a reason, an expiry date, and
  the user's approval.

## Keep the rule table

The repository keeps a rule-to-enforcer table in the file that its
`AGENTS.md` names. When no table exists, create one in a docs file and add one
`AGENTS.md` line that points to it.

- Add one row per rule when you add its enforcer.
- When the user corrects you, fix the mistake and add its rule.
- When the user corrects a mistake whose rule is already in the table, check
  that its enforcer still exists and still runs. An enforcer that was deleted
  or no longer fails counts as a repeat: fix the class at a higher level in
  the same change.
- Remove a row when its mistake can no longer happen.

## Reply

Each class with its evidence, the level you chose, why a higher level did not
work, and the failing-then-passing output of each new enforcer.
