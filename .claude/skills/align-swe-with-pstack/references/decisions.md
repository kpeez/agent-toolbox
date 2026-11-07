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
| `teach` | The uni plugin owns teaching. | #174 |
| `automate-me`, `make-bot-ui` | Persona and Cursor UI. | #174 |
| `setup-pstack` | Cursor setup. swe installs as a plugin. | #174 |
| `poteto-mode/scripts/` (`watch-pr`, `orch`, `bootstrap.ts`, bun files) | Cursor, Origin, and Graphite tooling. swe uses `gh` and its own Python scripts. | #174 |
| `why/references/sources/` for Databricks, Datadog, Notion, Sentry, incident postmortems | swe `why` uses git history, Linear, Slack, and project docs. | #179 |
| `show-me-your-work` TSV template | `log-decisions` writes JSONL. | #171 |
| `docs/harness/` | swe is written for Claude Code and Codex already. | #190 |
| `assets/`, `automations/`, `docs/guide/images/`, plugin manifests | Cursor packaging. | #179 |

## Imported as is

| pstack | Why | PR |
| --- | --- | --- |
| `statechart` | Imported on owner approval. Node scripts kept, not ported to Python: upstream code keeps its own language. Class `copied`. | #198 |
| `ketchup-video` | Imported on owner approval. Class `copied`. | #200 |
| `statechart` TypeScript compiler (cursor/plugins#977) | Full tree imported with the test corpus, on owner approval. It replaces the 26 `.mjs` scripts. Class `copied`. | #201 |

## Deleted swe content

| swe | Why | PR |
| --- | --- | --- |
| `swe-mode/references/run-program.md` (program store, inbox, ledger, frontier) | Upstream made orchestrate agentic (cursor/plugins#1043). Port and deletion made on owner approval. | #201 |

## Skipped upstream changes

| Upstream change | Why | PR |
| --- | --- | --- |
| `sharpen` returns only the rewritten prompt (cursor/plugins#729) | `go-deeper` frames and then does the task. Its prompt-only mode already covers the rewrite. | #198 |
| `sharpen` drops the rewritten-prompt ban | `go-deeper` already gives the rewrite on request. | #193 |
| `reflect`: never open a PR or push after a skill edit (cursor/plugins#800) | swe defaults allow task-scoped commits and draft PRs. swe ports only the rule against edits in a plugin cache. | #200 |
| `interrogate`: adversaries keep only findings a run proves (cursor/plugins#986) | swe dropped `interrogate`. The review brief also serves prose and design reviews, where a run cannot prove a finding. | #201 |
| `poteto-mode`: `run_in_background: true` on a steer or resume (cursor/plugins#986) | Claude Code runs subagents in the background by default. Codex has no such flag. | #201 |

## Different defaults

| pstack | swe | Why | PR |
| --- | --- | --- | --- |
| `poteto-mode` Autonomy and `opening-a-pr`: PRs open ready; merge only in Shipping on request | `ship-pr` Publication authority: an implementation request covers commits, pushes, a draft PR, and a merge without review once verified and checks pass; local-only or a hold point overrides | The rule moved from global agent rules into swe (dotfiles#73). | #203 |
| `bug-fix` playbook: no step encodes the bug; `correct` counts a class at its second occurrence | `fix-bug` step `10-encode-bug-class` turns a bug that the code alone shows into a type, lint rule, or check; `correct` counts such a bug at its first occurrence | swe turns each found bug into a lint rule. | #207 |
| `poteto-mode` first-message trigger: open each PR's `## Why` with the user's goal (ported in #201) | The goal restatement stays in the chat and subagent briefs. `ship-pr` builds the PR body from `templates/pr-body.md` with `pr_body.py render`, and a `PreToolUse` hook blocks any other body | The ported clause made PR bodies open with `## Why` and requester attribution (#207, #212). Do not port it again. | fix/pr-body-guard |
