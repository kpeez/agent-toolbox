---
name: to-issues
description: Split a large approved plan into pull-request-sized issues with dependencies on Linear or GitHub. Not for drafting plans or executing work.
---

# /to-issues

Most plans need one issue or none. Split only when the work needs several pull
requests that can be reviewed, verified, or sequenced independently. On the
Linear free plan every active issue counts toward a 250-issue cap, so do not
split for bookkeeping.

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
- **Dependencies:** native relations: blocked-by on Linear, sub-issues on
  GitHub.

Reuse existing issues rather than duplicating them, and follow the tracker's
existing states and labels.

## Process

1. Read the plan and enough code to use accurate names and paths.
2. Draft the smallest set of issues and their dependencies, and present it.
3. After approval, create the issues in dependency order and report their keys.
4. Rename a linked plan after the issue that owns it (`ABC-123-slug.md` in the
   directory printed by `python3 ../../scripts/plan_sync.py dir`) so it is
   mirrored to that issue.

Status comes from git: a branch name containing the issue key and a
`Fixes ABC-123` line in the pull request let the tracker's GitHub integration
move the issue. Update status by hand only for what git cannot show, such as
blocked.
