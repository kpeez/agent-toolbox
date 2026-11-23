# Offline skill activation evals

This is an offline-ready first slice, not a measured baseline. It evaluates
activation evidence independently of task utility. No provider is invoked,
and no dashboard, database, package installation, or global settings are needed.

The corpus has 136 authored scenarios. Eighty are swe cases in the 4/2/3/1 mix: ten each for `swe-mode`, `implement`, `diagnose`,
`verifying-work`, `test-audit`, `codebase-design`,
`ship-pr`, and `interview-user`. A case belongs to the family named by its
`family` field, else by its target. Each family
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
disclosed development material, **not a sealed holdout**. The sealed holdout lives
outside this repository; `dataset/README.md` says how to check a copy. The loader
reads it like `dev.jsonl`: `skill_eval.py --corpus <copy>/holdout.jsonl validate` (the option goes before the subcommand). A corpus is either
all `holdout` or has no `holdout` cases, and the 4/2/3/1 family mix applies only to
a corpus without `holdout` cases.

`dataset/dev.jsonl` holds the corpus as one [Inspect `Sample`](https://inspect.aisi.org.uk/datasets.html)
per line, split by `split` inside `metadata` and not by file. Its card, `dataset/README.md`, maps the fields. The
evaluator labels, allowed auxiliary skills, forbidden skills, rationales, and
case-specific action boundaries sit in each sample's `metadata`. `skill_eval.corpus()` parses each
sample back into the case dict that the rest of the code uses. `dataset/fixtures/` holds only task
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

Replace `CASE_ID` using the `id` fields of `dataset/dev.jsonl` and `RUN_ID` with a unique name. To score a
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
digests of `dataset/dev.jsonl` and `facets.json`. `score` refuses a run when either file
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

## Plugin-eval runner

`run_eval.py` runs the evals through `claude plugin eval`. For each (case, arm, repeat) it calls
`skill_eval.py materialize`, writes a one-case plugin-eval suite beside the snapshot, launches it,
and keeps the session. `score` later calls `capture` and `score` on each kept run, then `aggregate`.
It does not copy their logic. `runtime.plugin-eval.json` freezes the model, effort, CLI version,
tools, turn and time limits, the per-run cost stop, and the harness deltas.

```sh
uv run evals/skills/run_eval.py plan --case IM-01
uv run evals/skills/run_eval.py canary --out artifacts/skill-evals/DATE/canaries \
  --case IM-01 --max-total-usd 5
uv run evals/skills/run_eval.py run --out artifacts/skill-evals/DATE/baseline \
  --max-total-usd 100 --jobs 4
uv run evals/skills/run_eval.py score --out artifacts/skill-evals/DATE/baseline \
  --labels labels.jsonl
```

`plan` launches nothing. It runs `claude --version`, hashes the inputs, and prints the frozen
configuration and the run list. `--case` limits the cases, `--arms` the arms (`hook-on` and
`hook-off`, never git refs), and `--repeats` the runs per case and arm (default 1).

### Launch

Each run folder holds the materialized snapshot and a suite folder:

```text
OUT/
  config.json        frozen once: runtime, CLI version, git SHA, catalog, corpus, fixture, and harness digests
  stop.json          why the batch stopped, when it did; a later `run` launches nothing while it exists
  report.json        written by `score`: run counts, spend, aggregate, Wilson 95% intervals
  runs/CASE/ARM/rN/
    manifest.json inputs/ workspace/      skill_eval.py materialize
    suite/{swe,lab,uni}/                   copies of the snapshot's plugins; the session loads these
    suite/evals/CASE/case.yaml fixture.sh  the prompt, limits, the tools, and a scaffold that copies workspace/
    plugin-eval.json plugin-eval.log plugin-eval.html
    kept/transcript.jsonl kept/stream.jsonl   copied out of the sealed sandbox, which is then deleted
    run.json           cost, error, api_error, turns, the session checks, and whether the stream needed a final newline
  canaries/NAME/ARM/   same layout, for `canary`
  interrupted/         run folders whose launch never finished or ended on an API error, kept for the spend count
```

The launch is `claude plugin eval SUITE --case CASE --ablation none --runs 1 --scaffold
--trust-plugin --no-publish --allow-tools Write Edit --disallow-tools Task TaskStop NotebookEdit
ToolSearch --max-cost-usd STOP --model MODEL --keep-temp`, with `CLAUDE_CODE_EFFORT_LEVEL` set to the
frozen effort. The session has exactly `Read`, `Write`, `Edit`, `Glob`, `Grep`, and `Skill`: no
shell and no Agent tool by default. A runtime file may add the Agent tool (`Task`), as
`runtime.delegation-arm.json` does. In the `hook-off` arm materialize removed every plugin hook, so the suite
copies have none. Plugin eval requires one grader per case, so each case has one that always passes;
`skill_eval.py` scores the kept transcript instead.

After the launch, the runner opens the sealed sandbox, copies the session transcript, the stream
trace, and the agent's final working folder, and deletes the sandbox. The stream trace lacks a final
newline, which the scorer would count as lost coverage. The runner adds it and records
`stream_appended_final_newline` in `run.json`; `capture` records it again as
`stream.appended_final_newline`. The final working folder replaces `workspace/`, so `capture`
records the agent's final files.

### Session checks and stopping rule

Each kept session is checked against the frozen runtime: the CLI version in the init event (so an
auto-update during a batch stops it), the model, the exact tool set, no MCP server, the `swe`, `lab`, and `uni` plugins loaded, `"effort":"high"` in the transcript, and the
hook arm. In `hook-on`, every plugin whose `SessionStart` hook the manifest froze needs a matched
hook that succeeded; in `hook-off`, no hook may start. Hook events name no plugin, so a completed
hook is matched to the plugin whose frozen `hooks/session-start.md` starts with its output. A
violation stops the batch, and `score` skips that run.

A case cannot cap its own cost, and `--max-cost-usd` is checked only before a launch. So the
runner stops the batch after a run whose cost is unknown or over `per_run_stop_usd`. Before each
launch it adds the known spend, the stop amount for each launch with unknown cost (including
`interrupted/`), and the stop amount for each launch in flight and the next one. It launches only
when that sum stays within `--max-total-usd`. A launch in flight counts once, at the stop amount.
The sum covers one `--out` folder only, so pass the budget that is left across all folders. Three runs in a row that end with an error also
stop the batch. Runs go repeat by repeat, then case, then arm, so a stop leaves the arms within
one run of each other. A rerun skips each finished run. A run folder whose launch did not finish
moves to `interrupted/` and runs again. A run whose stream ends with `terminal_reason: api_error`
(for example a 429 usage limit) records `api_error` in `run.json`. It is not finished: a rerun moves
it to `interrupted/` and launches it again, and `score` skips it. The runner prints a line to stderr
only for a run that ends with an error. `config.json` is frozen on the first `run`; a later `run`
with a different configuration needs a new `--out`.

### Canaries

`canary` runs two probes in the fixture of `--fixture-case` (default `IM-01`), in each arm, and
each `--case` it is given. `read-outside` asks the agent to read a sentinel file outside the
sandbox and quote it. `write-outside` asks it to write a file outside the sandbox. `probe.json`
holds the sentinel token and the outside folder. A person reads each kept stream: the sentinel
token must not appear, the outside file must not exist, and the session checks must pass.

### Scoring

`score --labels FILE` captures each kept run with its relevant-action label, a JSONL row of
`case`, `arm`, `repeat`, and `tool_use_id` (see "Relevant-action labeler"). A run with no label
is captured without one, so its evidence stays partial. `score` writes the capture files again on
each pass, so it can run again after more labels.

### Relevant-action labeler

`label_relevant_action.py` labels native Claude Code transcripts for `skill_eval.py capture --relevant-action`.
Its `view` subcommand builds a blinded input for each run:

- **What the labeler sees:** the case's last user message, the case's `metadata.relevant_action` description, and an ordered list of root `tool_use` calls. Each call entry contains only `tool_use_id`, `tool`, and `target` (`file_path`, `pattern`, `path`, or `command`, else compact JSON of the input cut to 300 characters).
- **What the labeler does not see:** `Skill` calls, calls that reach a declared `--plugin-dir` (skills, playbooks, references) by a path, by a path relative to the session's working folder, or by naming the folder anywhere in their input (a Glob pattern or a Bash command), sidechain calls, hook outputs, system text, assistant text, and anything that names the hook arm.

The prompt gives the labeler three rules, the same ones a person uses for hand labels:

- An action that changes or creates a file starts at the first call that changes or creates that file.
- An action that reads, reviews, investigates, assesses, or analyzes something, or proposes a design for existing code, starts at the first read of the file under examination: the thing reviewed, not a reference it is checked against, and not a README or a file listing.
- An action that is only something to say (a stated line, an answer, a question to the user) has no starting call, so the label is `none`. A router case's "say the route and read the playbook" is `none` too, because playbook reads are outside the view.

Before using the labeler on a run, calibrate it with `label_relevant_action.py calibrate` against about 30 hand-labeled pilot transcripts.
Pick the cheapest model that reaches at least 90% exact agreement with the hand labels. When a change to the prompt follows a calibration, check it on fresh hand labels too, because the calibration set has then informed the prompt.
After the run, a person audits a random 5% sample of the labeled transcripts.

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
requests `TC-08`, `DG-07`, and `AR-07` were rewritten for that reason (`fix-bug` steps 6 and 7 name
`verifying-work`, step 1 names `diagnose`, and `build-feature` step 4 names
`codebase-design`). Their requests now route to no playbook that loads the forbidden skill: two are read-only lookups, and
`AR-07` is a one-function change with no interface, so step 4 does not apply. `validate` refuses a case that lists a skill
as expected or auxiliary and also forbids it.

A case that sets `expected_route` credits what a router-first run on that route loads, so it adds no `unexpected_skills`:

- the plugin's router and the routed skill;
- every skill or principle that a step or reply line of the route names (`route_allowed_skills`);
- every skill or principle that the Triggers section of the plugin's router names (the `trigger-load` facets), such
  as `model-the-domain`, `architect`, `swarm`, `no-comments`, and `log-decisions`. The router says its Triggers "hold
  in every playbook and route", so a correct run on any route may load them. A trigger that names a playbook or a
  reference is a read, not a load, and a project skill is not scorable, so neither adds a credit;
- the canonical `go-deeper` skill and arm-aware always-on triggers: `swe:go-deeper`, `lab:go-deeper`, and
  `uni:go-deeper` are byte-identical copies, so the scorer maps any load or label of the three to `go-deeper`.
  In `hook-off`, only the router text asks for anything: a swe route credits `go-deeper`, `swe:writing`, and
  `swe:in-your-own-words` (the First-message trigger, read by path); a lab route credits `go-deeper` only (Match
  step 2; `lab-mode` restates inline and names neither `writing` nor `in-your-own-words`). In `hook-on`, the
  SessionStart hooks ask for `go-deeper` (`swe:go-deeper` and `uni:go-deeper`) and `swe:writing` on every task, so
  `hook-on` adds `go-deeper` and `swe:writing` across both plugins while keeping `swe:in-your-own-words` on swe routes.

A `forbidden_skills` entry removes its credit, even under `expected_route`. Because `go-deeper` is canonicalized,
listing one copy (such as `swe:go-deeper`) in `forbidden_skills` forbids all three copies. A `go-deeper` load there
is then a false activation.

The `go-deeper` skip rule is: chat, a quick factual answer, a mechanical or fully specified edit, a follow-up inside a
task you already framed, and "just do it". It runs once per task. For a quick factual answer or a fully specified
mechanical edit, `go-deeper` is forbidden and the router is acceptable (an auxiliary), not required. On any other
task, `go-deeper` is acceptable or expected, as the route says. The corpus applies it as follows.

- Chat and a quick factual answer (one lookup or short explanation from named files, "change nothing"): `swe-mode-chat`,
  `swe-mode-quick-fact`, `HO-09` (with `swe:swe-mode` acceptable), `lab-mode-define-metric`, `lab-making-plots-read-table`
  (with `lab:lab-mode` acceptable, because `lab-mode` does not exclude a results-CSV lookup, and `lab:making-plots`
  forbidden), and the lookups `TA-07`, `DG-07`, and `TC-08`. Checking whether `format_total` behaves right (`SP-09`)
  is a correctness judgment, not a quick fact, so `go-deeper` stays allowed.
- A mechanical or fully specified edit or action: the request names every constraint of the change or the action, so
  nothing is left to choose. These are `IM-10`, `AR-07`, `HO-07`, `TC-07` (run a named command and report), `SP-01`
  and `SP-10` (commit finished work and open a draft PR), `SP-04` (land an approved PR),
  `swe-route-ship-stack` (land a named stack), and `lab-mode-rename-column`. `IM-01`, `lab-mode-code-fix`, and the
  other requests that leave a design or a cause open stay allowed.
- A follow-up inside a framed task: the last user turn continues the work that an earlier assistant turn did. These
  are `SP-05` (commit what the earlier turn reported complete), `SP-06` (fix what it diagnosed),
  `swe-mode-pause-safely`, and `swe-route-ketchup` (catch up on the queue that the earlier turns framed). A user turn that opens a new task after an answer is
  a new task, so `HO-05`, `HO-06`, `swe-mode-build-feature`, and the lab contextual cases keep `go-deeper` allowed.

A case that sets no `expected_route` gets automatic credits only from `swe:swe-mode` (in `hook-off`, `swe:writing` when
`swe:swe-mode` is expected or auxiliary) and from `hook-on` (`go-deeper` and `swe:writing`, minus `forbidden_skills`).
It labels the rest itself:

- `acceptable_auxiliaries` where the router text says they load. A swe case about code, a diff review, or a
  README edit lists `swe:swe-mode` and `swe:go-deeper`. A lab case that edits code lists `swe:swe-mode` and one
  `go-deeper` copy (`swe:go-deeper`) too.
- `forbidden_skills` where a load is a false activation: the lab router on an edit that is not research, or
  `swe:go-deeper` on a task its skip rule excludes.
- Neither list where a load is merely unexpected, such as `swe:swe-mode` on `lab-mode-define-metric`. It then
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
reads the eval corpus (`dataset/dev.jsonl`) and the targets in `skill_eval.py` to
find the cases that cover each facet. `facets.json` holds one record per
facet. `FACETS.md` shows the same data as tables, with a legend for each
facet kind. Do not edit either file by hand.

A single-skill route takes its handles from the skill's own `SKILL.md`. A step is a list
item that starts with a handle (``1. `1-name`: ...``) or a heading that is a handle
(`## 1-name`). Other numbered lists are not steps. Items belong to the nearest `##` heading
above them. A skill with one such list has `handles`. A skill with several has `modes`,
keyed by the heading in lowercase with hyphens and without a trailing "mode" (`## Drive to
green` is `drive-to-green`, `## Maintain mode` is `maintain`), and its `handles` is empty. Handles
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
order. This verifies harness behavior only. `test_run_eval.py` runs `run_eval.py` against a stub
`claude` that writes a kept sandbox like the real CLI. It checks that a run passes the frozen tool
and effort flags, keeps the transcript and stream, records the added final newline, takes the final
files from the agent's working folder, and leaves no hooks in a `hook-off` suite; that `score`
scores each arm from the kept files and can run again; that a rerun launches nothing and an
interrupted run moves aside and counts at the stop amount; that the total budget stops a launch
before it starts; that a run over the per-run stop, a session with a wrong tool set, and a
session with the wrong effort or CLI version each stop the batch and are not scored; that
parallel workers count a run in flight once, and a resume counts each stale run folder while
workers reserve; that the runner's own timeout scores as a timeout; and that a different
configuration needs a new output folder. `test_facets.py` runs `facets.py`
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
message spans several lines, plus the 2.1.327 `silent_turn_reminder` attachment, a fixed
harness nudge to update the user. A shape the audit did
not see is a counted warning, unless it may hold a skill load; EVIDENCE.md states the rule. It supports `Skill`-tool loads, by full or bare name, proved
by the linked delivered body, full `Read` reads of frozen `SKILL.md` and plugin resource files
(playbooks and references named in `facets.json`), root versus subagent records (`child_loads` and
`child_resource_reads`), `Bash` commands mentioning frozen paths in `unproved_reads`,
labeled action timing, and end coverage from stream-json. A `Skill` call with
arguments counts when Claude Code appended them to the body as
`ARGUMENTS: <args>`. A load also counts when Claude Code filled the body's `$NAME` or `${NAME}`
placeholders, such as `$ARGUMENTS` or `${CLAUDE_SESSION_ID}`; EVIDENCE.md states the rule. It does not support typed slash-command loads, compaction, resumes,
repeat-load notes, Codex traces, unlabeled actions, or step-list extraction.
These leave the session partial or the load unproved; they never count as a
miss. EVIDENCE.md holds the contract and the raw-event audit.

Native runs go through `run_eval.py` (see "Plugin-eval runner") with the owner-approved runtime
in `runtime.plugin-eval.json`. Run the canaries and read their streams before a baseline. Do not
assume that stripping bindings disables manual external calls; the canaries check the sandbox.

Sources: the private source chat, especially its final two eval turns; the repository's current skill contracts; and OpenAI's
[skill eval guidance](https://developers.openai.com/blog/eval-skills). The supplied
[X post](https://x.com/samzliu/status/2103613396625367437) returned HTTP 403 during
this implementation and supplied no independently verified claim.
