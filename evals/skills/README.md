# Offline skill activation evals

This is an offline-ready first slice, not a measured baseline. It evaluates
activation evidence independently of task utility. No provider is invoked,
and no dashboard, database, package installation, or global settings are needed.

The corpus has 127 authored scenarios. Eighty are swe cases in the 4/2/3/1 mix: ten each for `swe-mode`, `implement`, `diagnose`,
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
the same fixture. Six of them set `expected_route`, the route the agent should
pick, and the scorer checks whether the agent followed it (see "Route scoring").
The others set no route.

The two route-choice families, `swe-route-choice` (21 cases) and `lab-route-choice` (6 cases), cover
each playbook and single-skill route that no other case covers, with one case per route. They have
no fixed mix: `validate` rejects a negative case, and a case with no `expected_route`, in an open family, because a route-choice case scores one route. A negative in a mix family may set `expected_route`. Every
case instead resembles a neighbouring route and belongs to its own: the `rationale` names the
near miss. Cases on a route with modes set `expected_mode`. A route-choice case holds one correct
route that the router's own text supports, and its fixture holds every input that the task names.
For example, `swe-route-diagnose-runtime` runs a worker script that spins, `swe-route-ship-pr` has a conflicted
`receipt.py`, and `lab-route-maintain-project-skills` has project skills and a renamed column. Where two router lines overlap, such as the PR-status
trigger and the `ship-pr` route, the case uses wording that only one of them matches.

Three routes have no case. `ketchup` needs commit history, `reflect` needs a past session, and `ship-stack`
needs open PRs and their CI. A workspace is a copy of the fixture plus a fresh `git init` with no commits, remote, or
past sessions, so it holds none of these. Their cases wait until the setup can build that state.

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
  and `SP-10` (commit finished work and open a draft PR), `SP-04` (land an approved PR), and
  `lab-mode-rename-column`. `IM-01` and the other requests that leave a design or a cause open stay allowed.
- A follow-up inside a framed task: the last user turn continues the work that an earlier assistant turn did. These
  are `SP-05` (commit what the earlier turn reported complete), `SP-06` (fix what it diagnosed),
  and `swe-mode-pause-safely`. A user turn that opens a new task after an answer is
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
