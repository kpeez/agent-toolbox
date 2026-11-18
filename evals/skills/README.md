# Offline skill activation evals

This is an offline-ready first slice, not a measured baseline. It evaluates
activation evidence independently of task utility. No provider is invoked,
and no dashboard, database, package installation, or global settings are needed.

The corpus has 136 authored scenarios. Eighty are swe cases in the 4/2/3/1 mix: ten each for `swe-mode`, `implement`, `diagnose`,
`testing-code` (new-test and probe mode), `testing-code` audit mode, `codebase-design`,
`ship-pr`, and `interview-user`. A case belongs to the family named by its
`family` field, else by its target. The audit-mode cases set `family:
testing-code-audit`, so the two `testing-code` families keep their own 4/2/3/1 mix and their own
`aggregate` group. Each family
has four natural requests, two contextual requests, three nearby negatives, and
one explicit invocation control. Some negatives are direct diff-review requests,
which expect no `swe` skill.

The `lab-making-plots-*` family adds ten cases for `lab:making-plots` in the
same mix, on the `classifier-figures` fixture. Three of its natural and contextual
requests repeat a real session in which the skill did not load: regenerate the
figures, transpose the results table, and apply a reference visual design.

The `swe-mode-*` family adds ten cases for `swe:swe-mode` in the same mix. Its seven positives
are router-load cases that also set `expected_route`, so each scores the route line, the read of
the playbook, and the Steps section. Its three negatives are a closing remark, a quick fact that
needs no repository, and a task outside software. A load of the router there is a false
activation. The closing remark and the quick fact also forbid `swe:go-deeper`, because its skip rule
excludes chat and quick facts. The software-free task allows it and `swe:writing`, because the session-start hook
runs `go-deeper` on a task of any kind and sends the reply through `writing`. `swe-mode-pause-safely`
forbids `go-deeper` too: it is a follow-up inside a task that an earlier turn framed.
`swe-mode-improve-performance` runs on the `tile-preview` fixture, whose renderer rebuilds a palette of 3,000 shades
for every tile. `python3 preview.py` (python 3.9) took 14.6 to 16.3 s over eight runs, median 14.8 s, so the request
says "about 15 s".

The `lab-mode-*` family adds ten cases for `lab:lab-mode` in the same mix, on
the same fixture, except `lab-mode-run-experiment`, which needs a training pipeline and uses `ticket-classifier`. Six of them set `expected_route`, the route the agent should
pick, and the scorer checks whether the agent followed it (see "Route scoring").
The others set no route.

The two route-choice families, `swe-route-choice` (24 cases) and `lab-route-choice` (6 cases), cover
each playbook and single-skill route that no other case covers, with one case per route. They have
no fixed mix: `validate` rejects a negative case, and a case with no `expected_route`, in an open family, because a route-choice case scores one route. A negative in a mix family may set `expected_route`. Every
case instead resembles a neighbouring route and belongs to its own: the `rationale` names the
near miss. Cases on a route with modes set `expected_mode`. A route-choice case holds one correct
route that the router's own text supports, and its fixture holds every input that the task names.
For example, `swe-route-diagnose-runtime` runs a worker script that spins, `swe-route-ship-pr` has a conflicted
`receipt.py`, and `lab-route-maintain-project-skills` has project skills and a renamed column. Where two router lines overlap, such as the PR-status
trigger and the `ship-pr` route, the case uses wording that only one of them matches.

A workspace is a copy of the fixture plus a fresh `git init` with no commits, remote, or past sessions, and the native
tool set has no shell, so an agent can never run `git` or `gh`. A case that needs repository state puts it in the
fixture as plain files that the prompt names, and the prompt says the copy has no git history or forge access.
`swe-route-ship-stack` holds the stack's PR state, CI runs, and patches; `swe-route-ketchup` holds the commits, the PR
state, and the decision log of a four-day run; `swe-route-reflect` holds a past session's transcript; and
`swe-route-clean-worktrees` holds the worktree list, merge state, sizes, and the open sessions.

No `hidden-skill-fallback` case covers `autopilot-full` or `autopilot-stack`. Their hidden names sit in steps that a
PR owner reaches: `3-report-code-ready-head` (`no-comments`) and `6-swarm-verify-once` (`swarm`) need a code-ready head,
which an owner commits and reports. The native tool set has no subagent tool to spawn an owner and no shell to commit,
and the playbook forbids the coordinator to write a PR itself. A correct run therefore stops before those steps, and
files cannot supply an owner or a head, so no case lists their reads.

The family `hidden-skill-fallback` (6 cases) targets the skills and principles that the Skill tool
refuses because the model's list hides them. A playbook step names them, and the agent must read
`../<name>/SKILL.md` or `../principle-<slug>/SKILL.md` by path. Each case sets `expected_route` and lists in
`facets` the `principle-read` facets and `step-load` facets of hidden skills that its route needs. A name on a playbook's Reply
line is not listed, because the router loads only names in step parentheses. It words the request so that the
step which names each principle applies, for example two failed fixes before `attack-the-premise`.
A listed facet scores `loaded` or `miss` whether or not the agent marks its step done, so a case lists only facets from steps that a correct run on
its prompt and fixture must do. A step that the run may correctly skip, such as a conditional step whose condition the fixture does not meet, lists none.
The family has no fixed mix and no negatives.

The "Activation facets with no case" list in [FACETS.md](FACETS.md) names each
model-invocable skill that has no family yet.

The `ship-pr` family's negatives matter most: a false activation loads a skill that commits,
pushes, and merges. The fixture has
no remote, so a trace can show the commit and the reads that precede a push, but
not the push itself. Its `receipt-totals` fixture also holds a CI log and review
threads as plain files, because no host is reachable.

The `interview-user` family's negatives matter most: a false activation starts a question
round on a clear task. They include "figure out why a test fails", which is diagnosis.

20 cases marked `holdout_candidate` are
disclosed development material, **not a sealed holdout**. An independent sealed
set is still required before tuning from measured scores.

`cases.json` holds evaluator labels, allowed auxiliary skills, forbidden skills,
rationales, and case-specific action boundaries. `fixtures/` holds only task
inputs. The materializer copies messages and fixture files; it never copies
answer keys into the execution directory. Context is serialized as preceding
USER/ASSISTANT messages in one prompt, not replayed as native multi-turn sessions.
This delivery difference is frozen and must be reported with results.

## Local workflow

Run from the repository root with uv and Git. Run output belongs under
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
before scoring. Materialize records `corpus_sha256` and `facets_sha256`, the
digests of `cases.json` and `facets.json`. `score` refuses a run when either file
changed since materialization, because route scores read both. A manifest made
before `facets_sha256` existed still scores. Both digests enter the frozen
configuration, so runs scored under different maps never pool in `aggregate`.
Each score points to raw evidence and its frozen manifest.
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

## Native runner

`run_eval.py` runs the pilot: for each (case, arm, repeat) it calls `skill_eval.py`
`materialize`, launches headless `claude -p` with the frozen flags, then calls `capture` and
`score`, and at the end `aggregate`. It does not copy their logic. It is a dry run unless you pass
`--execute`. A dry run launches no model. It does run `claude --version`, `--help`,
`plugin list --json`, and `auth status --json`, which need no model.

```sh
uv run evals/skills/run_eval.py --case IM-01 --repeats 2
```

The dry run prints the frozen configuration, the planned runs (arms are `hook-on` and `hook-off`,
never git refs), the argv template, the worst-case cost, the preflight result, the blockers, and the
live steps that wait for approval. `--repeats` defaults to 10 runs per case and arm. Without `--case`
it plans every usable case.

Run the live canaries first, then execute, both only after approval and with the same flags:

```sh
uv run evals/skills/run_eval.py --canaries --pilot-id PILOT --max-cost-usd 20
uv run evals/skills/run_eval.py --execute --pilot-id PILOT --max-cost-usd 20 \
  [--backup-dir /absolute/path]
```

`--output-root` moves the pilot folders away from `artifacts/skill-evals/`. The tests set it to a
temporary directory, so no test writes under `artifacts/`. `--pilot-id` must be a plain folder name,
not `.` or `..`, that resolves to a folder inside `--output-root`.

The runtime file `runtime.native.json` holds the model, effort, tools, permission mode, per-run
budget, worst-request cost bounds, timeout, and the confinement each limit needs. Its model, effort,
`worst_request` fields, and `max_concurrent_requests` say `UNAPPROVED` and
`approval` is `null`. `--execute` and `--canaries` refuse until a person sets them and the preflight passes.
Both also need `--pilot-id` and `--max-cost-usd`. `--execute` also refuses until `canaries.json` holds
a pass for every canary (see "Canaries"). The runtime file is part of the frozen
configuration, so a changed file starts a new pilot.

### Layout

```text
artifacts/skill-evals/PILOT/
  pilot.json              frozen manifest, written once: runtime, stopping rule, harness and plugin digests, preflight
  runtime.json            the runtime file that materialize read
  mcp-empty.json          the strict MCP config
  canaries.json           the canary verdicts for this frozen configuration, written by --canaries
  canaries/NAME/          one run per canary, same layout as a run, plus canary.json (verdict, cost against budget)
  effective-session.json  the init event (skills, tools, plugins, model) of the first canary that has one, the baseline for drift
  report.json             run states, cost, aggregate with a Wilson 95% interval for recall and false activation
  runs/r-<hash>/          one run per (case, arm, repeat); the hash hides the case id from the agent
    run.json              argv, env keys, session id, exit code, timeout, duration, usage, effective session, violations
    launch/stream.jsonl   raw stdout bytes; launch/stderr.txt
    claude-home/          the run's own CLAUDE_CONFIG_DIR, with the session transcript and subagent files
    workspace/ inputs/ manifest.json capture.json raw*.jsonl final-files/ evidence.json score.json   (skill_eval.py)
```

`artifacts/` is ignored, so `--backup-dir` copies each finished run and the report to a destination
outside the repository. The runner deletes only a run folder that never launched: a folder with no
`run.json` left by an interrupted setup, and the folder it just materialized when a frozen input
(corpus, fixture, plugin catalog, or harness) changed since the freeze. Both hold no model output. It never deletes or moves a run that launched. `materialize` also refuses when the copy of `plugins/` differs from the catalog it hashed just before (less `__pycache__` and `*.pyc`), so a change during the copy launches nothing. Case labels and oracles stay in `cases.json`;
the run folder holds only the prompt, the fixture, and the frozen catalog.

### Preflight

Each check needs no model call, and a dry run writes nothing. A `fail` blocks `--canaries` and `--execute`.

- `runtime-complete`, `approval-recorded`: every field is set, and a person approved the model and effort.
- `cli-version`: the installed CLI equals the frozen version.
- `flags-in-help`: `claude --help` defines every flag a launch passes, `--include-hook-events` and `--plugin-dir` among them. The runner passes only flags that help lists.
- `effort-allowed`, `permission_mode-allowed`, `permission_prompts-allowed`: the values are in the help's choices.
- `config-home-isolated`: a fresh `CLAUDE_CONFIG_DIR` lists no installed plugin, so host plugins and
  skills stay out. The run uses one such directory per run.
- `auth-in-isolated-home`: the isolated home is logged in and honors the directory. It holds no OAuth
  login, so the pilot bills `ANTHROPIC_API_KEY`.
- `confine-read`, `confine-write`, `confine-network`: with `confined`, the tool set must hold no shell,
  web, or MCP tool, and `restricted` must be true for read and write. No flag confines a shell tool, so a
  tool set with one fails. Set the limit to `unconfined` to accept it. The manifest records that choice.
  A passing check is `pending_live`: the CLI documents the limit, and a canary proves it.
- `backup-dir`: writable, or creatable under a writable folder, and outside the repository. The check never creates it; the pilot creates it when it copies the first run.

The launch environment holds only `PATH`, `HOME`, `TMPDIR`, locale, proxy and certificate variables,
`ANTHROPIC_API_KEY`, and `CLAUDE_CONFIG_DIR`. After each run, the init event is checked: no MCP server,
no shell or web tool under a confined limit, and the auto-memory path inside the run's config home. A
check that fails stops the pilot. A run whose stream has no init event also stops it, because its isolation was not checked.
Every launch, canary or run, is also checked for an escape in its stream, whatever its prompt asked: a
`Write`, `Edit`, or `NotebookEdit` outside `<run>/workspace` and `<run>/inputs/plugins`, a `Read` of a
file there that returned, a `Glob` or `Grep` result that names a path there, or any shell or web call,
unless its `tool_result` is an error. A write, shell, or web call with no `tool_result` counts too. Both
sides of each path are resolved first. An escape writes `isolation-violation.json` before `run.json`
records it, and stops the pilot or the canary phase, so a crash after the launch cannot hide it.
Every later canary and run must match the effective session that the first canary with an init event
froze, which also freezes the bundled skills that the checked-out catalog does not list.

### Arm check

`--restricted` changes which settings load, so a `hook-on` run proves nothing unless its SessionStart
hook ran. The runner passes `--include-hook-events`, reads the `hook_started` and `hook_response`
events from `launch/stream.jsonl`, and records one entry per hook in `run.json` as `hook_events`:
event, name, plugin, started, completed, outcome. The events carry no plugin name, so the runner
attributes a completed hook to the plugin whose frozen `hooks/session-start.md` starts with the hook's
output. An arm violation stops the pilot, like an init-event violation:

- `hook-on`: some plugin that the manifest froze a SessionStart hook for has no matched SessionStart
  hook that completed with outcome `success`. Every plugin in `manifest["hooks"]` needs one.
- `hook-off`: any hook started or completed.

The event shape comes from a stream-json capture in an earlier session transcript (`type: system`,
`subtype: hook_started` or `hook_response`, `hook_id`, `hook_name` such as `SessionStart:startup`,
`hook_event`, and on the response `output`, `exit_code`, `outcome`). That capture came from another CLI
version, so the `hook-on` and `hook-off` canaries confirm it.

### Stopping rule and cost

The rule is fixed in `pilot.json` before the first launch. Runs go repeat by repeat, then case, then
arm, so any stop leaves the arms within one run of each other. A launch reserves its per-run budget plus
`max_concurrent_requests * max_request_usd`, computed from the runtime's `worst_request` fields
(`context_tokens`, `output_tokens`, `usd_per_mtok_input_max`, `usd_per_mtok_output`). The
runner launches a run only when the known spend, plus the reservation of each run with unknown cost, plus
the next run's reservation, stays within `--max-cost-usd`. It also stops after three failed runs in a
row, on drift, on an isolation violation, on an arm violation, and when a pilot run's known cost exceeds
its budget plus `max_concurrent_requests * max_request_usd` (which writes `budget-assumption-broken.json`
and blocks any future launch in that pilot). Cost comes from the stream's `result`
event. The runner reads it and checks that bound first after the child exits, before it reads the init
and hook events, so a run that fails later still records its cost. A missing cost stays `null`, counts at the reservation for the cap, and shows in `report.json` as
`unknown_cost_runs`. A run that already launched is never launched again. A rerun skips a run with
`score.json`, rescores a run that finished without one, and leaves a run that launched but did not
finish where it is. That run is `aborted`: the runner was interrupted, was hard-killed (SIGKILL or power
loss leaves a `run.json` with `started_at` and no `ended_at` or `outcome`), or failed while reading the
stream after the launch. Its `run.json` records `outcome: aborted` and the reason. It is final and
unscorable. `report.json` counts it under `run_states`. Its spend is the recorded cost, or the
reservation when it has none (an interrupt or a hard kill records none). An interrupted or hard-killed
run never reached the escape check, so the runner checks its retained stream once, when it records the
interrupt or settles the hard kill. An escape there writes `isolation-violation.json` and stops the pilot.

On SIGINT, SIGTERM, or SIGHUP, the runner kills the whole process group of the running `claude`, waits
for it, records the run as `aborted` with the signal, and exits with a nonzero status. The signals are
blocked from before the fork until `Popen` returns and while the kill runs, and only the first one
raises, so a signal cannot leave a child that the runner does not know or skip the kill. A signal that
arrives before the child starts is recorded as such, with no kill claimed. A signal that arrives while
the runner kills a child that already timed out is recorded as a killed child with `timed_out: true`.
No test covers the block before the fork. Only the unblock and the kill are tested, so the fork race
that the block closes is guarded by the code alone.

The cap rests on two assumptions:

- The CLI checks `--max-budget-usd` before each model request, so a run overshoots by at most the
  in-flight requests, at most `max_concurrent_requests` of them.
- The owner's `worst_request` numbers bound the cost of one request: the context window, the output
  limit, and the highest input and output prices of the approved model.

The `budget-ceiling` canary is the one live check of the first assumption (see "Canaries"). Every launch,
canary or run, checks its cost against the budget it launched with plus the bound, so `budget-ceiling`
checks against $0.02 plus the bound. A launch whose cost breaks it writes `budget-assumption-broken.json`,
which blocks every later launch in that pilot. The ordinary canaries
only show that their own cost stayed within the per-run budget. Their prompts are trivial, so that holds
whether or not the CLI enforces the budget.

Treat the cap as unverified until `canaries.json` shows `budget-ceiling` passed, and read its
`overshoot_usd` next to `overshoot_bound_usd`.

### Canaries

`--canaries` runs seven live runs under the same frozen configuration and approval gate. Each is a
materialized run folder under `canaries/NAME/` that the runner judges from its stream:

- `read-outside`: the agent must try each file-read tool in the session (`Read`, `Glob`, `Grep`) against
  a sentinel file outside the fixture and the plugin snapshot. Each tool needs at least one attempt. A
  call that succeeds and returns the sentinel's file name or its text counts as a read, whichever tool
  made it, so a `Grep` that only lists the file fails too. The sentinel text must also not appear
  anywhere in the stream. A file-read tool that was never tried fails the canary.
- `write-outside`: a `Write` to a new path outside the fixture. At least one attempt must happen, every
  one must be refused, and the file must not exist. The canary has no `Edit` probe. The CLI refuses an
  `Edit` of a file it has not read, and `Read` is confined, so a refused `Edit` would not show that
  writes are confined.
- `network`: the session has no shell or web tool, and no call of one succeeded. The agent does not have
  to try a web call.
- `playbook-read`: a Read of a plugin playbook under `inputs/plugins` succeeds under `--restricted`.
- `hook-on` and `hook-off`: the stream matches the arm (see "Arm check"). The agent does nothing special.
- `budget-ceiling`: a run with `--max-budget-usd 0.02`, far below the per-run budget, and a task of 40 `Read`
  calls, one per turn. It passes only if the budget caused the stop. That means fewer than 40 calls, a
  `result` subtype other than `success`, a known cost of at least the $0.02 budget, and an overshoot at most
  `max_concurrent_requests * max_request_usd` above it. `canary.json` records `stopped`, `tool_calls`,
  `stop_subtype`, `overshoot_usd`, and `overshoot_bound_usd`. A run that keeps spending past the budget,
  one that overshoots by more than the bound, one that finishes the task, and one that stops early with
  less than the budget spent (for example `error_during_execution`) all fail.

A canary also fails when its init event shows an isolation violation or drifts from the frozen
effective session. An escape in any canary (see "Preflight") writes `isolation-violation.json` and stops
the canary phase at once. `read-outside` also counts the sentinel text anywhere in the stream as an
escape, and `write-outside` counts its target file existing after the run. Every canary except `budget-ceiling` also
fails when its cost is not known and within the per-run budget. Only `read-outside`, `write-outside`,
`playbook-read`, and `budget-ceiling` fail when the agent never attempts the call they judge. `canaries.json` holds the verdicts and the frozen
configuration digest. `--execute` refuses without it, with a different digest, or with any canary not
passed or missing. A canary run counts toward `--max-cost-usd`. A canary that launched is never launched
again, so a failed or interrupted canary needs a new `--pilot-id`. A canary that a hard kill left
unjudged has its retained stream checked for escapes; an escape stops the canaries.

### What still needs approval

- Model, effort, runs per case, per-run budget, total cap, tool set, and the confinement choice.
- The backup destination.
- Running `--canaries`, and reading its verdicts and costs before `--execute`.
- A relevant-action label. The runner passes none, so evidence stays partial and recall has a zero
  denominator until a labeler runs. `claude plugin eval` does not replace this runner. Its help lists no hook arm, no effort flag,
  and no way to keep the raw transcript or the final fixture. Its ablation compares a plugin with no
  plugin, and it publishes its report to claude.ai unless `--no-publish` is set.

## Route scoring

A case may set four optional fields. `expected_route` is the id of a `route`
facet in `facets.json`, such as `route/lab/analyze-results`. It must belong to the plugin of the
case's target. A negative case in a mix family may set it, unless the case forbids the plugin's router, because
a route needs the router. An open family holds no negative case. `family` names the case's family (see above). `expected_mode` names the mode of a
single-skill route whose skill has modes, such as `publish` for `route/swe/ship-pr`. A route
with modes needs it, and any other route rejects it. `facets` lists facet ids whose evidence is `skill-call` or
`full-read`. `score.json` then holds `route` (null without `expected_route`)
and `facets`, a `loaded`, `miss`, or `unavailable` value for each listed facet.

`route` scores the agent against its router:

- `line`: the first root text with a `Playbook: <slug>` or `Route: <skill>`
  line. `Playbook` must name a playbook route and `Route` a single-skill route.
  The label may be bold (`**Playbook:**`, `**Playbook**:`) or bulleted
  (`- Playbook:`). The slug may be in backticks, with or without its plugin
  prefix. The status is `match`, `wrong`, `missing`, or `unavailable`.
- `playbook_read` (playbook routes) or `route_load` (skill routes): a root
  full read of the playbook, or a root load of the routed skill.
- `steps_section`: the Steps entries of the final reply (`evidence.json`
  `final_reply`). The parser anchors on the route's handles: the playbook's steps,
  the skill's steps, or the steps of the case's `expected_mode`. An entry is a line
  that starts with a handle, after optional space, a bullet (`-`, `*`, `+`,
  `1.`), backticks, or `**`. The handle must end at a character that is not a
  word character or a hyphen, so `4-check` is not `4-check-the-pipeline`. The
  first word after the handle sets the state, once separators (`:`, `-`, a long
  dash, `**`, backticks, space) are stripped. `done` is done, and a note may
  follow (`<handle>: done, note`). `skip` needs a reason after it
  (`skip: reason`, `skip (reason)`, `skip - reason`). Any other word, or a
  `skip` with no reason, lists the handle in `unclear_handles`. The reply
  splits into blocks at each line that starts with `Steps` in the first column,
  ignoring `#`, `*`, and the space after them. An indented line, such as a
  nested `  Steps 3 to 10 of analyze-results:`, stays inside its block. The text before the first such line is its own block. The section
  is the block with the most entries for this route's handles, and the last
  one on a tie. A block with no entry never wins over one with entries, so a
  second block for another playbook, or a prose line that starts with `Steps`,
  does not hide the route's block. `heading` records whether any such line
  exists. The status is `complete` when every handle appears once, in
  order, each done or skipped with a reason, and none is unclear. It is
  `missing` (or `unavailable` on partial evidence) with no entry, and
  `incomplete` otherwise.
- `step_loads`: for each step the agent marked `done`, the loads its step line
  names. `always` and `conditional` names are `required`, because a step marked
  done says its condition held. A `one-of` step needs any one name.
  A `transitive` name (a step that runs steps of another playbook) is `required` when its `conditional` is false, because the router says such a step also loads the names in those steps. A `transitive` name with `conditional` true is reported in `transitive` and never fails, because the outer Steps section cannot show whether the inner condition held. The scorer does not honor a skip in a nested breakdown. The router
  ties the load to the outer step ("when a step runs steps of another playbook,
  also load the names in those steps") and says the playbook's steps "do not
  join the list", so the Steps section lists only the outer handle. A
  `9-make-figures: skip` under `7-analyze` therefore still requires
  `making-plots`. An agent that skips all of those steps marks the outer step
  `skip:` with its reason. A reference or playbook needs
  a full read. A skill or principle needs a load. A subagent load or read counts
  for a `delegate-allowed` facet. A project skill or the reviewer agent is not
  scorable. A step marked `skip:` requires nothing. A step load has no timing check: a load
  anywhere in the session counts. A `Bash` read of a step resource earns no credit and
  scores `miss`, as in activation scoring.
- `followed`: `false` when any check fails, else `null` when any is unavailable,
  else `true`.

The router runs first, so a case's labels must agree with what a correct router-first run loads: the route, the
`always` loads of its steps, the skills the router's Triggers name, and the session-start hooks. A negative for a leaf skill is
valid only when the correct route for that request never loads that skill. A step text that carries its own condition
counts. `SP-07` forbids `swe:ship-pr` because `fix-bug` step 14 runs "when publication is authorized" and the request says
not to commit or push. `HO-07` forbids `swe:interview-user` because `build-feature` step 2 runs only when the user has not
decided, and the request states the decision. A step that only the user's wording lets a run skip does not count: the
requests `TC-08`, `DG-07`, `TA-07`, and `AR-07` were rewritten for that reason (`fix-bug` steps 6 and 7 name
`testing-code`, step 1 names `diagnose`, `refactor-structure` step 1 names `testing-code`, and `build-feature` step 4 names
`codebase-design`). Their requests now route to no playbook that loads the forbidden skill: three are read-only lookups, and
`AR-07` is a one-function change with no interface, so step 4 does not apply. `validate` refuses a case that lists a skill
as expected or auxiliary and also forbids it.

A case that sets `expected_route` credits what a router-first run on that route loads, so it adds no `unexpected_skills`:

- the plugin's router and the routed skill;
- every skill or principle that a step or reply line of the route names (`route_allowed_skills`);
- every skill or principle that the Triggers section of the plugin's router names (the `trigger-load` facets), such
  as `model-the-domain`, `architect`, `swarm`, `no-comments`, and `log-decisions`. The router says its Triggers "hold
  in every playbook and route", so a correct run on any route may load them. A trigger that names a playbook or a
  reference is a read, not a load, and a project skill is not scorable, so neither adds a credit;
- the always-on triggers: `go-deeper` (Match step 2 of the router) and `swe:writing` (the swe router's prose trigger,
  "the reply included"). A swe route credits `swe:go-deeper` and `swe:writing`.
  A lab route credits `lab:go-deeper` (its own Match step 2), and also `swe:go-deeper` and `swe:writing`. The swe
  session-start hook says to run `swe:go-deeper` on "a new task of any kind" and to write replies with the `writing` skill,
  and a snapshot with both plugins delivers it on a lab task too. The lab router names neither swe skill, so this is
  a decision about the hook, and a lab run that loads either one is not unexpected.

A `forbidden_skills` entry removes its credit, even under `expected_route`. That is how a routed case withholds the
`go-deeper` credit: list `go-deeper` (for a lab route, both `lab:go-deeper` and `swe:go-deeper`) where its skip rule
applies. A `go-deeper` load there is then a false activation.

The `go-deeper` skip rule is: chat, a quick factual answer, a mechanical or fully specified edit, a follow-up inside a
task you already framed, and "just do it". It runs once per task. The corpus applies it as follows.

- Chat and a quick factual answer: `swe-mode-chat`, `swe-mode-quick-fact`, `HO-09`, `lab-mode-define-metric`,
  `lab-making-plots-read-table`, and the lookups `TA-07`, `DG-07`, and `TC-08`.
- A mechanical or fully specified edit or action: the request names every constraint of the change or the action, so
  nothing is left to choose. These are `IM-10`, `AR-07`, `HO-07`, `TC-07` (run a named command and report), `SP-01`
  and `SP-10` (commit finished work and open a draft PR), `SP-04` (land an approved PR),
  `swe-route-ship-stack` (land a named stack), and `lab-mode-rename-column`. `IM-01` and the other requests that leave a design or a cause open stay allowed.
- A follow-up inside a framed task: the last user turn continues the work that an earlier assistant turn did. These
  are `SP-05` (commit what the earlier turn reported complete), `SP-06` (fix what it diagnosed),
  `swe-mode-pause-safely`, and `swe-route-ketchup` (catch up on the queue that the earlier turns framed). A user turn that opens a new task after an answer is
  a new task, so `HO-05`, `HO-06`, `swe-mode-build-feature`, and the lab contextual cases keep `go-deeper` allowed.

A case that sets no `expected_route` gets only one automatic credit: `swe:writing`, when it lists the plugin's router as
expected or auxiliary. It labels the rest itself:

- `acceptable_auxiliaries` where the router text says they load. A swe case about code, a diff review, or a
  README edit lists `swe:swe-mode` and `swe:go-deeper`. A lab case that edits code lists the swe pair too.
- `forbidden_skills` where a load is a false activation: the lab router on an edit that is not research, or
  `go-deeper` on a task its skip rule excludes.
- Neither list where a load is merely unexpected, such as `swe:swe-mode` on a quick factual answer. It then
  shows in `unexpected_skills` and does not count as a false activation.

`aggregate` adds `route_followed_*`, `route_line_*`, `route_steps_*`, and `route_read_*` counts to each group.
A negative case that sets a route (for example a diagnosis request among the `implement` negatives) counts in its
family's group beside the positives. Each count compares a run with the route its own case expects, so the counts
answer "how often did a run follow the route its case sets". A rate over them would mix tasks the skill should and
should not own, so none is reported; read `category` in each `score.json` to split them. It also adds
`other_expected`, the loaded, missed, and unavailable counts of each expected
skill that is not the target, over complete sessions.

## Facet map

A facet is one workflow behavior that a transcript can show. Examples are a
skill load, a route line, a full playbook read, a step load, and the Steps
section. `facets.py` derives every facet from the skill sources: the routers,
the playbooks, the session-start hooks, and the skill frontmatter. It also
reads the eval corpus (`cases.json`) and the targets in `skill_eval.py` to
find the cases that cover each facet. `facets.json` holds one record per
facet. `FACETS.md` shows the same data as tables, with a legend for each
facet kind. Do not edit either file by hand.

A single-skill route takes its handles from the skill's own `SKILL.md`. A step is a list
item that starts with a handle (``1. `1-name`: ...``) or a heading that is a handle
(`## 1-name`). Other numbered lists are not steps. Items belong to the nearest `##` heading
above them. A skill with one such list has `handles`. A skill with several has `modes`,
keyed by the heading in lowercase with hyphens and without a trailing "mode" (`## Drive to
green` is `drive-to-green`, `## Audit mode` is `audit`), and its `handles` is empty. Handles
count from 1 in order. `write` fails when a routed skill has no steps or breaks these rules.

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

The headline of `FACETS.md` counts the always-required behaviors that no case
scores. That count is the measurement gap. It is approximate: a step load
counts once per playbook and name, and a condition in the middle of a step
leaves its names `always`. The scoring policy follows from that: a step the
agent marks `done` requires all of its names. A case marks its route's facets
`scored` through `expected_route`, and the facets that it lists through `facets`.

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
order. This verifies harness behavior only. `test_run_eval.py` runs `run_eval.py` against a stub `claude` on `PATH`. It checks that:
a dry run launches no model and writes nothing, even with a new `--backup-dir`;
the flags check covers `--plugin-dir`;
a full run scores each arm and a rerun launches nothing;
the cost cap stops before the next launch, and unknown cost counts at the run reservation;
an unenforceable limit is rejected unless accepted as unconfined;
a session whose tools break a confined limit, a hook-on run missing a plugin's hook, a hook-off run with
any hook event, and a run with no init event each stop the pilot;
each run records the hook events its arm allows;
a run that launched and failed, and a run that a hard kill left without an end, are aborted and never
launched again; a run that failed after the launch keeps its cost for the cap;
an interrupt kills the child's process group and the run is aborted;
`launch` restores the interrupt handlers and the child keeps no blocked signals;
execute refuses without a canary record for the same configuration, or with a canary missing;
passing canaries are recorded with their cost and the budget-ceiling overshoot, and allow execute;
each failing canary variant is recorded and blocks execute;
an escape in any canary or run writes the marker before the verdict and stops the launches;
a canary that launched is never launched again; an unknown canary cost fails the canary; and a canary
cost above the per-run budget is recorded against that budget. `test_facets.py` runs `facets.py`
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
bindings disables manual external calls. `run_eval.py` runs the pilot (see "Native runner"), but no native run has happened and no
limit is yet proved live.

Sources: the private source chat, especially its final two eval turns; the repository's current skill contracts; and OpenAI's
[skill eval guidance](https://developers.openai.com/blog/eval-skills). The supplied
[X post](https://x.com/samzliu/status/2103613396625367437) returned HTTP 403 during
this implementation and supplied no independently verified claim.
