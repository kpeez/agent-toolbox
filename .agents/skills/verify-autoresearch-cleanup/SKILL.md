---
name: verify-autoresearch-cleanup
description: Kill the real autoresearch cleanup CLI (plugins/lab/skills/autoresearch/scripts/cleanup.py --apply) before each filesystem change it makes, under SIGKILL and SIGINT, and check that the original run stays recoverable and a rerun is safe. Use when a change touches cleanup.py (stage_lightweight, publish_lightweight, cleanup_run, write_archive, verify_archive) or the archive and retain steps in references/cleanup.md, or when the check fails.
paths:
  - plugins/lab/skills/autoresearch/scripts/cleanup.py
---

# Verify the autoresearch cleanup

## The rules

Each rule holds at every crash point:

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `OriginalRecoverable` | Every original entry, with its bytes, mode, and link target, is whole in the run folder, in `.<run>.cleanup-original`, or in the archive installed in the run folder. | A crash loses the only copy of a run. |
| `RerunSafe` | The same command run again either finishes with the three-entry layout, a matching archive, and no leftover folder, or refuses, names a leftover folder, and changes nothing. | A rerun hides or deletes what a crash left behind. |
| `InterruptNamesRecovery` | After a SIGINT that leaves `.<run>.cleanup-original`, stderr says `cleanup interrupted; inspect original recovery <path>`. | The user does not know where the original is. |

The staging archive and the trash do not count for `OriginalRecoverable`:
`references/cleanup.md` promises that the original stays whole until the
replacement is installed and verified.

## Run it

From the repository root:

```sh
uv run .agents/skills/verify-autoresearch-cleanup/scripts/check.py
```

It needs uv and `zstd`. It takes about 10 seconds. CI runs it in the
`autoresearch-cleanup-crash-check` job of `.github/workflows/checks.yml`. It
exits 0 only when each rule holds and each mutant breaks the rule it
targets. For a rule that breaks, it prints the signal, the crash point, and
why.

`--no-mutants` skips the mutants.

## How it works

This is not a model. Every run is `uv run --script cleanup.py RUN --apply
--acknowledge-stopped-run` on a fresh fixture run, with a fake `trash` on
`PATH` that moves the folder aside.

1. The check puts `scripts/crash_hook/` on `PYTHONPATH`. Its
   `sitecustomize.py` adds a Python audit hook to `cleanup.py` only. Each
   audit event that can change the filesystem (a write `open`, `os.rename`,
   `os.mkdir`, `os.chmod`, `shutil.copyfile`, `subprocess.Popen`, and the
   others in `MUTATIONS`) is one crash point. The hook prints each one.
2. A full run lists the crash points. The list comes from the process, so a
   new step in `cleanup.py` adds its crash points with no edit here.
3. For each crash point, and once after the last one, a new run stops just
   before that change: with SIGKILL, or with a real SIGINT that raises
   `KeyboardInterrupt`. The check reads the files with its own `zstd` and
   `tarfile` code, not with `cleanup.py`, and checks the rules.
4. The same command runs again, without the hook, and `RerunSafe` is checked.

The mutants in `MUTANTS` in `scripts/check.py` are text edits to a copy of
`cleanup.py`. Each one must break its rule:

- `trash-before-install` trashes the recovery folder before it installs the
  replacement. It breaks `OriginalRecoverable`.
- `ignore-unfinished-cleanup` removes the refusal when a leftover folder
  exists. It breaks `RerunSafe`.
- `silent-interrupt` drops the recovery path from the interrupt message. It
  breaks `InterruptNamesRecovery`.

A mutant whose text no longer matches `cleanup.py` stops the check with a
message. Update its text in the same change.

Bounds: one fixture run with regular files, a nested folder, a hidden file,
an executable file, and a symlink to a file outside the run. Not covered:
a crash while the `zstd` child writes the archive (the parent makes no
audit event then), a crash during the rerun, concurrent writers, and
`ledger.py`. The unit tests in `scripts/tests/test_cleanup.py` cover the
refusals before `--apply` changes anything, corrupt and changed archives,
and a source that changes during cleanup.

Coverage: `cleanup_run`, `stage_lightweight`, `write_archive`,
`verify_archive`, `publish_lightweight`, and `validate_retained_layout` in
`plugins/lab/skills/autoresearch/scripts/cleanup.py`.

Sync commit: the commit that adds this skill. At that commit the check
describes the code.

## When a change touches the covered code

1. Run the check before and after the change.
2. A rule that breaks: the output names the signal and the crash point.
   Copy a run into a scratch folder and replay that crash point:
   `env PYTHONPATH=.agents/skills/verify-autoresearch-cleanup/scripts/crash_hook CLEANUP_CRASH_AT=<index> CLEANUP_CRASH_SIGNAL=KILL uv run plugins/lab/skills/autoresearch/scripts/cleanup.py <scratch run> --apply --acknowledge-stopped-run`
   (`INT` for SIGINT). Look at the files it leaves. When the original is
   lost or the rerun is unsafe, it is a bug in the change.
3. When the protocol in `references/cleanup.md` changed on purpose, update
   the rule above, its sentence in `references/cleanup.md`, and
   `scripts/check.py` in the same change. Never weaken a rule or remove a
   mutant only to make the check pass.
4. A new kind of filesystem change that the hook does not see, such as a new
   audit event: add it to `MUTATIONS` in `scripts/crash_hook/sitecustomize.py`.
5. After you confirm the check describes the code, set the sync commit above
   to the commit you checked.
