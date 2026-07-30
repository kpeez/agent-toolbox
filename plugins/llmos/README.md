# llmos plugin

Tooling for the shared **llmOS Obsidian vault** — the durable knowledge base
agent sessions read from and write to across machines. The plugin bundles
three skills, a set of lifecycle hooks that keep vault writes well-formed and
indexed, and `llmos_vault`, a Python library with a `llmos-vault` CLI that
gives agents deterministic verbs against the vault instead of hand-rolled
file operations.

## Contents

```text
plugins/llmos/
├── skills/
│   ├── maintain-llmos/    # vault conventions and maintenance workflows
│   ├── setup-llmos/       # machine access diagnosis + vault-root config
│   └── vault-cli/         # routing table for the llmos-vault CLI
├── hooks/                 # session/tool lifecycle hooks (see below)
├── llmos_vault/           # Python library + `llmos-vault` cyclopts CLI
├── scripts/               # audit, doctor, daily-activity utilities
└── tests/                 # pytest suite with fixture vaults
```

## Skills

| Skill            | What it does                                                                                                  |
| ---------------- | ------------------------------------------------------------------------------------------------------------- |
| `maintain-llmos` | Maintains the vault through its conventions: filing durable knowledge, project docs, reviews, link/property repair |
| `setup-llmos`    | Diagnoses whether a machine can use the vault (Obsidian CLI, `qmd`), and configures the vault root when missing |
| `vault-cli`      | Routes deterministic vault operations — read, list, move, link, file, daily notes, health — to the `llmos-vault` CLI |

## Hooks

`hooks/hooks.json` wires four lifecycle events. One script per concern, and
the same scripts serve both Claude and Codex — each `hooks.json` entry names
its event on the command line, and the JSON payload arrives on stdin the same
way on both harnesses.

| Event                  | Script                | Purpose                                                                                                     |
| ---------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------- |
| SessionStart           | `llmos_hook.py`       | Injects vault context at session start (startup, resume, clear, compact)                                    |
| PreToolUse (Write/Edit)| `llmos_hook.py`       | Gates direct writes into the vault so they follow its conventions                                           |
| PreToolUse (Bash)      | `guard_bash.py`       | Guards `obsidian-cli` targeting and vault-unsafe `mv`/`rm`; a cheap pre-filter keeps the fast path silent   |
| PostToolUse (Write/Edit)| `llmos_stamp_hook.py`| Normalizes frontmatter, stamps `updated`, appends the writing provider to `authors`, flags the index dirty  |
| Stop                   | `llmos_qmd_hook.py`   | Reindexes the `qmd` llmos collection **iff** this turn dirtied the vault; a vault-untouched turn spawns nothing |

The stamp and reindex hooks share a session-scoped dirty flag
(`llmos_dirty_flag.py`), so concurrent sessions never collide or leak a stale
flag into each other.

## The `llmos_vault` library and CLI

`llmos_vault/` is a Python package (see `pyproject.toml`) exposing the
`llmos-vault` CLI. Every command is a thin wrapper: resolve `--vault` to a
root path, call a framework-free function, print JSON — so agents get
predictable, parseable output for reads, listings, moves, links, daily notes,
inbox filing, graph neighbors, and vault health checks. Command help renders
straight from docstrings; `skills/vault-cli/references/commands.md` is the
routing table skills use to pick the right verb.

Vault-root resolution lives in `llmos_vault/root.py` and is shared by the
hooks, the CLI, and the setup skill, so every entry point agrees on where the
vault is.

## Scripts

- **`scripts/doctor.sh`** — end-to-end health check: is the vault root valid,
  are the CLI and `qmd` reachable, is the collection indexed.
- **`scripts/audit_metadata.py`** — audits frontmatter contracts across the
  vault; read-only unless `--fix` is passed.
- **`scripts/write_daily_activity.py`** — writes the machine-owned
  `## Projects` block of daily notes from GitHub activity. Deterministic
  script, not an agent: fetch → hash → one model call → verify → write.
- **`scripts/vault_root.py`** — back-compat shim over `llmos_vault.root` for
  callers that import by file path.

## Tests

`tests/` is a pytest suite run from the plugin directory (`uv run pytest`),
covering the hooks (gating, guards, stamp format, reindex), root resolution,
the CLI's backends, and vault health — against committed fixture vaults in
`tests/fixtures/`.
