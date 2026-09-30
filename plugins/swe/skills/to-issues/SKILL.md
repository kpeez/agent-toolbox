---
name: to-issues
description: Split a large approved plan into pull-request-sized issues with dependencies on Linear or GitHub. Not for drafting plans or executing work.
---

# /to-issues

Most plans need one issue or none. Split only when the work needs several pull
requests that can be reviewed, verified, or sequenced independently. Do not
split for bookkeeping; check the selected tracker's current limits if they
matter to the proposed breakdown.

## Tracker

Use the tracker the user names, otherwise the one pinned in the repository's
`AGENTS.md`, `CLAUDE.md`, or `.agents/docs/CONTEXT.md` (for example
`Issue tracker: linear`), otherwise ask. Never infer the tracker from where the
code is hosted. Use the Linear connection for Linear and `gh` for GitHub. An
unavailable or unsupported tracker is a limitation to report, not a reason to
switch trackers.

Creating issues changes external state. Present the breakdown first and create
issues only once the user approves it or has already asked for them.

## Each issue

- **Title:** the outcome.
- **Body:** what and why in two or three sentences, observable acceptance
  checks, and starting paths. Paths are guidance; verify them when work starts.
- **Dependencies:** use blocked-by/blocking relations on Linear or GitHub when
  the selected tool supports them. GitHub sub-issues express hierarchy, not a
  blocking edge. If native dependency relations are unavailable, state the
  blocking issue explicitly and report the limitation.

Reuse existing issues rather than duplicating them, and follow the tracker's
existing states and labels.

## Process

1. Read the plan and enough code to use accurate names and paths.
2. Draft the smallest set of issues and their dependencies, and present it.
3. After approval, create the issues in dependency order and report their keys.
4. For a Linear issue, name its linked plan `ABC-123-slug.md` so it is eligible
   to mirror, following [plan storage](../write-plan/references/plan-storage.md).
   A GitHub-linked plan stays local; link it through the authorized GitHub
   workflow without assuming the Linear mirror applies.

Use the selected tracker's actual Git integration for status. For GitHub, use
an intended closing reference such as `Fixes #123` or `Fixes owner/repo#123`
when the pull request should close that issue; confirm the target repository
and merge behavior. For Linear, use the issue key in the branch name and the
configured integration's PR syntax, such as `Fixes ABC-123` when supported.
Update status by hand for states the integration cannot show, such as blocked.
