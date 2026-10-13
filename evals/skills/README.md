# Offline skill activation evals

This is an offline-ready first slice, not a measured baseline. It evaluates
activation evidence independently of task utility. No provider is invoked,
and no dashboard, database, package installation, or global settings are needed.

The corpus has 50 authored scenarios: ten each for `implement`, `diagnose`,
`testing-code`, `test-audit`, and `improve-codebase-architecture`. Each family
has four natural requests, two contextual requests, three nearby negatives, and
one explicit invocation control. Some negatives are direct diff-review requests,
which expect no `swe` skill.

The swe consolidation merged `test-audit` into `testing-code` and
`improve-codebase-architecture` into `codebase-design`. The corpus keeps the
old names, so every arm runs byte-identical cases. On a catalog without an old
name, `SUCCESSORS` in `skill_eval.py` scores it as its successor. Four cases
lose their meaning there and are excluded: `TC-07` and `TA-07` expect and
forbid the same merged skill, and `TA-10` and `AR-10` type a removed name.
`validate` lists them. A comparison with a catalog that still has the old
names must drop the same four cases from both arms. User-only skills such as `write-plan` have no
family: the model cannot load them, so there is no activation to measure.
Ten cases marked `holdout_candidate` are
disclosed development material, **not a sealed holdout**. An independent sealed
set is still required before tuning from measured scores.

`cases.json` holds evaluator labels, allowed auxiliary skills, forbidden skills,
rationales, and case-specific action boundaries. `fixtures/` holds only task
inputs. The materializer copies messages and fixture files; it never copies
answer keys into the execution directory. Context is serialized as preceding
USER/ASSISTANT messages in one prompt, not replayed as native multi-turn sessions.
This delivery difference is frozen and must be reported with results.

## Local workflow

Run from the repository root with Python 3.10+ and Git. Run output belongs under
`artifacts/skill-evals/`. Choose a fresh output directory; existing runs are never
overwritten. The repository already provides its ignored artifacts location.

```sh
python3 evals/skills/skill_eval.py validate
python3 evals/skills/skill_eval.py materialize \
  --case CASE_ID --runtime evals/skills/runtime.offline.json \
  --output artifacts/skill-evals/RUN_ID
python3 evals/skills/skill_eval.py capture \
  --run artifacts/skill-evals/RUN_ID --source /absolute/path/to/trace.jsonl \
  --state completed --format synthetic-contract-v1 --evidence-kind synthetic
python3 evals/skills/skill_eval.py score --run artifacts/skill-evals/RUN_ID
python3 evals/skills/skill_eval.py aggregate artifacts/skill-evals/*/score.json
```

Replace `CASE_ID` using `cases.json` and `RUN_ID` with a unique name. To score a
Claude Code session, run it headless from the run's `workspace/` in the audited
shape, then capture the session transcript:

```sh
claude -p "$(cat /absolute/RUN/inputs/prompt.txt)" --output-format stream-json --verbose \
  --setting-sources project,local --plugin-dir /absolute/RUN/inputs/plugins/swe \
  < /dev/null > /absolute/path/to/stream.jsonl
```

`--output-format stream-json` needs `-p` and `--verbose`.
`--setting-sources project,local` keeps user settings out, so an installed
`swe` plugin does not load beside the snapshot. Add the model, permission, and
tool flags that the frozen runtime names. [EVIDENCE.md](EVIDENCE.md) names the
audited probe runs; their `commands.sh` is the reference invocation.

```sh
python3 evals/skills/skill_eval.py capture \
  --run artifacts/skill-evals/RUN_ID \
  --source ~/.claude/projects/PROJECT/SESSION_ID.jsonl --state completed \
  --format claude-transcript --plugin-dir /absolute/RUN/inputs/plugins/swe \
  --stream /absolute/path/to/stream.jsonl --relevant-action TOOL_USE_ID
```

`--plugin-dir` repeats the absolute path given to `claude`. `--relevant-action`
is a person's label: the root `tool_use` id where the case's relevant action
starts, or `none`. Any other native trace, captured with the default
`--format native`, is retained but stays unscored. Interrupted capture
uses `--state timeout` or `--state incomplete`. Import retains the raw bytes,
capture digest, and final fixture files. Inputs and raw trace digests are checked
before scoring. Each score points to raw evidence and its frozen manifest.
Synthetic read requests must use the exact paths in that run's `manifest.json`
and the corresponding complete bodies. A raw trace from another run will not
prove a load of the newly materialized catalog.

Materialization creates a standalone disposable Git repository with an empty
template, never a linked worktree. It snapshots every checked-out plugin body
and resource, rather than supplying only the target skill. Both original source
and effective input file hashes are retained. Staged hooks and MCP configuration
bindings are removed and listed as harness deltas; source plugins are unchanged.
The full checked-out SWE/Lab catalog is not claimed to equal all installed skills
on a real host. A native pilot must freeze and verify that complete effective set.

The offline runtime example deliberately says `not-run`. For any future native
run, replace it with verified model ID, effort, CLI/version, permissions, tools,
catalog scope, context delivery, and harness deltas before materializing.

## Metrics and evidence

See [EVIDENCE.md](EVIDENCE.md) for the exact observation contract, the synthetic
envelope, and the Claude transcript adapter. Both adapters prove exact identity
and full delivered body before counting a load. Mentions, intentions, listings, failed reads and partial
bodies cannot count as successful activation.

Aggregation separates frozen configuration (runtime, source catalog, adapter
and scorer), target, split, evidence kind and implicit versus explicit controls.
Recall uses completed sessions with complete evidence and a resolved
load/miss, with its denominator reported. Nearby negatives supply false activation
rates; allowed auxiliaries do not count as confusion. Unexpected successful loads
produce confusion pairs grouped by the actual expected skill set. Pair rates
include only cases where the observed skill is inappropriate and its evidence
is resolved; correct positive activations cannot dilute negative-case confusion.
Timeouts, incomplete sessions, unavailable/partial
evidence and read status counts remain visible instead of being silently folded
into misses. Timing is `before`, `late`, or `unavailable`, separately from recall.
Observed forbidden loads are preserved even for interrupted sessions.

These cases assess skill discovery, not whether instructions improve outcomes.
The older 38 metadata-selection seeds and 12 utility cases remain separate.
A utility A/B/C experiment needs task oracles and verified instruction isolation;
it is not implemented here. Authored prompt variety does not imply broad coverage
or justify a single pooled efficacy percentage.

## Verification and next step

`python3 -m unittest discover -s evals/skills/tests` exercises the public CLI with
synthetic traces and minimal Claude-shaped transcripts. It checks leakage/isolation
of fixtures, strict body identity, ordering, incomplete/failed reads, missing
native evidence, aggregate denominators, and the Claude load proofs and message
order. This verifies harness behavior only.
The retained verification record is
`artifacts/skill-evals/2026-09-30-offline-verification/verification.json`.
Four inspectable synthetic examples and their raw evidence are retained at
`artifacts/skill-evals/2026-09-30-offline-demo-final/report.json`.
Use `PYTHONDONTWRITEBYTECODE=1` for unittest and place explicit compilation caches
under `artifacts/skill-evals/`, so run output stays out of source directories.

Native scoring supports Claude Code session transcripts from the audited
version (2.1.296, headless): `Skill`-tool loads, by full or bare name, proved
by the linked delivered body, full `Read` loads of a frozen `SKILL.md`, root versus sidechain scope,
labeled action timing, and end coverage from stream-json. It does not support
typed slash-command loads, `Skill` calls with arguments, compaction, resumes,
repeat-load notes, Codex traces, unlabeled actions, or step-list extraction.
These leave the session partial or the load unproved; they never count as a
miss. EVIDENCE.md holds the contract and the raw-event audit.

No activation baseline exists yet. A native run needs an authorized pilot:
proposed model, effort, count, access, isolation limits and costs must go to the
coordinator before starting. Do not run the model matrix from this README or assume stripping
bindings disables manual external calls. Native subprocess execution and sandbox
enforcement are intentionally absent pending that gate.

Sources: the private source chat, especially its final two eval turns; the repository's current skill contracts; and OpenAI's
[skill eval guidance](https://developers.openai.com/blog/eval-skills). The supplied
[X post](https://x.com/samzliu/status/2103613396625367437) returned HTTP 403 during
this implementation and supplied no independently verified claim.
