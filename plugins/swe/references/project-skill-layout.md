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

Claude Code reads project skills only from `.claude/skills/`. Give it the
skill through the symlink `.claude/skills -> ../.agents/skills`. The
repository's setup step creates the link. Commit the skill folder, but do
not commit the link.

- Add one line to the setup step that the repository already has, such as
  `just install` or `make install`:

  ```bash
  mkdir -p .claude && if [ -L .claude/skills ] || [ ! -e .claude/skills ]; then ln -sfn ../.agents/skills .claude/skills; else echo ".claude/skills is a real directory; link .agents/skills into it by hand"; fi
  ```

  The line is safe to run again. It replaces only a link, and it never
  overwrites a real `.claude/skills` directory.
- Make sure Git ignores the link. When `.gitignore` covers neither `.claude/`
  nor `.claude/skills`, add `/.claude/skills`.
- When `.claude/skills` is already a real directory with committed skills,
  do not replace it. Link the one skill folder instead
  (`ln -sfn ../../.agents/skills/<skill-name> .claude/skills/<skill-name>`),
  and tell the user.
- Run the setup step once, and confirm that `.claude/skills/<skill-name>/SKILL.md`
  resolves.

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
