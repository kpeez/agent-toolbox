# Project skill layout

A skill that a swe skill generates for a project follows this layout.

## One folder per skill

- Put the skill in `.agents/skills/<skill-name>/` at the repository root.
  Never put it in `.claude/skills/`. Agents other than Claude Code read
  `.agents/skills/`, and many repositories ignore `.claude/`.
- Keep every file the skill needs in that folder: `SKILL.md`, model, proof,
  or data files (for example `<Name>.tla`), and runner scripts under
  `scripts/`. Make each script executable.
- Keep no files for the skill outside its folder, such as a top-level
  `formal/` or `verify/` directory.
- Where `SKILL.md` names a file of the skill, in the frontmatter or the body,
  use a path relative to the skill folder: `scripts/check.py`, not
  `.agents/skills/<skill-name>/scripts/check.py`. A script finds its sibling
  files from its own location, not from the working directory.
- Commit the skill folder with the change that adds it, so every clone gets
  the skill. Many repositories ignore parts of `.agents/` (for example
  `.agents/docs/` or `.agents/plans/`). Before you commit, run
  `git check-ignore -v .agents/skills/<skill-name>/SKILL.md`. When it prints a
  rule, change `.gitignore` so it ignores only those other parts. Git cannot
  re-include a file under an ignored directory, so `!/.agents/skills/` after
  `.agents/` has no effect. Write `/.agents/*` and then `!/.agents/skills/`
  instead. Then confirm that
  `git ls-files .agents/skills/<skill-name>` lists every file of the skill.

## Claude Code sees it through a link

Claude Code reads project skills only from `.claude/skills/`. Give it each
skill through its own committed symlink,
`.claude/skills/<skill-name> -> ../../.agents/skills/<skill-name>`. A
committed link works on clone with no setup step. Do not commit a link for
the whole `.claude/skills` folder: when a teammate keeps a local, ignored
`.claude/skills/` directory, their next pull deletes it without a warning.

- When `git ls-files -s .claude/skills` already lists `.claude/skills`
  itself with mode `120000`, the repository commits a folder link. When
  `.claude/skills/<skill-name>/SKILL.md` resolves through it, add nothing,
  and skip the rest of this list. When it does not resolve, stop: tell the
  user that the folder link does not reach the skill, and do not change it.
- When `.claude/skills` is a link that Git does not track
  (`[ -L .claude/skills ]` and `git ls-files .claude/skills` prints
  nothing), an older version of this layout made it in a setup step. Delete
  the link with `rm .claude/skills`, and remove the setup-step line that made
  it. Leave `.gitignore` as it is.
- When the setup step has a line that links this one skill
  (`ln -sfn ../../.agents/skills/<skill-name> .claude/skills/<skill-name>`),
  an older version of this layout added it with the ignore line
  `/.claude/skills/<skill-name>`. Remove both lines.
- When `.claude/skills/<skill-name>` is a real directory, stop. `ln -sfn`
  would put the link inside it. Tell the user that the directory hides the
  skill, and do not move or delete it.
- Otherwise, link the skill:
  `mkdir -p .claude/skills && ln -sfn ../../.agents/skills/<skill-name> .claude/skills/<skill-name>`.
- Then commit the link with `git add -f .claude/skills/<skill-name>`. The `-f`
  adds it even when `.gitignore` covers `.claude/`. Git applies no ignore
  rule to a tracked path, so do not edit `.gitignore` for the link. If the
  link later leaves the index, add it again with `git add -f`;
  `git add -A` does not.
- Confirm that `git ls-files -s .claude/skills` shows the link with mode
  `120000`, and that `.claude/skills/<skill-name>/SKILL.md` resolves.

## One repo-level command

When the skill runs a check, give the check one command at the repository
level: a `just` or `make` recipe in the file that the repository already
uses. The recipe runs the bundled script by its full path, for example:

```just
# model-check the training resume (TLA+; add --mutants)
verify-resume *flags:
    @uv run python .agents/skills/verify-training-resume/scripts/check.py {{flags}}
```

Name the command in `AGENTS.md` (or the repository's agent instructions
file), next to the other commands, and say which code changes need it. An
agent that does not load skills still finds the check there. In `SKILL.md`,
tell the agent to run that command.
