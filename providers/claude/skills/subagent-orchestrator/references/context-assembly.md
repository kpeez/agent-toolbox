# Context Assembly

Use this file when a thin delegation prompt needs to become a useful subagent
packet.

## Thin prompt

```text
Review this repository and summarize the main risks.
```

That is not enough on its own. It says what to do, but not why, how to judge
the answer, or where to look first.

## Delegation packet

Build a prompt with these fields:

```text
Goal:
Success looks like:
Failure looks like:
Return format:
Relevant skills or domain hints:
Files to read first:
Attached context:
Task:
```

## What to Fill In

### Goal

State why Claude is delegating the task.

Examples:

- Find the highest-risk correctness issues before I spend Claude time reviewing details.
- Produce a cheap first-pass repo map so Claude can focus on judgment instead of discovery.

### Success looks like

State what a useful answer must contain.

Examples:

- A ranked list of the top five risks with file references and short rationale.
- A concise architecture summary that names the modules worth deeper review.

### Failure looks like

State what would make the result unusable.

Examples:

- Generic observations without file references.
- Style-only feedback when Claude asked for correctness or architecture risks.

### Return format

Keep it strict when you want easy review.

Examples:

- Five bullets, each with `risk`, `why`, and `files`.
- Markdown sections: `Summary`, `Risks`, `Open questions`.

### Relevant skills or domain hints

Tell the subagent which domain lens to use.

Examples:

- If this is an Obsidian vault, use obsidian-related skills and pay attention to wikilinks, frontmatter, and vault conventions.
- If the repo uses specs, read the relevant `specs/` files before proposing changes.
- If the task is Python-heavy, use the repo's Python conventions.

### Files to read first

Give an ordered short list.

Good candidates:

- `AGENTS.md`
- `README.md`
- `specs/<feature>/AGENTS.md`
- `specs/<feature>/design.md`
- the specific source files that define the behavior under review

### Attached context

Attach only the chunks that remove ambiguity.

Good attachments:

- the relevant paragraph from `AGENTS.md`
- the exact acceptance criteria from a spec
- a short excerpt from a configuration file

Avoid pasting long files when a path plus a one-line instruction is enough.

## Example: Repo Risk Review

```text
Goal:
Give Claude a cheap first-pass map of the highest-risk architecture and correctness issues in this repo.

Success looks like:
Return the top 5 material risks, each with a file path, why it matters, and what Claude should inspect next.

Failure looks like:
Generic repo summary, style nits, or risks without file references.

Return format:
Markdown with sections: Summary, Top Risks, Follow-up Files.

Relevant skills or domain hints:
Read repo instructions first. If there is a spec for the current feature, use the spec workflow and read those files before judging implementation risk.

Files to read first:
- AGENTS.md
- README.md
- specs/current-feature/AGENTS.md
- specs/current-feature/design.md
- src/auth.py
- src/session.py

Attached context:
- Current task: review correctness and architecture risk, not style.
- Spec note: feature is still in implementation phase.

Task:
Review this repository and summarize the main risks.
```

## Example: Obsidian Vault Task

```text
Goal:
Help Claude quickly assess whether this Obsidian vault automation will break links or metadata.

Success looks like:
Call out link, frontmatter, template, or base-view risks with concrete note paths.

Failure looks like:
Generic markdown advice that ignores Obsidian-specific behavior.

Return format:
Bullet list of risks plus a short verdict.

Relevant skills or domain hints:
Use obsidian-related skills. Pay attention to wikilinks, embeds, Bases files, and vault conventions.

Files to read first:
- AGENTS.md
- README.md
- vault/Templates/Daily Note.md
- vault/Bases/Projects.base
- scripts/sync_notes.py

Attached context:
- This repo is an Obsidian vault. Link integrity matters more than generic markdown style.

Task:
Review this repository and summarize the main risks.
```
