---
name: validate-skills
description: Check the agent-toolbox skill set for drift — frontmatter name/directory match, README inventory parity, manifest version parity, and dead skill references. Use before publishing skill changes, or to audit the toolbox.
disable-model-invocation: true
---

# /validate-skills — drift guard

Run the checker and fix anything it reports. It is the single source of truth for
"the skill set is internally consistent" — wire it into CI and run it before any
PR that touches skills, the README skills table, or a plugin manifest.

```
uv run ${CLAUDE_SKILL_DIR}/scripts/validate_skills.py
```

It exits nonzero and prints one `FAIL:` line per issue. It checks:

1. **name ↔ directory** — every `SKILL.md` frontmatter `name:` equals its folder.
2. **README inventory parity** — the README skills table and the actual skill
   directories agree 1:1 (catches advertised-but-missing and missing-from-docs).
3. **Manifest version parity** — each plugin's `.claude-plugin` and `.codex-plugin`
   `plugin.json` carry the same version.
4. **Dead references** — no `SKILL.md`, README, or `AGENTS.md` mentions a
   `/<skill>` that doesn't exist (host commands are allowlisted in the script).

When it flags a dead reference to a skill you intend to keep, build the skill;
when the reference is obsolete, delete it. Don't silence a real failure by
expanding the allowlist — that is only for genuine host/harness commands.
