# Agent rule enforcers

This table pairs each rule that stops a repeated agent mistake with what
enforces it. The `correct` skill in `plugins/swe` maintains it. Each row names
the past mistakes, the enforcer's path, and the command that runs it.

| Rule | Past mistakes | Level | Enforcer | Command |
|---|---|---|---|---|
| A plugin never names another plugin's skill, agent, or playbook | swe `hillclimb-metric` handed its loop to `lab:autoresearch`; swe `testing-code`, `swe-mode`, and `figure-it-out` named `lab:autoresearch`; lab `making-plots` named `swe:testing-code`; the shared `go-deeper` used swe's `interview-user` "when it is installed" | check | `.github/scripts/plugin_isolation.py`, run by `.github/workflows/shared-skills.yml` | `python3 .github/scripts/plugin_isolation.py` |
| A PR body is the filled `ship-pr` template and never names the requester or the chat | `## Why` sections and requester attribution in #207, #212, and PRs in other repos | architecture + check | `plugins/swe/skills/ship-pr/scripts/pr_body.py` (`render` builds the body from `templates/pr-body.md`), the swe `PreToolUse` hook in `plugins/swe/hooks/hooks.json`, and `.github/workflows/attribution.yml` | `python3 plugins/swe/skills/ship-pr/scripts/pr_body.py check body.md` |
| Dependent PRs in a `gh-stack` repo publish with `gh stack link` or `gh stack submit`, not hand-chained `gh pr create --base` | 30 dependent PRs opened with hand-set `--base` and no `gh stack link`, leaving GitHub without a stack | check | `plugins/swe/skills/ship-pr/scripts/pr_body.py` (`hook`), run by the swe `PreToolUse` hook in `plugins/swe/hooks/hooks.json` | `python3 -m unittest discover -s plugins/swe/skills/ship-pr/scripts/tests -v` |
| The eval facet map matches the skill sources, so the evals see each workflow change | the swe router (#157, now `swe-mode`) landed with no `swe-mode` eval case; `lab-mode` (#222) landed with cases that check only the router load | check | `evals/skills/facets.py`, run by `.github/workflows/shared-skills.yml` | `python3 evals/skills/facets.py check` (fix with `write`) |
