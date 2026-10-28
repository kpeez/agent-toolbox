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
| `show-me-your-work` | `log-decisions` | Kyle wants verb names. JSONL log, not TSV. | #171 |
| `bro` | `wait-what` | Existing swe name. | #174 |
| `tdd` | `testing-code` | swe already had a test skill. The failing-test-first cadence is merged into it. | #174 |
| `technical-writing`, `unslop` | `writing` | One writing hub with prose, ASD-STE100, and show-me references. | #176 |
| `create-verification-skill`, `maintain-verification-skill` | `verification-skill` | One skill creates the skill, or audits it when it exists. | #174 |
| `interrogate` | `references/review-brief.md` | Cross-model review adds little when only Claude runs. Callers start a fresh reviewer subagent with the brief. | #175 |

## Dropped

| pstack | Why | PR |
| --- | --- | --- |
| `arena` | Kyle dropped it. The eval playbook runs candidates and the blinded judge through `swarm`. | #174 |
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
| `statechart` | Kyle approved. Node scripts kept, not ported to Python: upstream code keeps its own language. Class `copied`. | #198 |
| `ketchup-video` | Kyle approved. Class `copied`. | #200 |
| `statechart` TypeScript compiler (cursor/plugins#977) | Kyle approved the full tree with the test corpus. It replaces the 26 `.mjs` scripts. Class `copied`. | #201 |

## Deleted swe content

| swe | Why | PR |
| --- | --- | --- |
| `swe-mode/references/run-program.md` (program store, inbox, ledger, frontier) | Upstream made orchestrate agentic (cursor/plugins#1043). Kyle approved the port and the deletion. | #201 |

## Skipped upstream changes

| Upstream change | Why | PR |
| --- | --- | --- |
| `sharpen` returns only the rewritten prompt (cursor/plugins#729) | `go-deeper` frames and then does the task. Its prompt-only mode already covers the rewrite. | #198 |
| `sharpen` drops the rewritten-prompt ban | `go-deeper` already gives the rewrite on request. | #193 |
| `reflect`: never open a PR or push after a skill edit (cursor/plugins#800) | swe defaults allow task-scoped commits and draft PRs. swe ports only the rule against edits in a plugin cache. | #200 |
| `interrogate`: adversaries keep only findings a run proves (cursor/plugins#986) | swe dropped `interrogate`. The review brief also serves prose and design reviews, where a run cannot prove a finding. | #201 |
| `poteto-mode`: `run_in_background: true` on a steer or resume (cursor/plugins#986) | Claude Code runs subagents in the background by default. Codex has no such flag. | #201 |
