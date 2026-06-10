# Issue tracker: Local Markdown

Issues for this repo live as markdown files under `specs/` (private, gitignored —
never committed).

## Conventions

- One feature per directory: `specs/<feature>/` (the same directory that holds
  `SPEC.md` and `examples/`)
- Implementation issues are `specs/<feature>/issues/<NN>-<slug>.md`, numbered from `01`
- The parent issue is the spec itself — `SPEC.md`'s goal/scope header; do not
  duplicate it as an issue file
- Triage state is a `Status:` line near the top of each issue file, using the
  triage label strings from `SKILL.md`; done is `Status: done`
- "Blocked by" references other issue files by relative path
- Comments and progress notes append to the bottom of the file under a
  `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `specs/<feature>/issues/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the
issue number directly.
