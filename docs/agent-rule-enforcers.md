# Agent rule enforcers

This table pairs each rule that stops a repeated agent mistake with what
enforces it. The `correct` skill in `plugins/swe` maintains it. Each row names
the past mistakes, the enforcer's path, and the command that runs it.

| Rule | Past mistakes | Level | Enforcer | Command |
|---|---|---|---|---|
| A plugin never names another plugin's skill, agent, or playbook | swe `hillclimb-metric` handed its loop to `lab:autoresearch`; swe `testing-code`, `swe-mode`, and `figure-it-out` named `lab:autoresearch`; lab `making-plots` named `swe:testing-code`; the shared `go-deeper` used swe's `interview-user` "when it is installed" | check | `.github/scripts/plugin_isolation.py`, run by `.github/workflows/shared-skills.yml` | `python3 .github/scripts/plugin_isolation.py` |
| A PR body is the filled `ship-pr` template and never names the requester or the chat | `## Why` sections and requester attribution in #207, #212, and PRs in other repos | architecture + check | `plugins/swe/skills/ship-pr/scripts/pr_body.py` (`render` builds the body from `templates/pr-body.md`), the swe `PreToolUse` hook in `plugins/swe/hooks/hooks.json`, and `.github/workflows/attribution.yml` | `python3 plugins/swe/skills/ship-pr/scripts/pr_body.py check body.md` |
