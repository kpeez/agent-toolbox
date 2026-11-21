# Delegation arm (KP-599)

This file is the pre-registration. It was written and committed before any scored run. A later edit
must say what changed and why.

## Question

After the two coordinator bullets in `swe-mode` `## Subagents`, does the lead agent make fewer
code edits in the root thread and spawn `daedalus` more often, without finishing fewer tasks?

## Design

- Two catalogs, same runner, same runtime, same cases.
  - **base**: `514b8bc`. It is `main` at `8f67ce4` plus the one runner commit that lets a runtime
    add the Agent tool. `git rev-parse 514b8bc:plugins` equals `git rev-parse 8f67ce4:plugins`, so
    the plugin content is the content of `main` at the branch point.
  - **head**: the PR head after this file and the metrics script are committed. Its `plugins/` tree
    holds the strip-model-names and coordinator-bullets changes. The head SHA is written in the
    result file under `artifacts/delegation-arm/2026-11-21/`.
- Runner: `claude plugin eval`, through `evals/skills/run_eval.py` with
  `evals/skills/runtime.delegation-arm.json`. Claude Opus 5.5, `CLAUDE_CODE_EFFORT_LEVEL=high`,
  Claude Code 2.1.330, the owner's subscription (cost is the API-equivalent figure the CLI reports).
- Tool set: Read, Write, Edit, Glob, Grep, Skill, and the Agent tool (named `Task` in the init
  event). There is no shell, in the root thread or in a subagent. The frozen hook-on arm is the
  only arm, because the session-start hook is how a user reaches `swe-mode`.
- Cases (12): `IM-01` to `IM-10`, `swe-mode-build-feature`, `swe-fallback-fix-bug`. Nine ask for a
  source edit. `IM-07` (diagnose only), `IM-08` (review only), and `IM-09` (test design only) forbid
  a source edit and act as controls.
- One run is one (case, SHA, repeat). Order is repeat by repeat, then case.

## Metrics

Each is computed per run by `evals/skills/delegation_metrics.py` from the kept transcript and
stream. A run with an API error, a runner error, or a session-check violation is excluded and
listed.

1. **Code edits in the root thread.** The count of `Edit`, `Write`, and `NotebookEdit` calls in the
   root transcript (not in a subagent transcript). Report the mean per run, and the share of runs
   with at least one.
2. **A `daedalus` spawn.** The share of runs with at least one root-thread Agent call whose
   `subagent_type` contains `daedalus`.
3. **Task done.** The result event is `success`, and the final working folder agrees with the
   case. For an edit case, at least one file other than `test_*` files and `README.md` differs from
   the fixture or is new. For a control case, no such file differs. This is a proxy: no run can
   execute tests, so it does not show that the change is correct.
4. **Total tokens.** The sum of input, output, cache-read, and cache-creation tokens across every
   model in the result event's `modelUsage`. That covers subagents. Report mean, median, and
   standard deviation, and total cost in USD.

Report each metric for all 12 cases, for the nine edit cases, and for the three controls. Rates
come with the count over the denominator and a Wilson 95% interval. The two SHAs are compared by
their counts and intervals. No significance claim is made from fewer than 10 runs per SHA.

## Budget and stop rules

- Spend cap for the arm: $40 API-equivalent, including the dry run. The dry run (`IM-01`, head
  catalog, one run) cost $1.04 and is not a scored run.
- Runs per case: chosen after the dry run. One run on `IM-01` cost $1.04, so one repeat of all 24
  (case, SHA) pairs is about $20 and a second repeat would pass the cap. The runner gets
  `--repeats 2` with a per-folder budget, and the repeat-major order leaves the SHAs within one run
  of each other when the budget stops it. Counts are reported as run, not as planned.
- Per-run stop: $2, the current `per_run_stop_usd` of the repository runner (the closed KP-598
  program raised it from $1 to $2). A run over the stop ends the batch.
- Runs go from a clean tree at each pinned SHA.

## Results (2026-11-21)

Runs: 12 cases x 2 repeats x 2 SHAs = 48 scored runs, all complete, none excluded, no stop. The
base SHA is `514b8bc` and the head SHA is `a536e03`. `plugins/` is identical at `a536e03` and at the
final PR head. The later commits change `evals/skills/delegation_metrics.py`, this file, and one
line of `evals/skills/run_eval.py`: the order of the tools in the generated `case.yaml`. The scored
runs used the earlier order (Read, Write, Edit, Glob, Grep, Skill, Task) and the final head writes
the six base tools first (Read, Glob, Grep, Skill, Write, Edit, Task). The tool set is the same.
Spend: $10.32 head,
$9.96 base, and $1.04 for the dry run, $21.32 of the $40 cap. Raw runs, `metrics.json`, and the
commands are in `artifacts/delegation-arm/2026-11-21/`.
The cost estimate above was high: the 48 scored runs cost $0.42 each on average, against $1.04 for the
`IM-01` dry run.

One scoring fix after the first look: the sandbox puts a `.git` folder in the working folder, and
the first version of `is_source` counted it as a changed source file. It marked the control cases
as not done. `.git` is now ignored. The fix came from a control-case count that made no sense, and
the other metrics did not change.

| Metric (24 runs per SHA) | base | head |
| --- | --- | --- |
| Root-thread edit calls per run, all cases | 1.25 | 1.12 |
| Root-thread edit calls per run, nine edit cases | 1.67 | 1.50 |
| Runs with a root-thread edit | 14/24, 0.58 [0.39, 0.76] | 14/24, 0.58 [0.39, 0.76] |
| Runs with a `daedalus` spawn | 18/24, 0.75 [0.55, 0.88] | 19/24, 0.79 [0.60, 0.91] |
| Task done (proxy) | 21/24, 0.88 [0.69, 0.96] | 22/24, 0.92 [0.74, 0.98] |
| Total tokens, mean (median, SD) | 241k (224k, 144k) | 262k (210k, 160k) |

Edit cases only (18 runs per SHA): a root-thread edit in 14 and 14, a `daedalus` spawn in 16 and 16,
task done in 16 and 16. Control cases (6 runs per SHA): no root-thread edit in either; a `daedalus`
spawn in 2 (base) and 3 (head); task done in 5 and 6.

Reading: the two SHAs are indistinguishable on these 12 cases. The base catalog already spawns
`daedalus` in 16 of 18 edit runs, which leaves little room for the bullets to move that rate. The
root thread still edits in 14 of 18 edit runs under both SHAs. Six cases differ by one or two
root-thread edits, in both directions (base to head, over two runs each): `IM-01` 12 to 10,
`IM-04` 5 to 3, `IM-06` 2 to 1, `IM-10` 3 to 2, `swe-mode-build-feature` 1 to 3, and
`swe-fallback-fix-bug` 1 to 2. The intervals overlap everywhere and each case has
two runs per SHA, so the data show no effect, not an effect of zero. The token difference is
inside one standard deviation. `IM-02` ended with no source change under both SHAs, in all four runs.
