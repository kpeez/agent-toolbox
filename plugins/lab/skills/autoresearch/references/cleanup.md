# Clean up a completed run

Use this workflow for `/autoresearch cleanup [run-directory]`. Resolve the
exact run and the user's authorization to apply cleanup. Inspect-only requests
stay read-only. Do not start evaluations, change experiment decisions, or
discard branches as part of cleanup.

## Recover the evidence first

Inspect the run, its original worktree and Git history, and the relevant agent
sessions. Use session identities, timestamps, commands, commits, and output
paths to establish which records belong to this run. Corroborate session claims
with ledgers, evaluator outputs, logs, configurations, and checkpoints. If a
material source cannot be recovered, identify the gap and ask the user for that
source before archiving. Do not turn missing evidence into an inferred result.

Before invoking the cleanup helper, ensure these regular, nonempty files exist
at the run root:

- `program.md`: a byte-for-byte copy of the original program actually used.
  Recover it from the original file, a recorded Git revision, or an exact
  session snapshot. Record its source and SHA-256 in the summary. A current
  generic program, a rewritten retrospective, and the skill's historical
  example are not substitutes. Preserve conflicting existing files and resolve
  their provenance. If the approved program changed during the run, retain
  each evidenced version with its applicable attempts, keeping the original
  at `program.md`.
- `EXPERIMENT_SUMMARY.md`: summarize the question, experimental design,
  hypotheses, objective and direction, evaluator/data identity, budgets,
  controls, seeds/replication, changes tested, methods, and measured results.
  Explain the comparable baseline, kept/discarded/crashed attempts, stopping
  reason, limitations, and any remaining uncertainty. Cite the relevant
  sessions and artifact paths/record IDs for claims. Distinguish training,
  screening, and final evaluations. Do not claim a significance test or a
  replication statistic that was not performed. Retain the relevant evidence
  inside the run, with provenance, when it otherwise exists only outside it.
- `autoresearch-run.png`: the current progress plot of the actual optimized
  metric, produced with the shared `scripts/plot_trials.py` according to
  [progress plotting](trial-plots.md). Reuse or copy an existing accurate plot
  and summary instead of needlessly deriving them again. Check their sources
  and coverage; an older or unrelated PNG is not sufficient. Inspect the PNG.

The helper validates files and archive bytes; it cannot establish scientific
provenance. Complete this evidence review before using it.

## Legacy runs and plotting

Keep original directory names and records, including names such as
`baseline-s0-seed0_*`, `e10-imgsz960-*`, `ref100-*`, and `smoke-*`. Do not require
modern `expNNN-slug` names and do not sort attempt chronology lexically.

When there is no compatible ledger, prepare a separate run-local plotting
input directory containing `results.jsonl` and `trial-plot.json`. Preserve the
original records. Map observed candidate attempts into the renderer's schema
with increasing numeric IDs, original descriptions, evidenced decisions and
objective values. Retain the source-to-row mapping and any extraction script
inside the run. Establish chronology and keep/discard decisions from the
sessions and logs; directory names or the highest measured value do not prove
those decisions. Do not invent commits, statuses, measurements, or omitted
attempts. The renderer accepts legacy descriptions unchanged.

Use only comparable attempts for the approved objective. Keep seed replicates,
smoke tests, calibration, and longer-budget reference runs distinct unless the
original program explicitly defines their aggregation or comparability. Name
any supported aggregation and unit of replication in the label/scope. Document
excluded runs and reasons in the summary. A different metric with more complete
data is not a replacement for the optimized metric.

Validate and render through the shared renderer, for example:

```bash
python3 <skill-dir>/scripts/plot_trials.py <plot-input-dir> --validate
uv run <skill-dir>/scripts/plot_trials.py <plot-input-dir> --out <run-directory>/autoresearch-run.png
```

If the objective, chronology, decisions, or comparable measurements cannot be
recovered sufficiently to draw an honest progress plot, report exactly what is
missing and ask how to resolve it. Leave the full run in place. Do not fabricate
a placeholder plot to pass the helper's file check.

## Archive and retain

Confirm the run has stopped, including remote workers, queued jobs, and writers
with open files. Inspect the relevant process/job state on the host that owns
the run. A quiet directory alone is not proof that a sleeping job has ended.
Do not stop jobs merely to make cleanup succeed. Reconcile incomplete attempts
using [interrupted-run reconciliation](resume-reconciliation.md).

The final run directory contains exactly:

```text
<run-directory>/
  <run-directory-name>_archive.tar.zst
  autoresearch-run.png
  EXPERIMENT_SUMMARY.md
```

The compressed tar contains the entire prepared original run, including
`program.md`, summary, plot, hidden files, and retained provenance. Symlinks are
archived as links, never followed; external target contents are not included.
Identify external dependencies before cleanup and copy required evidence into
the run explicitly within the authorized scope. Never recursively dereference
unknown links. Inspect restore destinations and link targets before extracting
an archive.

Use `scripts/cleanup.py` for archive mechanics:

```bash
python3 <skill-dir>/scripts/cleanup.py <run-directory>
python3 <skill-dir>/scripts/cleanup.py <run-directory> --apply --acknowledge-stopped-run
```

The first command inspects readiness without changing the run. Use the second
only after the evidence review and stopped-run checks above. Read `--help` for
additional active-marker checks. Readiness checks require Python 3, `zstd`, and
recoverable `trash` or `trash-put`, just as apply does. Missing tools or
insufficient space block cleanup without a permanent deletion fallback. Use
the explicit `_archive.tar.zst` naming convention.

Do not bypass a changing-run check, existing archive, verification failure, or
interrupted cleanup. Preserve staged data and originals until their state is
understood. The helper exclusively creates the sibling
`.<run-directory-name>.cleanup-staging`, verifies compressed integrity, tar
membership, file hashes, permissions, and link targets against the source,
then renames the whole original to `.<run-directory-name>.cleanup-original`.
It checks that original again, installs the three-file replacement, verifies
it, and only then sends the exact original directory to Trash. Renaming does
not stop writers with open files; the stopped-run precondition still applies.
Either sibling remaining blocks another cleanup. On failure, inspect the
reported paths; do not automatically remove them or restart. Never use a
wildcard or `rm` to complete the destructive phase.

After success, verify the three-file layout and report the archive path and
verification result. Summary and plot stay byte-identical outside the archive;
the original program and full contents remain recoverable inside it. Moving
originals to Trash is recoverable and may not immediately free disk space. Do
not empty Trash as part of this workflow.

A repeat invocation verifies compressed integrity, tar structure, required
members, and matching retained files, then reports `already-clean` without
mutation. The complete source comparison happens before the first retirement;
once originals are absent, repeat verification cannot re-establish their full
membership independently of the archive.
