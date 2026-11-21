# pstack decisions

This log records why swe differs from pstack. `upstream.json` records
which swe files hold each pstack file. This file records the reason.

Add an entry when a sync, or a swe change, renames, merges, drops, or
replaces pstack content, or skips an upstream change on purpose. Write one
line for each entry, with the PR. Do not record a skipped wording change.

## Renamed or merged skills

| pstack | swe | Why | PR |
| --- | --- | --- | --- |
| `poteto-mode` | `swe-mode` and the SessionStart hook | swe name. The hook replaces the Cursor Custom Mode. | #174, #182 |
| `poteto-help` | `help` | swe name. | #182 |
| `sharpen` | `go-deeper` | go-deeper frames each new task and then does it. It also has a prompt-only mode. One copy each in swe, lab, and uni. | #192 |
| `show-me-your-work` | `log-decisions` | swe names skills with verbs. JSONL log, not TSV. | #171 |
| `bro` | `wait-what` | Existing swe name. | #174 |
| `tdd` | `testing-code` | swe already had a test skill. The failing-test-first cadence is merged into it. | #174 |
| `technical-writing`, `unslop` | `writing` | One writing hub with prose, ASD-STE100, and show-me references. | #176 |
| `create-verification-skill`, `maintain-verification-skill` | `verification-skill` | One skill creates the skill, or audits it when it exists. | #174 |
| `interrogate` | `references/review-brief.md` | Cross-model review adds little when only Claude runs. Callers start a fresh reviewer subagent with the brief. | #175 |
| `docs/guide/02-poteto-mode.md` | swe `README.md` Usage section | The swe README carries the full routing detail. Sequence diagram, not flowchart. | #202 |

## Dropped

| pstack | Why | PR |
| --- | --- | --- |
| `arena` | Dropped. The eval playbook runs candidates and the blinded judge through `swarm`. | #174 |
| `orchestrate` (cursor/plugins#1043, deleted upstream in #1249) | Not imported again. Its planner rules already live in swe: `swe-mode` Subagents, `plan-multi-phase`, `figure-it-out`, and `swarm`. KP-599 adds two coordinator bullets to `swe-mode` instead. | KP-599 |
| `teach` | The uni plugin owns teaching. | #174 |
| `automate-me`, `make-bot-ui` | Persona and Cursor UI. | #174 |
| `setup-pstack` | Cursor setup. swe installs as a plugin. | #174 |
| `poteto-mode/scripts/` (`watch-pr`, `orch`, `bootstrap.ts`, bun files) | Cursor, Origin, and Graphite tooling. swe uses `gh` and its own scripts. | #174 |
| `show-me-your-work` TSV template | `log-decisions` writes JSONL. | #171 |
| `show-me-your-work/scripts/log.sh` | The model appends `log-decisions` rows itself, and the handoff posts them to the tracker issue. No script writes the log. | #24 |
| `docs/harness/` | swe is written for Claude Code and Codex already. | #190 |
| `assets/`, `automations/`, `docs/guide/images/`, plugin manifests | Cursor packaging. | #179 |

## Imported as is

| pstack | Why | PR |
| --- | --- | --- |
| `statechart` | Imported on owner approval. Node scripts kept, not ported to Python: upstream code keeps its own language. Class `copied`. | #198 |
| `ketchup-video` | Imported on owner approval. Class `copied`. | #200 |
| `statechart` TypeScript compiler (cursor/plugins#977) | Full tree imported with the test corpus, on owner approval. It replaces the 26 `.mjs` scripts. Class `copied`. | #201 |
| `poteto-mode/worker.md` (cursor/plugins#1249) | Imported on owner approval as `swe-mode/worker.md`. Upstream's reason: the rules live in skills a started agent does not load, so they reach it only through its brief. Its PR rules point at `ship-pr` (draft first, the body template), not upstream's ready PRs and six headings. Class `modified`. | #238 |

## Deleted swe content

| swe | Why | PR |
| --- | --- | --- |
| `swe-mode/references/run-program.md` (program store, inbox, ledger, frontier) | Upstream made orchestrate agentic (cursor/plugins#1043). Port and deletion made on owner approval. | #201 |
| `why` lanes, synthesizer, confidence tiers, and `why/references/` | Upstream cut `why` to one short file that names no source (cursor/plugins#1236). It reads the commits and PR discussions first and other sources only when that trail is thin. | #238 |
| `how` explorers, `how/references/`, and every route to `how` | Upstream cut `how` to one subagent and stopped routing to it (cursor/plugins#1236). Playbooks trace the code directly. | #238 |
| `reflect` reviewers, synthesizer, and `reflect/references/` | Upstream made `reflect` one file with no subagents (cursor/plugins#1249). | #238 |
| `architect` phases and `architect/references/` | Upstream cut `architect` to a short brief (cursor/plugins#1249). | #238 |
| `run-program` playbook | Upstream deleted Orchestrate (cursor/plugins#1249). `figure-it-out` takes program-scale work. | #238 |
| `scripts/check_plan.py` and `swe-mode/references/plan-multi-phase.md` | Upstream cut the plan playbook to five steps and deleted `check-plan.mjs` (cursor/plugins#1249). | #238 |
| `principle-model-the-domain` "Find implicit state machines" section | Cut to one sentence with the upstream principle cut (cursor/plugins#1249). | #238 |

## Skipped upstream changes

| Upstream change | Why | PR |
| --- | --- | --- |
| `sharpen` returns only the rewritten prompt (cursor/plugins#729) | `go-deeper` frames and then does the task. Its prompt-only mode already covers the rewrite. | #198 |
| `sharpen` drops the rewritten-prompt ban | `go-deeper` already gives the rewrite on request. | #193 |
| `reflect`: never open a PR or push after a skill edit (cursor/plugins#800) | swe defaults allow task-scoped commits and draft PRs. swe ports only the rule against edits in a plugin cache. | #200 |
| `interrogate`: adversaries keep only findings a run proves (cursor/plugins#986) | swe dropped `interrogate`. The review brief also serves prose and design reviews, where a run cannot prove a finding. | #201 |
| `poteto-mode`: `run_in_background: true` on a steer or resume (cursor/plugins#986) | Claude Code runs subagents in the background by default. Codex has no such flag. | #201 |
| Model defaults: Opus 5.5 first, Fable 5.2 only on request or after two failures, a cap at xhigh, `-fast` slugs, and another vendor for a second opinion (cursor/plugins#1236, #1249) | swe skills name no model or vendor. | #238 |

## Different defaults

| pstack | swe | Why | PR |
| --- | --- | --- | --- |
| `poteto-mode` Autonomy and `opening-a-pr`: PRs open ready; merge only in Shipping on request | `ship-pr` Publication authority: an implementation request covers commits, pushes, a draft PR, and a merge without review once verified and checks pass; local-only or a hold point overrides | The rule moved from global agent rules into swe (dotfiles#73). | #203 |
| `bug-fix` playbook: no step encodes the bug; `correct` counts a class at its second occurrence | `fix-bug` step `10-encode-bug-class` turns a bug that the code alone shows into a type, lint rule, or check; `correct` counts such a bug at its first occurrence | swe turns each found bug into a lint rule. | #207 |
| `poteto-mode` first-message trigger: open each PR's `## Why` with the user's goal (ported in #201) | The goal restatement stays in the chat and subagent briefs. `ship-pr` builds the PR body from `templates/pr-body.md` with `pr_body.ts render`, and a `PreToolUse` hook blocks any other body | The ported clause made PR bodies open with `## Why` and requester attribution (#207, #212). Do not port it again. | #214 |
| `principle-model-the-domain`: the stance only, for new code | `principle-model-the-domain` adds one sentence: look for state machines nobody wrote down in existing code before you add a branch | swe looks for implicit state machines in existing code, not only in new code. The longer section (#215) was cut to this sentence. | #215, #238 |
| `autopilot-stack`, `shipping`, and `opening-a-pr`: hand-chained `gh pr create --base` and one-by-one merge | `autopilot-stack.md`, `ship-stack.md`, and `ship-pr/SKILL.md` use `gh stack link` to publish stacks and `gh stack merge --squash` for a fully verified stack, keeping plain `gh` base chaining only as a fallback when `gh stack` is unavailable | Prevents hand-chained `--base` PRs that omit a GitHub stack, enforced by `pr_body.ts hook`. Departs from pstack on purpose; keep on sync. | KP-589 |
| `poteto-mode` todo list: a skipped step no longer stays as `skip: <reason>` (cursor/plugins#1249) | `swe-mode` ends the reply with a Steps section, each handle `done` or `skip:` with a reason | The route eval in `evals/skills` reads the Steps section to score whether an agent followed its route (#235). | #238 |
| `architect` sends a large or contested design to `arena` | `architect` sends it to `codebase-design` design mode | swe has no `arena`. `codebase-design` compares materially different interfaces. | #238 |
