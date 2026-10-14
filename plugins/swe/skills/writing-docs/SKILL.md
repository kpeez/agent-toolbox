---
name: writing-docs
description: Write or restructure docs for human readers: a README, a docs/ page, or a plugin guide. Use when creating or editing one, or when a change makes one stale.
---

# Write docs for people

A reader comes to a document with one question. The document answers it, then
points to the next page. Docs written for agents (a skill, `AGENTS.md`,
`CLAUDE.md`) follow `writing-for-agents` instead.

## Where each fact goes

Every fact has one owning page. Find the owner before you write.

| Fact | Owner |
| --- | --- |
| What the project is, who it is for, how to install it, one first example | `README.md` |
| How to do one task (set up a host, add a plugin, run a check) | `docs/<task>.md` |
| What a component is and how it behaves (a plugin, the CLI, hooks, an API) | `docs/<component>.md` |
| Why a design is the way it is | an ADR, linked from the component page |
| Rules for contributors and agents (versioning, checks, layout rules) | `AGENTS.md` or `docs/contributing.md` |
| What changed in a release | the PR and the release notes |
| Research, pilots, proposals | the project's notes location, not `docs/` |

When no page owns the fact, add a page named for its topic. Link it from the
README docs list. A page has one topic and one job: a tutorial, a how-to, a
reference, or an explanation. Split a page that does two.

## The README

The README is the front door. It holds these sections, in this order:

1. **Title and one paragraph**: what it is and who it is for, in plain words.
2. **Install**: the shortest copy-paste path for each supported host.
3. **Quick start**: one example that works after install, with what the reader
   sees.
4. **What is included**: one line per part, each linked to its docs page.
5. **Docs**: links to the other docs pages.
6. **Credits and license**: short; detail lives in `NOTICE` files.

Keep it under 100 lines. When a fact needs more than one line in the README,
it belongs on a docs page; the README keeps a one-line link.

## Each docs page

- Open with one sentence: what the page covers and who needs it.
- Put the task before the mechanism: what to run comes first, how it works
  comes after, under its own heading.
- Give every command in a copyable block, with the expected result.
- Use a table for a set of parallel items (commands, hooks, skills).
- Link to code and other pages by relative path.

## Sentences

- Write the current behavior. History earns a line only as a migration step
  the reader must do ("Remove the old `~/.codex/skills/teach` symlink").
- Make each sentence change what the reader does or knows. Cut slogans and
  policy statements that name no action ("Sound work can stay unchanged").
- Use concrete nouns and exact names: the command, the file, the flag.
- Ground each claim in the code: a count, a default, or a feature you read in
  the source, not one you recall. Write placeholders such as `<checkout>` for
  paths that differ by machine.
- Write for a newcomer: define a project term on first use, or link to where
  it is defined.
- Apply every rule in [prose rules](references/prose-rules.md).

## When a change makes docs stale

Update the owning page in the same change. Edit the README only when the
change adds, removes, or renames a top-level part, or changes install. Then
the README gets one line and a link.

## Check

Done when every item holds:

- Each fact in the change sits on its owning page, once.
- The README has the six sections in order and is under 100 lines.
- Every relative link resolves.
- No sentence matches a pattern in [prose rules](references/prose-rules.md).
- Every command in the change was run, or is marked not verified.
- A fresh subagent given only the README can say what the project is, how to
  install it, and where to read next.
