---
name: external-agents
description: "Run workers on another agent CLI, such as OpenCode or Antigravity `agy`: a few small questions in parallel, or a whole spec delegated for implementation that Claude then reviews and fixes. Use when the user asks for OpenCode, Antigravity, or agy workers, a swarm or second opinion on one, or to hand one a spec to build."
argument-hint: "<task>"
---

# External agents

The lead is this session. It writes each worker's brief, starts each worker
with the harness CLI, and owns every result. There is no runner script: the
harness reference gives the exact command.

The skill has two modes:

- **Questions**: three to five workers in parallel, each with one bounded
  question. The lead checks every claim.
- **Delegate**: one worker builds a whole spec. The lead then reviews the
  work against the spec and finishes it.

## Harnesses

| Harness | Reaches | Reference |
| --- | --- | --- |
| OpenCode 2.x | The providers the user connected to OpenCode | [opencode.md](references/opencode.md) |
| Antigravity (`agy`) | The models on the user's Antigravity account | [antigravity.md](references/antigravity.md) |

Use the harness the user named. With no harness named, use OpenCode. Read the
harness reference before step 1.

## Rules for every worker

- **Data.** A provider is a third party, and free models can keep the
  prompt. Send only the repository content the user authorized for that
  provider.
- **Full tools, no prompts.** Headless mode cannot ask, and a denied tool
  ends the run early, so each worker approves its own tools. The reference
  says how far each harness contains the worker. An agy worker runs its
  commands in an OS sandbox with no network. An OpenCode worker has no
  sandbox: it can run any command, read and change any file the user can,
  and reach the network.
- **The user's trust.** Your own host can block a command that starts an
  agent with auto-approve. Run each worker command exactly as the reference
  gives it, as one plain command. If the host blocks it, stop and follow
  [host-permissions.md](references/host-permissions.md). Never work around
  the block.
- **Your worktree, not the user's checkout.** Workers run in your current
  directory, which must be a git worktree for this task. If you are in the
  user's main checkout, make one with `git worktree add` and work there.
  Every worker in the run shares it. The worktree is only the worker's
  working directory, not a boundary: an OpenCode worker can reach the main
  checkout, and every worktree shares one `.git` and one stash list.
- **Run folder.** Make the run folder with `mktemp -d`, outside the
  repository. Below, `<run>` is its real absolute path, as `realpath` prints
  it, `<id>` is the worker's slug, and `<worktree>` is the real path of your
  current directory, as `pwd -P` prints it.
- **Brief as a file.** Write each brief to `<run>/<id>.md`, so the brief
  needs no shell quoting and stays out of the diff. A worker sees no chat,
  so the brief names the goal, the paths to read, the commands it may need,
  and the report format, such as one `path:line: finding` per line or
  `NONE`. Every brief also says: do not commit, and do not run a git
  command that changes branches, the stash, or history.
- **Parallel, with a time limit.** Start each worker as its own background
  command, then wait for all of them. The reference gives the time limit
  and how to stop a worker.
- **Status.** The reference says how to read each result as `ok`, `error`,
  or `timeout`. An `error` or a `timeout` is a gap, not a pass.
- **One retry.** Run a failed worker once more on the next model in the
  pool. Free models often hit rate limits.

## Questions

1. **Check the harness.** Run the version check in the reference.
2. **Choose models.** Follow the reference. Use a paid model only when the
   user named it.
3. **Frame the questions.** Pick a shape from [swarm](../swarm/SKILL.md): a
   coverage matrix for one slice per worker, or a race for one brief on
   several models. Keep three to five workers, each with one bounded
   question. The workers share your worktree, so each brief also says not to
   change files.
4. **Write the briefs and set the effort.** Pick an effort per worker as you
   would for a native subagent: `low` for mechanical lookups, `medium` for
   routine reading, `high` or above for judgment. The reference says how to
   set it.
5. **Run it.** If you have uncommitted work you cannot lose, commit it
   first. Keep the output of `git rev-parse HEAD`, `git stash list`, and
   `git status --short`. Then start every worker with the command in the
   reference.
6. **Verify.** Read each answer. Check each claim in the code before you use
   it. Drop claims you cannot confirm. For a race, apply the selection rule
   you declared in step 3.
7. **Check for changes.** Run the three commands from step 5 again. A
   change since then is a worker's: noise, not a result. Undo it, and say so
   in the report.
8. **Report.** Give one report per [swarm](../swarm/SKILL.md#phase-d-report):
   the verified results, the harness and model of each worker, and the gaps.

## Delegate

1. **Check the harness and choose the model** as in the questions steps.
   Pick a strong model at `high` effort or above.
2. **Fix the spec.** The spec is a file the worker can read. It names each
   requirement, the files in scope, and the commands that build and test the
   work. Number the requirements, such as `R1-csv-bom`. A spec with an open
   product decision goes back to the user first.
3. **Start clean.** The worker's diff must stand alone. Commit your own
   changes first, or make a new worktree on its own branch for the delegate.
   Keep the base commit from `git rev-parse HEAD`.
4. **Run the worker** with the command in the reference, at the delegate
   time limit. Its brief points to the spec, says to build and test every
   requirement, and asks for a final list of each requirement with `done` or
   `not done`.
5. **Review against the spec.** Read the whole change from the base:
   `git diff <base>` and `git log <base>..`. Mark each requirement met,
   partly met, or missing, with `path:line` evidence. Look for changes
   outside the spec's scope. The worker's own list is a claim, not evidence.
6. **Run the checks yourself.** Run the spec's build and test commands in the
   worktree. A check the worker says passed counts only when your run passes.
7. **Finish the work.** Fix each gap and failure yourself in the worktree.
   When the gaps are large, send one more worker round with the open
   requirements and your findings, then go back to step 5.
8. **Report.** Give the requirement table, the changes you made after the
   worker, the check results, and the branch. Publish the branch per
   [ship-pr](../ship-pr/SKILL.md).
