# Human docs

A reader comes to a document with one question. The document answers it, then
points to the next page. Write so a tired engineer understands on the first
read. Docs written for agents (a skill, `AGENTS.md`, `CLAUDE.md`) follow
`writing-for-agents` instead. Every doc also follows the
[prose rules](prose.md).

When a rule makes a sentence worse, fix the sentence another way or leave it
alone. A sentence that follows every rule and sounds like a machine wrote it
has failed.

Apply both layers below to every doc: the mode and the sentences. The prose
rules add the statement rules and the Global English rules.

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
README docs list. A page has one topic and one mode.

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

## Pick the mode first (Diataxis)

One document, one mode. Two questions pick it. Does the content inform action
(doing) or understanding (thinking)? Does it serve learning or work?

- Action and learning: **tutorial**.
- Action and work: **how-to**.
- Understanding and work: **reference**.
- Understanding and learning: **explanation**.

Use the same two questions on a whole document or on one sentence.

**Tutorial: learning by doing.** The learner's success is your job, not
theirs. Open by saying what the learner will build, not what they will
"learn". Every step produces a visible result, early and often. Tell them what
they should see: the expected output, the prompt change, the log line. Cut
explanation to one clause and a link. Stay concrete. Write as "we", in
commands: "First, do x. Now, do y."

**How-to: steps to a goal.** Solve a problem a person has, not an operation
the machine can perform. Assume competence and skip teaching. Write action
only. Link background and completeness instead of including them. Allow forks
and judgment: "If you want x, do y." Name the guide by the task: "How to
calibrate the radar array", not "Radar array calibration".

**Reference: facts for lookup.** Only describe. Give no instruction,
persuasion, or opinion. Be dry, complete, and sure. State facts, options,
limits, and errors with no hedging. Mirror the structure of the thing
described, so a reader can move between the code and the docs. Put material
where readers expect it. Generate it from code where possible.

**Explanation: understanding and why.** One bounded topic, readable away from
the product. Each title reads well with an implied "About..." in front. Anchor
on a real why question. Give context: design decisions, history, constraints,
and alternatives. Opinion is allowed here and nowhere else.

Keep each mode pure. A tutorial holds no reference tables, a reference holds
no hand-holding, and a how-to holds no argument. Split and link instead.

## Each docs page

- Open with one sentence: what the page covers and who needs it.
- Put the task before the mechanism: what to run comes first, how it works
  comes after, under its own heading.
- Give every command in a copyable block, with the expected result.
- Use a table for a set of parallel items (commands, hooks, skills).
- Link to code and other pages by relative path.
- Make every count or tree claim true at the commit that lands it, and include
  the command that regenerates it.

## Words

- The codebase is the word list. Write the real symbol, file, flag, or
  command name, not a synonym or a description of it.
- Use the words a developer would say out loud: "move", "delete", "a budget
  that only decreases". Leave out invented jargon such as "evacuate",
  "ratchet", or "endgame". A named pattern is fine when the doc says what it
  means the first time.
- When you find a new jargon word, propose it and its replacement in your
  reply as an addition to rule 26 of the [prose rules](prose.md), with the
  diff. Leave that skill unchanged.
- Write the current behavior. History earns a line only as a migration step
  the reader must do ("Remove the old `~/.codex/skills/teach` symlink").
- Make each sentence change what the reader does or knows. Cut slogans and
  policy statements that name no action ("Sound work can stay unchanged").
- Ground each claim in the code: a count, a default, or a feature you read in
  the source, not one you recall. Write placeholders such as `<checkout>` for
  paths that differ by machine.
- Write for a newcomer: define a project term on first use, or link to where
  it is defined.

## Write sentences to the reader (Google developer style)

- Talk to the reader as "you", in the present tense. Use "will" only for
  things that happen later.
- Say who does what: "the compiler checks", not "is checked". Use the passive
  only when the actor is unknown or beside the point.
- Write instructions as commands: "Click Submit." State facts plainly. Never
  write "should be done".
- Put the condition before the instruction: "To delete the document, click
  Delete."
- Put the common case first and the exceptions after.
- Sound like a knowledgeable friend. Use no buzzwords, no figurative language,
  and no "please" in instructions. Never write "simply", "easy", or "quickly"
  in a procedure. If it were simple, the reader would not be here.
- Do not announce future work ("we will soon support..."). Do not start
  consecutive sentences with the same phrase.
- Write link text that says where the link goes: the page title or a short
  description. Never write "click here". Prefer a sentence of context on the
  page over a link off it.
- Make headings carry the point, not just the topic ("Pick the mode first",
  not "Modes"). Use sentence case. A task heading is a bare verb phrase
  ("Create an instance"). A concept heading is a noun phrase. Use one h1 per
  page and skip no levels.
- Use numbered lists for sequences and bullets for everything else. Introduce
  a list with a complete sentence. Keep items parallel.
- Put code in code font and UI elements in bold. Use serial commas. Drop
  "etc." and say up front that a list is partial.

## Other surfaces

- A PR body is a briefing that a reviewer can read in under a minute. Link
  swarm logs, SHA lists, and metric tables instead of pasting them.
- Product UI strings are not documentation. Follow the product's copy
  guidelines for those.

## Worked example

Before:

> Configuration of the proto import ratchet budget script parameters is
> performed via budget.json. Note that it's important to remember that
> running with --write, which updates the committed budget to reflect the
> current count, should only be done when lowering it. If exceeded, CI fails.

After:

> `budget.mjs` reads the committed budget from `budget.json` and counts the
> files that import protos. If the count exceeds the budget, CI fails. Run
> `budget.mjs --write` only to lower the budget.

## When a change makes docs stale

Update the owning page in the same change. Edit the README only when the
change adds, removes, or renames a top-level part, or changes install. Then
the README gets one line and a link.

## Check

Done when every item holds:

- Each fact in the change sits on its owning page, once.
- Each page has one mode.
- The README has the six sections in order and is under 100 lines.
- Every relative link resolves.
- Every sentence passes the sentence layer above and the
  [prose rules](prose.md).
- Every command in the change was run, or is marked not verified.
- A fresh subagent given only the README can say what the project is, how to
  install it, and where to read next.
