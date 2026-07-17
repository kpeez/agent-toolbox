---
name: setup-llmos
description: Diagnose whether a machine can use the llmOS vault through Obsidian CLI and qmd, and configure the vault root when it is missing. Use when setting up llmOS, checking provider prerequisites, repairing vault access, or verifying that the canonical llmos qmd collection is correctly rooted and can return complete notes.
---

# Setup llmOS

Use this workflow on macOS or Linux, the supported llmOS desktop environments.
The doctor detects the OS and prints platform-specific repairs.

Resolve `<llmos-plugin-root>` as the directory two levels above this
`SKILL.md` (its `scripts/` holds `doctor.sh`, `vault_root.py`, and this
skill's `write_config.py` lives alongside it under `skills/setup-llmos/`).

Run the bundled doctor before changing the machine:

```sh
bash "<llmos-plugin-root>/scripts/doctor.sh"
```

The doctor is read-only. It reports `PASS` or `FAIL` for each available
prerequisite, prints an exact `REPAIR` command after every failure, and exits
nonzero when setup is incomplete.

## Workflow

1. **Run the doctor.** Treat the result as healthy only when the command
   exits `0`; binary presence alone is insufficient.
2. **If `vault-root` fails**, the machine has no `$LLMOS_ROOT` and no
   `~/.config/llmos/config.json`. Ask the user for the absolute path to their
   llmOS vault checkout, then write the config:

   ```sh
   python3 "<llmos-plugin-root>/skills/setup-llmos/scripts/write_config.py" "<path the user gave>"
   ```

   The script validates the path before writing anything — it must exist and
   contain both `.obsidian/` and `AGENTS.md`. It never writes a config
   pointing at a non-vault; on a rejected path it exits nonzero with the
   reason and writes nothing, so re-ask the user and retry rather than
   guessing or falling back to a nearby directory.
3. **Rerun the doctor** to confirm `vault-root` now passes.
4. **Review every remaining failure's `REPAIR` command** with the user.
   Obtain authorization before running commands that install software, open
   applications, or change qmd collections.
5. **Apply only authorized repairs**, then rerun the doctor until every check
   passes.

## Platform notes

The `obsidian-vault` check needs Obsidian already running with the `llmOS`
vault open and its command line interface enabled (Settings → General →
Advanced → Command line interface).

- **macOS** ships the `obsidian-cli` binary inside the app bundle; the repair
  symlinks it onto `PATH`.
- **Linux** exposes the CLI as `obsidian`; the repair installs the snap and
  writes an `obsidian-cli` shim to `~/.local/bin` that execs `obsidian`. Run
  the doctor from within the desktop session so `DISPLAY`/`WAYLAND_DISPLAY`
  and the session D-Bus address are set; otherwise the CLI cannot reach the
  running app.
