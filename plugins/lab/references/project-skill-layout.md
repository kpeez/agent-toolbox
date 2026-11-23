# Project skill layout

A skill that a lab skill generates for a project follows this layout.

## One folder per skill

- Put the skill in `.agents/skills/<skill-name>/` at the repository root.
  Never put it in `.claude/skills/`. Agents other than Claude Code read
  `.agents/skills/`, and many repositories ignore `.claude/`.
- Keep every file the skill needs in that folder: `SKILL.md`, small
  known-good inputs and their expected outputs, and runner scripts under
  `scripts/`. Make each script executable.
- Keep no files for the skill outside its folder, such as a top-level
  `checks/` or `pipeline-notes/` directory.
- Where `SKILL.md` names a file of the skill, in the frontmatter or the body,
  use a path relative to the skill folder: `scripts/check.py`, not
  `.agents/skills/<skill-name>/scripts/check.py`. A script finds its sibling
  files from its own location, not from the working directory.
- Commit the skill folder with the change that adds it, so every clone gets
  the skill. The link script below stages it.

## Claude Code sees it through a link

Claude Code reads project skills only from `.claude/skills/`. Give it each
skill through its own committed symlink,
`.claude/skills/<skill-name> -> ../../.agents/skills/<skill-name>`. A
committed link works on clone with no setup step. Do not commit a link for
the whole `.claude/skills` folder: when a teammate keeps a local, ignored
`.claude/skills/` directory, their next pull deletes it without a warning.

After you write the skill folder, run the link script. The script is
[`../scripts/link_project_skill.py`](../scripts/link_project_skill.py),
relative to this file. Build its absolute path from this file's folder, and
run it from inside the repository:

```sh
uv run <absolute path of link_project_skill.py> <skill-name>
```

The script stages the skill folder, makes the link, stages it with
`git add -f`, and checks that Git records it with mode `120000`. It also
handles these cases:

- A root `.gitignore` rule for the whole `.agents/` folder hides the skill:
  it rewrites the rule to `/.agents/*` and `!/.agents/skills/`.
- The repository commits a `.claude/skills` folder link that reaches the
  skill: it adds no link.
- An older version of this layout made an untracked `.claude/skills` link in
  a setup step: it removes that link.
- A real file or folder is at `.claude/skills/<skill-name>`: it refuses.

It is safe to run again. Read its exit code:

- `0`: commit the staged files with the skill. For each `note:` line that
  names an old setup line or ignore line, remove that line.
- `1`: stop and tell the user the `refused:` or `failed:` line. After
  `refused:`, the script changed nothing. After `failed:`, the changes it
  printed stay in place.
- `2`: run it inside the repository, with the name of a folder in
  `.agents/skills/` that holds a `SKILL.md`.

If the link later leaves the index, run the script again. `git add -A` does
not add it back when `.gitignore` covers `.claude/`.

## One repo-level command

When the skill runs a check, give the check one command at the repository
level: a `just` or `make` recipe in the file that the repository already
uses. The recipe runs the bundled script by its full path, for example:

```just
# run the known-good check of the fMRI statistics pipeline (add --null)
check-glm *flags:
    @uv run python .agents/skills/fmri-glm-stats/scripts/check.py {{flags}}
```

Name the command in `AGENTS.md` (or the repository's agent instructions
file), next to the other commands, and say which code or data changes need it.
An agent that does not load skills still finds the check there. In
`SKILL.md`, tell the agent to run that command.
