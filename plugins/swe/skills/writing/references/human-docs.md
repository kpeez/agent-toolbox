# Human docs

A reader comes to a document with one question. The document answers it, then
points to the next page. Write so a tired engineer understands on the first
read. Docs written for agents (a skill, `AGENTS.md`, `CLAUDE.md`) follow
`writing-for-agents` instead. Every doc also follows the
[prose rules](prose.md).

- Cut every word that does no work.
- Use the short, everyday word: "use", not "utilize".
- When a rule makes a sentence worse, fix the sentence another way or leave it
  alone.
- Write the real symbol, file, flag, or command name, not a synonym or a
  description of it.
- Do not invent jargon. Use the words a developer would say out loud. Say what
  a named pattern means the first time.
- Write the current behavior. History earns a line only as a migration step
  the reader must do.
- Ground each claim in the code, not in memory. Write placeholders such as
  `<checkout>` for paths that differ by machine.
- Define a project term on first use, or link to where it is defined.

## Where each fact goes

Every fact has one owning page. Find the owner before you write. When no page
owns the fact, add a page named for its topic and link it from the README.

| Fact | Owner |
| --- | --- |
| What the project is, who it is for, how to install it, one first example | `README.md` |
| How to do one task | `docs/<task>.md` |
| What a component is and how it behaves | `docs/<component>.md` |
| Why a design is the way it is | the PR and the commit, or a short note on the component page |
| Rules for contributors and agents | `AGENTS.md` or `docs/contributing.md` |
| What changed in a release | the PR and the release notes |
| Research, pilots, proposals | the project's notes location, not `docs/` |

The README is the front door, under 100 lines. It has these sections in this
order: title and one paragraph, install, quick start, what is included (one
linked line per part), docs, credits and license. A fact that needs more than
one line belongs on a docs page. When a change makes a doc stale, update the
owning page in the same change. Edit the README only when the change adds,
removes, or renames a top-level part, or changes install.

## Pick the mode first (Diataxis)

One document, one mode. Do not mix modes. Split and link instead.

- **Tutorial: learning by doing.** Say what the learner will build. Every step
  produces a visible result, and you say what they should see. Explanation
  gets one clause and a link.
- **How-to: steps to a goal.** Solve the reader's problem. Assume competence.
  Write action only. Allow forks. Name the guide by the task.
- **Reference: facts for lookup.** Only describe. Be dry, complete, and sure.
  Mirror the structure of the thing described.
- **Explanation: understanding and why.** One bounded topic. Give context:
  design decisions, history, constraints, alternatives. Opinion is allowed
  here and nowhere else.

## Write sentences to the reader (Google developer style)

- Talk to the reader as "you", in the present tense.
- Say who does what. Use the passive only when the actor is unknown or beside
  the point.
- Write instructions as commands. Put the condition before the instruction
  and the common case first.
- No buzzwords, no figurative language, no "please". Never write "simply",
  "easy", or "quickly" in a procedure.
- Do not pre-announce. Do not start consecutive sentences with the same
  phrase.
- Link with words that say where the link goes.
- Headings carry the point, in sentence case. One h1 per page, no skipped
  levels.
- Use numbered lists for sequences and bullets for everything else. Introduce
  a list with a complete sentence. Keep items parallel.
- Put code in code font and UI elements in bold. Use serial commas. Drop
  "etc.".
- Give every command in a copyable block, with the expected result. Make every
  count or tree claim true at the commit that lands it, and include the
  command that regenerates it.

## Other surfaces

- A PR body is a briefing that a reviewer can read in under a minute. Link
  swarm logs, SHA lists, and metric tables instead of pasting them.
- Product UI strings are not documentation. Use the product's copy guidelines
  for those.
