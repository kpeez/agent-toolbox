---
name: verify-project-skill-link
description: Run the project-skill link script (link_project_skill.py in plugins/swe/scripts and plugins/lab/scripts) end to end in throwaway Git repositories, and check a fresh clone and a teammate's pull. Use when a change touches that script or the link steps in a project-skill-layout.md, or when the check fails.
paths:
  - plugins/swe/scripts/link_project_skill.py
  - plugins/lab/scripts/link_project_skill.py
  - plugins/swe/references/project-skill-layout.md
  - plugins/lab/references/project-skill-layout.md
---

# Verify the project-skill link script

## Run it

From the repository root:

```sh
uv run .agents/skills/verify-project-skill-link/scripts/check.py
```

It needs uv and Git, works offline, and takes about 10 seconds. It isolates
Git from your global and system config. CI runs it in the
`project-skill-link` job of `.github/workflows/checks.yml`, which also fails
when the swe and lab copies of the script differ.

Options:

- `--script <path>`: run another link script, such as a stand-in for the
  steps an older layout gave. Default: the swe copy.
- `<scenario> ...`: run only the named scenarios.

It prints `PASS <scenario>` or `FAIL <scenario>: <check>, ...` for each
scenario, and exits 0 only when all pass.

## What a scenario does

Each scenario in `SCENARIOS` of `scripts/check.py` builds a repository with
a remote and an ignore setup, and a teammate clone. The teammate keeps a
personal skill in `.claude/skills/personal/`. Then the scenario writes the
skill `.agents/skills/demo`, runs the script, and checks:

| Check | Fails when |
| --- | --- |
| `exits-0` or `exits-1` | the exit code is not the one the scenario expects |
| `refusal-leaves-repo-unchanged` | a refusal changed a file, a link, or the index |
| `second-run-changes-nothing` | a second run fails or changes the repository |
| `no-stray-link-in-skill-folder` | a link landed inside the skill folder, as `ln -sf` without `-n` does |
| `commit-holds-the-skill` | after `git add -A` and a commit, a fresh clone has no skill files |
| `fresh-clone-lists-the-skill` | in a fresh clone, `.claude/skills/demo/SKILL.md` does not resolve, or Git does not record the link with mode `120000` |
| `team-skill-still-tracked` | a committed team skill in `.claude/skills/` left Git |
| `teammate-pull-succeeds`, `teammate-keeps-personal-skill`, `teammate-lists-the-skill` | the teammate's pull fails, deletes their personal skill, or does not give them the skill |

## When a check fails

1. Run the one scenario again, and build its repository by hand in a
   scratch folder to see the state.
2. Fix the script, not the check. Never remove a scenario or a check only to
   make the run pass.
3. When the expected behavior changes on purpose, change the scenario, the
   script, and the "Claude Code sees it through a link" section of both
   `project-skill-layout.md` files in the same change.
