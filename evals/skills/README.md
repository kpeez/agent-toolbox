# Offline skill activation evals

This is an offline-ready first slice, not a measured baseline. It evaluates
activation evidence independently of task utility. No provider is invoked,
and no dashboard, database, package installation, or global settings are needed.

The corpus has 90 authored scenarios. Seventy are swe cases: ten each for `implement`, `diagnose`,
`testing-code`, `test-audit`, `improve-codebase-architecture`, `ship-pr`, and
`grill` (family prefix `HO`). Each family
has four natural requests, two contextual requests, three nearby negatives, and
one explicit invocation control. Some negatives are direct diff-review requests,
which expect no `swe` skill.

The `lab-making-plots-*` family adds ten cases for `lab:making-plots` in the
same mix, on the `classifier-figures` fixture. Three of its natural and contextual
requests repeat a real session in which the skill did not load: regenerate the
figures, transpose the results table, and apply a reference visual design.

The `lab-mode-*` family adds ten cases for `lab:lab-mode` in the same mix, on
the same fixture. The scorer checks only that the router loads. Each case
names the playbook it should pick in `relevant_action`, but no field scores
that choice.

The swe consolidation merged `test-audit` into `testing-code` and
`improve-codebase-architecture` into `codebase-design`. The corpus keeps the
old names, so every arm runs byte-identical cases. On a catalog without an old
name, `SUCCESSORS` in `skill_eval.py` scores it as its successor. Four cases
lose their meaning there and are excluded: `TC-07` and `TA-07` expect and
forbid the same merged skill, and `TA-10` and `AR-10` type a removed name.
`validate` lists them. A comparison with a catalog that still has the old
names must drop the same four cases from both arms.

Five negatives also change meaning on the new catalog. `TA-08` and `TA-09`
now forbid `testing-code`, and `AR-07` to `AR-09` now forbid
`codebase-design`. On the old catalog, a load of those skills there was only
unexpected, and `codebase-design` could load legitimately. Report these five
cases' false activations as their own stratum, not in a pooled comparison. The
"Activation facets with no case" list in [FACETS.md](FACETS.md) names each
model-invocable skill that has no family yet.

The `ship-pr` family exists because `ship-pr` became model-invoked on the
`swe-router-rewrite` branch. On main it is user-only, so main scores zero recall
and zero false activation for it by construction. Report this family on its own,
not in the pooled main-versus-branch comparison. Its negatives matter most: a
false activation loads a skill that commits, pushes, and merges. The fixture has
no remote, so a trace can show the commit and the reads that precede a push, but
not the push itself. Its `receipt-totals` fixture also holds a CI log and review
threads as plain files, because no host is reachable.

The `HO` family targets `interview-user`, the renamed `grill` with a wider trigger.
The family keeps the corpus name `grill`. `SUCCESSORS` scores it as `interview-user` on
the branch, so the family compares main and branch directly. Its explicit case
types the new name `/swe:interview-user`, so main excludes it. Its negatives matter
most: a false activation starts a question round on a clear task. They include
"figure out why a test fails", which is diagnosis.

Fourteen cases marked `holdout_candidate` are
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
uv run evals/skills/skill_eval.py validate
uv run evals/skills/skill_eval.py materialize \
  --case CASE_ID --runtime evals/skills/runtime.offline.json \
  --output artifacts/skill-evals/RUN_ID [--hook-arm {hook-off,hook-on}]
uv run evals/skills/skill_eval.py capture \
  --run artifacts/skill-evals/RUN_ID --source /absolute/path/to/trace.jsonl \
  --state completed --format synthetic-contract-v1 --evidence-kind synthetic
uv run evals/skills/skill_eval.py score --run artifacts/skill-evals/RUN_ID
uv run evals/skills/skill_eval.py aggregate artifacts/skill-evals/*/score.json
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
uv run evals/skills/skill_eval.py capture \
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
and effective input file hashes are retained. By default (`--hook-arm hook-off`),
materialize deletes every plugin `hooks/` directory, MCP configuration file,
and manifest `hooks` or `mcpServers` key. With `--hook-arm hook-on`, materialize
keeps each plugin's `hooks/session-start.md` and keeps only the `SessionStart`
entries in `hooks/hooks.json` that read that file; it deletes all other hook
files and event bindings. `rules/AGENTS.md` stays in both arms, and
`manifest.json` records `hook_arm`, `removed_bindings`, and `known_deltas`.
Source plugins stay unchanged. `score` and `aggregate` record `hook_arm` in the
frozen configuration and group keys, so the two arms never pool. The hook
delivery shape comes from local transcripts, and `6-native-pilot` must confirm
it (see [EVIDENCE.md](EVIDENCE.md)).
The full checked-out SWE/Lab catalog is not claimed to equal all installed skills
on a real host. A native pilot must freeze and verify that complete effective set.

The offline runtime example deliberately says `not-run`. For any future native
run, replace it with verified model ID, effort, CLI/version, permissions, tools,
catalog scope, context delivery, and harness deltas before materializing.

## Facet map

A facet is one workflow behavior that a transcript can show. Examples are a
skill load, a route line, a full playbook read, a step load, and the Steps
section. `facets.py` derives every facet from the skill sources: the routers,
the playbooks, the session-start hooks, and the skill frontmatter. It also
reads the eval corpus (`cases.json`) and the targets in `skill_eval.py` to
find the cases that cover each facet. `facets.json` holds one record per
facet. `FACETS.md` shows the same data as tables, with a legend for each
facet kind. Do not edit either file by hand.

Regenerate both files after you change a skill, a router, a playbook, a hook,
or an eval case:

```sh
uv run evals/skills/facets.py write
```

CI runs `uv run evals/skills/facets.py check`. The check fails when a skill
change leaves the map stale. `write` also fails when a playbook step names a
skill, principle, playbook, or reference that does not exist.

Each facet has a scorer status:

- `scored`: a case field scores it.
- `recorded`: the scorer records the load, resource read, subagent read, or hook delivery, but no case field scores it.
- `invisible`: the scorer drops the event.

The headline of `FACETS.md` counts the always-required facets that no case
scores. That count is the measurement gap.

One known limit: the generator labels a whole step `conditional` when the
step starts with "When " or says "Skip when" or "Skip for". A step that has
one unconditional name and one conditional name gets the same label for both
names.

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

`uv run -m unittest discover -s evals/skills/tests` exercises the public CLI with
synthetic traces and minimal Claude-shaped transcripts. It checks leakage/isolation
of fixtures, strict body identity, ordering, incomplete/failed reads, missing
native evidence, aggregate denominators, and the Claude load proofs and message
order. This verifies harness behavior only. `test_facets.py` runs `facets.py`
on a copied catalog. It checks that `check` fails on a stale map and that
`write` rejects a step name that nothing owns.
The retained verification record is
`artifacts/skill-evals/2026-09-30-offline-verification/verification.json`.
Four inspectable synthetic examples and their raw evidence are retained at
`artifacts/skill-evals/2026-09-30-offline-demo-final/report.json`.
Use `PYTHONDONTWRITEBYTECODE=1` for unittest and place explicit compilation caches
under `artifacts/skill-evals/`, so run output stays out of source directories.

Native scoring supports Claude Code session transcripts from the audited
version (2.1.296, headless), plus the 2.1.325 additions: five metadata record
types (`session-owner`, `api-request`, `api-request-shape`, `api-request-blob`,
`tools-used`) that carry no skill load, and parallel tool calls whose one API
message spans several lines. It supports `Skill`-tool loads, by full or bare name, proved
by the linked delivered body, full `Read` reads of frozen `SKILL.md` and plugin resource files
(playbooks and references named in `facets.json`), root versus subagent records (`child_loads` and
`child_resource_reads`), `Bash` commands mentioning frozen paths in `unproved_reads`,
labeled action timing, and end coverage from stream-json. A `Skill` call with
arguments counts when Claude Code appended them to the body as
`ARGUMENTS: <args>`. It does not support typed slash-command loads, arguments
substituted into a `$ARGUMENTS` placeholder, compaction, resumes,
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
