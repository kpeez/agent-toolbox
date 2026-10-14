# Split a plan into issues

Most plans need one issue or none. Split only when the work needs several pull
requests that can be reviewed, verified, or sequenced independently. Do not
split for bookkeeping; check the selected tracker's current limits if they
matter to the proposed breakdown.

## Tracker

Use the tracker the user names, otherwise the one pinned in the repository's
`AGENTS.md`, `CLAUDE.md`, or `.agents/docs/CONTEXT.md` (for example
`Issue tracker: local`), otherwise ask. Never infer the tracker from where the
code is hosted. Use local plan files for `local`, the Linear connection for
Linear, and `gh` for GitHub. An
unavailable or unsupported tracker is a limitation to report, not a reason to
switch trackers.

Creating issues on Linear or GitHub changes external state. Present the
breakdown first and create issues only once the user approves it or has
already asked for them.

With the `local` tracker, each issue is one plan file in the plans directory
([plan storage](plan-storage.md)), named `<slug>.md`, where the slug is the
issue's planned branch name with `/` changed to `-`. The file uses the plan
template in [write-plan](../SKILL.md#template); its Goal is the issue's title
and body. Name each blocking issue's slug in the Approach. Delete the file
when its pull request merges.

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
3. After approval, create the issues in dependency order and report their keys
   or, for `local`, their paths.
4. For a Linear or GitHub issue, name any linked plan `<slug>.md` after the
   issue's branch, following [plan storage](plan-storage.md), and link the
   plan's path from the issue.

Use the selected tracker's actual Git integration for status. For GitHub, use
an intended closing reference such as `Fixes #123` or `Fixes owner/repo#123`
when the pull request should close that issue; confirm the target repository
and merge behavior. For Linear, use the issue key in the branch name and the
configured integration's PR syntax, such as `Fixes ABC-123` when supported.
Update status by hand for states the integration cannot show, such as blocked.
