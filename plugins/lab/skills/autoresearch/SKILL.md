---
name: autoresearch
description: Run an autonomous experiment loop for open-ended engineering or research work with a defined endpoint. Use when the user asks Codex to autoresearch, explore alternatives, improve toward a target metric, run repeated experiments, or compare outcomes. The skill coauthors an approved immutable program, isolates changes in a worktree, freezes the evaluator, records a baseline and append-only ledger, and keeps only verified improvements within explicit budgets.
---

# Autoresearch

Run a bounded experiment loop: approve the rules, freeze the evaluator, measure
a baseline, test one committed hypothesis at a time, and preserve enough
evidence to reproduce every decision. This is a portable workflow, not an
experiment framework or provider integration.

## Approval gates

Do not create artifacts, create a worktree, run commands that may write, or
change code on implied consent.

1. Inspect the repository and proposed evaluator read-only. Coauthor a draft
   `program.md` in chat, including the setup actions and permission boundary.
2. Ask the user to approve setup. Only after explicit approval, create the
   private artifact directory and dedicated worktree, hash the evaluator, and
   run the baseline within the approved setup boundary.
3. Put the measured baseline and all final run boundaries into `program.md` and
   show the exact file to the user. Ask for explicit run approval.
4. After approval, compute the program SHA-256, record it in the group
   `README.md`, and make no candidate mutation until both the program and
   evaluator hashes match their approved values.

Approval covers only the written program. Changed requirements, evaluator,
metric parser, protected data, mutable paths, budgets, thresholds, or stop
conditions end the run and require a new program and approval. Never edit an
approved `program.md` in place.

## Private isolated run

Before setup, inspect the current branch, base commit, and working tree. Refuse
to overwrite or incorporate unrelated user changes.

- Use a URL-safe group name such as `api-latency` and a branch named
  `autoresearch/<group>`.
- Create a dedicated sibling worktree for the branch. If an isolated worktree
  or the approved sandbox/permission boundary is unavailable, stop.
- Use the user's artifacts root when specified; otherwise use the absolute path
  to `.autoresearch/` in the primary repository. The default is gitignored and
  private. Do not commit run artifacts unless the user explicitly changes that
  boundary in a newly approved program.
- Run every candidate in the dedicated worktree. Resolve and record the
  absolute worktree and artifact paths before any destructive rollback.

Create this structure after setup approval:

```text
<artifacts-root>/<group>/
├── program.md
├── README.md
├── results.tsv
└── YYYY_MM_DD-expt-<NN>-<slug>/
    ├── README.md
    ├── LOG.md
    ├── logs/
    └── scripts/
```

Use monotonically increasing two-digit experiment numbers;
`YYYY_MM_DD-expt-00-baseline` is first. The group `README.md` records the
program hash, worktree, branch, current best commit and metric, consumed
budgets, terminal state, and concise experiment summary. It may change during
the run; `program.md` may not.

## The frozen program

The final `program.md` is complete only when it records all of these fields:

- problem statement and desired outcome;
- baseline commit, evaluator result, primary metric, and guardrail results;
- primary metric direction (`maximize` or `minimize`);
- guardrail names, limits, and comparison rules;
- evaluator command, machine-readable output contract, protected evaluator and
  data paths, exact hash algorithm/command, and aggregate evaluator SHA-256;
- exact mutable paths and forbidden paths;
- per-evaluation timeout and compute/cost limits;
- total candidate-count, evaluator-time, and compute/cost budgets, with units;
- minimum meaningful improvement or deterministic retest rule;
- acceptance threshold;
- keep, discard, inconclusive, crash, timeout, evaluator-tamper, and rollback
  rules;
- stop conditions, including threshold, budget, repeated failure/no-progress,
  evaluator/environment invalidity, guardrail, and safety stops;
- approved sandbox, network, dependency, credential, and external-action
  boundaries;
- environment identity, dependency lock, seeds, and other reproducibility
  inputs the evaluator needs;
- the ledger header and artifact-record format below.

Record that contract with these exact nonempty labels so it can be validated:

```text
Problem:
Desired outcome:
Baseline commit:
Baseline result:
Primary metric:
Metric direction: maximize | minimize
Guardrails:
Evaluator command:
Evaluator output contract:
Protected paths:
Evaluator hash command:
Evaluator SHA-256:
Mutable paths:
Forbidden paths:
Per-evaluation timeout seconds:
Per-evaluation compute cost limit:
Candidate budget:
Evaluator-time budget seconds:
Compute-cost budget:
Meaningful improvement or retest rule:
Acceptance threshold:
Keep rule:
Discard rule:
Inconclusive rule:
Crash rule:
Timeout rule:
Evaluator-tamper rule:
Rollback rule:
Stop conditions:
Approval record:
Sandbox/network/dependency/credential boundaries:
Environment identity:
Dependency lock:
Seeds:
Ledger header:
Artifact record format:
```

The evaluator output contract must be machine-readable and include both the
primary metric and every guardrail result; ledger and experiment records come
from that parsed output rather than coordinator-supplied values.

List protected paths relative to the worktree, separated by semicolons. The
aggregate evaluator digest is SHA-256 over the bytewise-sorted records
`<relative-path><TAB><file-sha256><LF>`.

Hash every protected evaluator/parser/data file before baseline evaluation.
Define the aggregate deterministically as the SHA-256 of the bytewise-sorted
relative path plus file-SHA-256 pairs, and record the exact commands used. Hash
again after baseline, before and after every candidate evaluation, and on
resume. The evaluator's output—not the agent's judgment—is the measurement.

If the evaluator hash differs at any check, do not accept its result. Capture
the mismatch, mark the attempt `evaluator_tamper` and `inconclusive`, restore
the dedicated worktree to the last verified best commit under the approved
rollback policy, verify restoration, and stop. An evaluator change requires a
new approved program even when the change seems beneficial.

## Baseline and ledger

Run the frozen evaluator on the baseline commit before any candidate. Save its
command, environment identity, start/end time, exit status, stdout, stderr,
parsed primary metric, guardrails, evaluator hashes, and budget consumed in
`00-baseline/`. The evaluator must finish successfully with valid output and
passing guardrails. Otherwise stop without starting the loop.

Create `results.tsv` once with this exact header (literal tab separators):

```text
experiment	commit	evaluator_sha256	primary_metric	guardrails	outcome	decision	elapsed_seconds	artifact_dir	summary
```

Append the baseline row first, with `outcome=completed` and
`decision=baseline`. Then follow these rules:

- append exactly one physical row for every attempted committed candidate;
- never rewrite, truncate, reorder, or delete the header or existing rows;
- replace tabs, carriage returns, and newlines inside values with spaces;
- serialize guardrails in program order as `name=value;name=value`; use `NA`
  for an unavailable metric;
- use the full commit hash, approved evaluator hash, experiment-relative
  artifact path, and elapsed evaluator seconds on every row;
- set outcome to `completed`, `invalid`, `crash`, `timeout`, or
  `evaluator_tamper`, and decision to `keep`, `discard`, or `inconclusive` for
  every candidate;
- append only after the detailed record and logs are durable, then verify the
  row has exactly ten tab-separated fields and references an existing commit
  and artifact directory.

Detailed evidence, not the TSV, holds multiline output and complex results.
Each experiment `README.md` records the falsifiable hypothesis, planned
smallest change, parent best commit, candidate commit, evaluator hash, primary
and guardrail results, budget used, decision and reason, and rollback proof.
`LOG.md` records timestamped commands and exit statuses; `logs/` and `scripts/`
retain raw outputs and exact one-off evaluation helpers.

Use these exact nonempty experiment `README.md` labels: `Hypothesis`, `Planned
change`, `Parent best commit`, `Candidate commit`, `Evaluator SHA-256`, `Primary
metric`, `Guardrails`, `Outcome`, `Elapsed seconds`, `Compute cost`, `Decision`,
`Decision reason`, and `Rollback proof`. Baseline-only fields use `N/A`. Every
ledger artifact directory must also contain a nonempty `LOG.md` and the `logs/`
and `scripts/` directories.

## Candidate loop

Start each iteration from the verified best commit with a clean dedicated
worktree.

1. Verify the program hash, evaluator hash, branch, best commit, ledger shape,
   artifact links, and remaining budgets.
2. Stop before starting if the maximum allowed next evaluation could exceed a
   total budget. Never silently raise a budget.
3. Create the next experiment record with one falsifiable hypothesis and the
   smallest change that tests it. Touch only mutable paths; a forbidden-path
   change is an invalid candidate.
4. Commit exactly that candidate before evaluation. The full commit hash is
   its identity; do not bundle hypotheses.
5. Verify evaluator integrity, run its exact command under the per-evaluation
   timeout and resource boundary, retain stdout/stderr and resource use, then
   verify evaluator integrity again.
6. Parse the declared output, write detailed evidence, and append one TSV row.
7. Keep only a completed candidate that passes every guardrail and improves by
   the program's meaningful threshold or retest rule. Update the verified best
   commit only after the row and evidence are durable.
8. Discard a regression, unchanged result, invalid output, forbidden-path
   change, or guardrail failure. Use `inconclusive` for a crash, timeout, or
   genuinely unresolved measurement. In all non-kept cases, return the
   dedicated branch/worktree to the prior verified best commit, verify both
   commit and clean status, and record that proof without touching any other
   worktree or user work.
9. After a keep or rollback, update the mutable group `README.md`, account for
   all consumed budget, and evaluate terminal conditions before proposing the
   next hypothesis.

Rollback may use a destructive Git operation only inside the resolved
dedicated worktree, only to the exact recorded best commit, and only when the
program and host approval policy authorize it. Candidate commits remain named
in the append-only ledger even when the branch moves away from them.

## Failures, terminal states, and resume

- **Crash:** capture the exit and logs, append `outcome=crash` with
  `decision=inconclusive`, rollback, account for budget, then apply the
  configured repeated-failure stop rule.
- **Timeout:** terminate only the evaluator processes within the approved
  boundary, capture partial logs, append `outcome=timeout` with
  `decision=inconclusive`, rollback, charge the full elapsed budget, then apply
  the timeout/failure stop rule.
- **Guardrail regression:** append the completed measurements with
  `decision=discard`, rollback, and stop as well if the program's guardrail stop
  condition fires.
- **Acceptance threshold:** stop immediately after a verified kept result meets
  it; do not spend remaining budget.
- **Budget:** stop before an evaluation that could exceed any total limit, or
  immediately after the configured candidate count is reached.
- **Invalid evaluator/environment or safety boundary:** preserve evidence,
  rollback any candidate, and stop; do not improvise around the boundary.

On resume, perform no candidate mutation until all of these checks pass:

1. Re-read the approved program and verify its recorded hash from the group
   `README.md`; verify the evaluator and environment identity.
2. Validate the fixed TSV header and every row's field count, commit, evaluator
   hash, and artifact directory. Never repair history by rewriting it.
3. Recompute consumed budgets from the ledger and detailed records. Find the
   last verified `baseline` or `keep` row; that commit is the only resume base.
4. Reconcile an interrupted experiment. If durable evidence proves a completed
   evaluation, append its missing row exactly once. If a candidate commit
   exists but evaluation evidence is incomplete, record it as a
   crash/inconclusive attempt, append one row, and rollback. If interruption
   happened before a candidate commit, mark the artifact abandoned and append
   no row. Never invent a metric from partial output.
5. Verify the dedicated worktree is clean at the best commit. If not, preserve
   diagnostic evidence and apply only the approved rollback; otherwise stop.
6. If a terminal condition was already reached, record it and do not resume the
   loop. Otherwise continue with the next unused experiment number.

End with exactly one group terminal state: `threshold_met`, `budget_exhausted`,
`stop_condition`, `evaluator_invalid`, `environment_invalid`, `safety_stop`, or
`user_stopped`. Report the best verified commit and metrics, attempts/keeps,
budgets consumed, terminal reason, and artifact path. A crash of the agent or
host is not itself permission to exceed the approved program on resume.

For mechanical validation, record `Evaluator SHA-256: <digest>` in `program.md`
and `Program SHA-256: <digest>`, `Worktree: <path>`, `Best commit: <commit>`,
`Candidates consumed: <count>`, `Evaluator seconds consumed: <number>`,
`Compute cost consumed: <number>`, and `Terminal state: <state>` in the group
`README.md`. These totals are recomputed from the fixed ledger and experiment
records and must remain within every per-evaluation and total program budget.
Before reporting completion or resuming mutation, run
`python scripts/validate_run.py <group-directory>` from this skill directory
and fix every reported artifact-integrity error.
