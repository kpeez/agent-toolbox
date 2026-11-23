---
name: verify-plugin-rollout
description: Model-check the plugin rollout with TLA+ (TLC) - PRs that change plugin folders and catalogs, the required CI checks, the merge, and the update of each Claude Code config folder and Hermes profile - in every order of steps. Use when a change touches the install or update steps in the READMEs, docs/contributing.md, the marketplace catalogs, or plugin_catalogs.py, plugin_isolation.py, or manifest_versions.py, or when the check fails.
paths:
  - README.md
  - plugins/swe/README.md
  - plugins/lab/README.md
  - plugins/uni/README.md
  - docs/contributing.md
  - .claude-plugin/marketplace.json
  - .agents/plugins/marketplace.json
  - .github/scripts/plugin_catalogs.py
  - .github/scripts/plugin_isolation.py
  - .github/scripts/manifest_versions.py
---

# Verify the plugin rollout

A plugin change reaches a user in two parts. First, a PR changes the tree on
`main`, and the required `repo-checks` job gates the merge. Then the operator
updates each config folder of each agent host: each Claude Code config folder
(each `CLAUDE_CONFIG_DIR`) and each Hermes profile.

The promise: after the documented update steps, every config folder loads the
merged commit, no folder loads an agent's uncommitted edits, and `main` has
catalogs that match the plugin folders and no plugin that names another
plugin's skill.

## The rules

`PluginRollout.tla` checks each rule in every state that the steps can reach.

| Rule | Plain sentence | Harm when it breaks |
| --- | --- | --- |
| `DocStepsReachEveryFolder` | After the operator runs every documented update step, every config folder loads the merged commit. | A session in a stale folder runs old skills and hooks, and nobody knows. |
| `NeverLoadsUncommittedEdits` | No config folder loads edits that are not on `main`. | An agent's unreviewed edits become the skills of every session. |
| `FoldersListed` | Each catalog lists each plugin folder. | That host cannot install the plugin. |
| `EntriesPointAtFolders` | Each catalog entry points at a plugin folder that exists. | The install of that entry fails. |
| `NoCrossPluginNames` | No plugin names a skill of another plugin. | A user who installed one plugin is sent to a skill that does not exist. |

## Run it

From the repository root:

```sh
uv run .agents/skills/verify-plugin-rollout/scripts/check.py
```

It needs uv and mise. It uses the statechart skill's pinned TLC and Java
through `.github/scripts/statechart_tlc.py`, or `TLA2TOOLS` and `JAVA` when
they are set. It runs the 13 runs in `RUNS` in parallel, in about 5 s. CI
runs it in the `plugin-rollout-model-check` job. It exits 0 only when each
run gives its expected result:

- `holds`: each listed rule holds on today's protocol.
- `finding`: a known hole in today's protocol still breaks its rule.
- `past bug`: the protocol before a past fix breaks the rule that the fix
  restored.
- `mutant`: a broken check breaks a rule that no past bug broke.

For each rule that breaks, it prints TLC's shortest path as a list of
actions, each with its PR and change or its config folder. `--keep` keeps
the TLC configs.

Read every result, and draw the rollout, with the `statechart` skill. Give
it `PluginRollout.tla`, `chart.cfg`, and the view `chart-view.mjs`.
`chart/chart.mmd` and `chart/report.md` are its output for `chart.cfg`: one
PR that edits a plugin, two Claude Code config folders, and one Hermes
profile (60 states). The chart marks the state where the README steps are
done and the second Claude Code folder is stale. The check runs the
constants of `chart.cfg` as two runs, so a constant that the chart config
leaves out fails the check.

## Findings in today's protocol

The check keeps each finding as a `finding` run, so a fix shows up as a
failing run. When a fix lands, move its run to `holds`.

- **The Claude Code update steps reach only the active config folder.**
  `DocStepsReachEveryFolder`. The README steps run
  `claude plugin marketplace update` and `claude plugin update` and name no
  config folder, so they act on the folder of the shell's
  `CLAUDE_CONFIG_DIR`. Each config folder has its own
  `installed_plugins.json` and plugin cache. The Hermes steps say "for each
  profile"; the Claude Code steps do not. This happened on 2026-11-18: one
  rollout updated only the active folder of a host with three. A replay on
  Claude Code 2.1.330 with two scratch config folders and a scratch git
  marketplace: after the README steps in one folder, that folder loaded the
  new commit and the other kept the old one.
- **Two PRs that pass the checks on different bases can merge into a broken
  `main`.** `FoldersListed` and `NoCrossPluginNames`. The `main-protection`
  ruleset requires `repo-checks` but not an up-to-date branch
  (`strict_required_status_checks_policy` is false). GitHub runs the checks
  on the PR merged into `main` as `main` was then. A replay with real git
  squash merges and the real check scripts: a PR that deletes `plugins/uni`
  and its catalog entries passes, a PR that adds a skill file under
  `plugins/uni` passes, and after both merge, `plugin_catalogs.py` fails with
  `add an entry for plugins/uni`. In the same way, a PR that adds a plugin
  `newp` passes, a PR that adds `newp:helper` to a swe skill passes (no
  folder `newp` yet), and after both merge, `plugin_isolation.py` fails. The
  `push` run of `checks` on `main` shows the break, but only after the
  merge.

## Past bugs

Each variant is the protocol before its fix.

- `versionKey`, 2352b4b (2026-07-16), fixed by f02383d: Claude Code
  keyed updates on the manifest `version`. A PR changed content and kept the
  version, so `claude plugin update` said `already at the latest version`.
  The same replay shows it on a plugin with `"version": "1.0.0"`.
- `externalDirs`, 2026-11-19, fixed by 94537ee: Hermes read the
  checkout's skills through `skills.external_dirs`, and an agent's edits in
  the checkout became the loaded skills.
- `noCatalogCheck`, 7bbb754 (2026-07-16), fixed by 0f729df: a new plugin was
  listed in the Claude Code catalog only. `plugin_catalogs.py` on 7bbb754
  prints `add an entry for plugins/llmos` and exits 1.
- `noIsolationCheck`, before 3cb84a7 (2026-11-15): swe, lab, and uni named
  each other's skills. `plugin_isolation.py` on 3cb84a7's parent finds 7
  references and exits 1.
- The mutant `listedOnlyCheck` drops the half of `plugin_catalogs.py` that
  checks that each entry points at a folder.

## How the model maps to the protocol

| Action | Protocol |
| --- | --- |
| `PrOpens(p)` | A PR with one change from `AllDiffs`, which merges with no git conflict at that time. |
| `ChecksRun(p)` | `repo-checks` on the PR merged into `main` as it is now: `plugin_catalogs.py` lines 33 to 57 (`FoldersListed`, `EntriesPointAtFolders`) and `plugin_isolation.py` lines 22 to 39 (`NoCrossPluginNames`). |
| `PrMerges(p)` | A squash merge with green checks. The ruleset does not require a current base. |
| `ClaudeUpdates(d)` | `plugins/swe/README.md` lines 48 to 49: `claude plugin marketplace update`, then `claude plugin update`, in one config folder. The key is the marketplace HEAD SHA (`docs/contributing.md` line 25), or the manifest version in `versionKey`. |
| `HermesInstalls(d)` | `README.md` lines 54 to 69: `hermes -p <profile> plugins install … --ref <sha> --force` for each profile. |
| `AgentEditsCheckout`, `CheckoutPulls` | An agent edits the live checkout; the checkout pulls `main`. |

`Documented(d)` holds the steps that the docs give: the active Claude Code
folder, and each Hermes profile. `manifest_versions.py` keeps `version` out of
the manifests, so today's runs have no `editCoreBump` change.

### Bounds

One or two Claude Code config folders, one or two Hermes profiles, one or
two PRs, and two plugins: `core`, which every tree has and whose edits the
rollout ships, and `extra`, which PRs add and remove. Each PR merges at most
once.

### Assumptions

- The two README update commands run as one step.
- A new file under a deleted folder merges with no conflict. A PR that adds a
  folder that exists, or deletes one that is gone, conflicts.
- A plugin folder exists when its manifest exists.

### Left out

Codex (it reinstalls every plugin when the marketplace commit changes, also
at session start), agy (one folder; reinstall copies the files), and
`npx skills`. A session restart: the model checks what a new session loads.
The hook-runtime rules of `hook_runtime.py`. A failed update, such as the
Codex LFS timeout.

## Coverage

| Protocol | Actions |
| --- | --- |
| `README.md`, and the update steps in `plugins/{swe,lab,uni}/README.md` | `ClaudeUpdates`, `HermesInstalls` |
| `docs/contributing.md` "Versions", `manifest_versions.py` | the update key in `ClaudeUpdates` |
| `.github/scripts/plugin_catalogs.py`, `plugin_isolation.py` | `Gate`, `ChecksRun` |
| The `main-protection` ruleset | `PrMerges` |

Sync commit: the commit that adds this skill (`git log --diff-filter=A --
.agents/skills/verify-plugin-rollout/SKILL.md`). Move it forward only after
you confirm that the model describes the protocol at the new commit.

The check does not read the docs or run the scripts. A change to a covered
file passes the check until someone changes the model to match. So after
such a change, update the action first, then run the check.

## When the check fails

1. A `holds` run that fails: read the path with the `statechart` skill, and
   replay it against the real steps, in scratch config folders and a scratch
   git repository. When every step happens, the change has a bug. When a
   step cannot happen, fix the action, not the rule.
2. A `finding` run that fails: the change closed the hole. Move the run to
   `holds`, and remove the finding from this file.
3. A `past bug` or `mutant` run that fails: the model no longer reaches that
   bug. Check that the variant still matches the old protocol.
4. "TLC failed": a parse or config error. Read the output that it prints.
