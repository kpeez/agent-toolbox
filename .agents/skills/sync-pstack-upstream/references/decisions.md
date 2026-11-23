# pstack decisions

This log records why swe differs from pstack. `upstream.json` records
which swe files hold each pstack file. This file records the reason.

Add an entry when a sync, or a swe change, renames, merges, drops, or
replaces pstack content, or skips an upstream change on purpose. Write one
line for each entry, with the issue key or the commit that made the change.
Do not record a skipped wording change.

## Renamed or merged skills

| pstack | swe | Why | Commit |
| --- | --- | --- | --- |
| `poteto-mode` | `swe-mode` and the SessionStart hook | swe name. The hook replaces the Cursor Custom Mode. | `26ee9c5`, `3ea3f44` |
| `poteto-help` | `help` | swe name. | `3ea3f44` |
| `sharpen` | `go-deeper` | go-deeper frames each new task and then does it. It also has a prompt-only mode. One copy each in swe, lab, and uni. | `2f116c1` |
| `show-me-your-work` | `log-decisions` | swe names skills with verbs. JSONL log, not TSV. | `a75b34e` |
| `bro` | `wait-what` | Existing swe name. | `26ee9c5` |
| `tdd` | `verifying-work` | swe already had a test skill, then named `testing-code`. The skill was renamed to `verifying-work`. The failing-test-first cadence is merged into it. | `26ee9c5` |
| `technical-writing`, `unslop` | `writing` | One writing hub with prose, ASD-STE100, and show-me references. | `500049d` |
| `create-verification-skill`, `maintain-verification-skill` | `verification-skill` | One skill creates the skill, or audits it when it exists. | `26ee9c5` |
| `interrogate` | `references/review-brief.md` | Cross-model review adds little when only Claude runs. Callers start a fresh reviewer subagent with the brief. | `d6b488c` |
| `docs/guide/02-poteto-mode.md` | swe `README.md` Usage section | The swe README carries the full routing detail. Sequence diagram, not flowchart. | `ff63b2a` |

## Dropped

| pstack | Why | Commit |
| --- | --- | --- |
| `arena` | Dropped. The eval playbook runs candidates and the blinded judge through `swarm`. | `26ee9c5` |
| `teach` | The uni plugin owns teaching. | `26ee9c5` |
| `agents/poteto-agent.md` (swe `daedalus`) | Code delegates are native subagents. The router picks each model, and `worker.md` holds the delegate rules. | `0470d8b` |
| `automate-me`, `make-bot-ui` | Persona and Cursor UI. | `26ee9c5` |
| `setup-pstack` | Cursor setup. swe installs as a plugin. | `26ee9c5` |
| `poteto-mode/scripts/` (`watch-pr`, `orch`, `bootstrap.ts`, bun files) | Cursor, Origin, and Graphite tooling. swe uses `gh` and its own scripts. | `26ee9c5` |
| `show-me-your-work` TSV template | `log-decisions` writes JSONL. | `a75b34e` |
| `show-me-your-work/scripts/log.sh` | The model appends `log-decisions` rows itself, and the handoff posts them to the tracker issue. No script writes the log. | `9be7388` |
| `docs/harness/` | swe is written for Claude Code and Codex already. | `1fb1eab` |
| `assets/`, `automations/`, `docs/guide/images/`, plugin manifests | Cursor packaging. | `d8a4e5e` |

## Imported as is

| pstack | Why | Commit |
| --- | --- | --- |
| `statechart` | Imported on owner approval. Node scripts kept, not ported to Python: upstream code keeps its own language. Class `copied`. | `07702a5` |
| `ketchup-video` | Imported on owner approval. Class `copied`. | `d0990d4` |
| `statechart` TypeScript compiler (cursor/plugins#977) | Full tree imported with the test corpus, on owner approval. It replaces the 26 `.mjs` scripts. Class `copied`. | `ef381fe` |
| `poteto-mode/worker.md` (cursor/plugins#1249) | Imported on owner approval as `swe-mode/worker.md`. Upstream's reason: the rules live in skills a started agent does not load, so they reach it only through its brief. Its PR rules point at `ship-pr` (draft first, the body template), not upstream's ready PRs and six headings. Class `modified`. | `b130007` |

## Deleted swe content

| swe | Why | Commit |
| --- | --- | --- |
| `swe-mode/references/run-program.md` (program store, inbox, ledger, frontier) | Upstream made orchestrate agentic (cursor/plugins#1043). Port and deletion made on owner approval. | `ef381fe` |
| `why` lanes, synthesizer, confidence tiers, and `why/references/` | Upstream cut `why` to one short file that names no source (cursor/plugins#1236). It reads the commits and PR discussions first and other sources only when that trail is thin. | `b130007` |
| `how` explorers, `how/references/`, and every route to `how` | Upstream cut `how` to one subagent and stopped routing to it (cursor/plugins#1236). Playbooks trace the code directly. | `b130007` |
| `reflect` reviewers, synthesizer, and `reflect/references/` | Upstream made `reflect` one file with no subagents (cursor/plugins#1249). | `b130007` |
| `architect` phases and `architect/references/` | Upstream cut `architect` to a short brief (cursor/plugins#1249). | `b130007` |
| `run-program` playbook | Upstream deleted Orchestrate (cursor/plugins#1249). `figure-it-out` takes program-scale work. | `b130007` |
| `scripts/check_plan.py` and `swe-mode/references/plan-multi-phase.md` | Upstream cut the plan playbook to five steps and deleted `check-plan.mjs` (cursor/plugins#1249). | `b130007` |
| `principle-model-the-domain` "Find implicit state machines" section | Cut to one sentence with the upstream principle cut (cursor/plugins#1249). | `b130007` |

## Skipped upstream changes

| Upstream change | Why | Commit |
| --- | --- | --- |
| `sharpen` returns only the rewritten prompt (cursor/plugins#729) | `go-deeper` frames and then does the task. Its prompt-only mode already covers the rewrite. | `07702a5` |
| `sharpen` drops the rewritten-prompt ban | `go-deeper` already gives the rewrite on request. | `72ab388` |
| `reflect`: never open a PR or push after a skill edit (cursor/plugins#800) | swe defaults allow task-scoped commits and draft PRs. swe ports only the rule against edits in a plugin cache. | `d0990d4` |
| `interrogate`: adversaries keep only findings a run proves (cursor/plugins#986) | swe dropped `interrogate`. The review brief also serves prose and design reviews, where a run cannot prove a finding. | `ef381fe` |
| `poteto-mode`: `run_in_background: true` on a steer or resume (cursor/plugins#986) | Claude Code runs subagents in the background by default. Codex has no such flag. | `ef381fe` |
| Model defaults: Opus 5.5 first, Fable 5.2 only on request or after two failures, a cap at xhigh, `-fast` slugs, and another vendor for a second opinion (cursor/plugins#1236, cursor/plugins#1249) | swe skills name no model or vendor. | `b130007` |

## Different defaults

| pstack | swe | Why | Commit |
| --- | --- | --- | --- |
| `poteto-mode` Autonomy and `opening-a-pr`: PRs open ready; merge only in Shipping on request | `ship-pr` Publication authority: an implementation request covers commits, pushes, a draft PR, and a merge without review once verified and checks pass; local-only or a hold point overrides | The rule moved from global agent rules into swe (dotfiles#73). | `c57bc85` |
| `bug-fix` playbook: no step encodes the bug; `correct` counts a class at its second occurrence | `fix-bug` step `10-encode-bug-class` turns a bug that the code alone shows into a type, lint rule, or check; `correct` counts such a bug at its first occurrence | swe turns each found bug into a lint rule. | `3c3bae7` |
| `poteto-mode` first-message trigger: open each PR's `## Why` with the user's goal (ported in `ef381fe`) | The goal restatement stays in the chat and subagent briefs. `ship-pr` builds the PR body from `templates/pr-body.md` with `pr_body.ts render`, and a `PreToolUse` hook blocks any other body | The ported clause made PR bodies open with `## Why` and requester attribution (`3c3bae7`, `c42ce5c`). Do not port it again. | `e54e7c6` |
| `principle-model-the-domain`: the stance only, for new code | `principle-model-the-domain` adds one sentence: look for state machines nobody wrote down in existing code before you add a branch | swe looks for implicit state machines in existing code, not only in new code. The longer section (`4524155`) was cut to this sentence. | `4524155`, `b130007` |
| `autopilot-stack`, `shipping`, and `opening-a-pr`: hand-chained `gh pr create --base` and one-by-one merge | `autopilot-stack.md`, `ship-stack.md`, and `ship-pr/SKILL.md` use `gh stack link` to publish stacks and `gh stack merge --squash` for a fully verified stack, keeping plain `gh` base chaining only as a fallback when `gh stack` is unavailable | Prevents hand-chained `--base` PRs that omit a GitHub stack, enforced by `pr_body.ts hook`. Departs from pstack on purpose; keep on sync. | KP-589 |
| `poteto-mode` todo list: a skipped step no longer stays as `skip: <reason>` (cursor/plugins#1249) | `swe-mode` ends the reply with a Steps section, each handle `done` or `skip:` with a reason | The route eval in `evals/skills` reads the Steps section to score whether an agent followed its route (`e0358d4`). | `b130007` |
| `architect` sends a large or contested design to `arena` | `architect` sends it to `codebase-design` design mode | swe has no `arena`. `codebase-design` compares materially different interfaces. | `b130007` |
