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
