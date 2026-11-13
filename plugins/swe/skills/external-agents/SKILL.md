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
- **Delegate**: a worker builds a whole spec. The lead reviews the work and
  can send it back for further rounds.

## Harnesses

| Harness | Reaches | Reference |
| --- | --- | --- |
| OpenCode 2.x | The providers the user connected to OpenCode | [opencode.md](references/opencode.md) |
| Antigravity (`agy`) | The models on the user's Antigravity account | [antigravity.md](references/antigravity.md) |

Use the harness the user named. With no harness named, use OpenCode. Read the
harness reference before step 1.

## Rules for every worker

- **Data.** A provider is a third party and can keep the prompt. Send only
  the repository content the user authorized for that provider.
- **Tools, no prompts.** Headless mode cannot ask. Each worker approves the
  tools its config permits. An agy worker runs commands in an OS sandbox with
  no network. OpenCode has no sandbox. Its scout cannot edit or run shell
  commands; its builder can change files and reach the network.
- **The user's trust.** Your own host can block a command that starts an
  agent with auto-approve. Run each worker command exactly as the reference
  gives it, as one plain command. Never wrap it in `nu -c`, `bash -c`, or
  another shell, even when your own rules say to run commands that way: a
  wrapper stops the host's allow rule from matching. If the host blocks it, stop and follow
  [host-permissions.md](references/host-permissions.md). Never work around
  the block.
- **Worktree.** A delegate runs in your task worktree, not the user's main
  checkout. If needed, make a task worktree with `git worktree add`. A scout
  runs in your current directory. Other questions workers use a throwaway
  worktree. A worktree is only a working directory, not a boundary. Worktrees
  share one `.git` and one stash list.
- **Run folder.** Make the run folder
  `.agents/scratch/<branch-slug>/external-agents/<stamp>/`
  ([agent scratch](../../references/agent-scratch.md)), where `<stamp>` is a
  timestamp. Below, `<run>` is its real absolute path, as `realpath` prints
  it, `<id>` is the worker's slug, and `<worktree>` is the real path of the
  directory the worker runs in, as `pwd -P` prints it.
- **Brief as a file.** Write each brief to `<run>/<id>.md`, so the brief
  needs no shell quoting and stays out of the diff. A worker sees no chat,
  so the brief names the goal, the paths to read, the commands it may need,
  and the report format, such as one `path:line: finding` per line or
  `NONE`. A scout brief says not to change files. A builder brief allows
  commits on the current branch and forbids push, merge, rebase, reset, stash,
  and branch changes. An agy brief has the same git rules and forbids commits,
  including for a delegate.
- **Parallel, with a time limit.** Start each worker as its own background
  command, then wait for all of them. The reference gives the time limit
  and how to stop a worker.
- **A pane the user watches.** In Rex, when the user asks to watch an
  OpenCode worker or names a pane for it, follow the Rex pane section of
  the OpenCode reference instead. A pane worker can ask the user for
  approval, and it has no time limit.
- **Status.** Classify each result using the reference. Both harnesses use
  `ok`, `error`, and `timeout`. Only OpenCode uses `rate_limited` and
  `auth_failed`. A non-`ok` result is a gap, not a pass. OpenCode
  `auth_failed` names the provider that needs `opencode auth login`.
- **One retry.** Retry an `error` or `timeout` once, using the next model if
  available. For the OpenCode-only statuses `rate_limited` and `auth_failed`,
  try the next model in the role's list without using the one retry. If every
  model in that list fails with those statuses, do the work yourself and say
  so in the report, for example "builder quota out; implemented inline". With
  no list, do the same when the agent's configured model has one of those
  statuses. Also work inline and report it when a task is too small to be
  worth a brief.

## Questions

1. **Check the harness.** Run the checks in the reference.
2. **Choose models.** Follow the reference for the worker role.
3. **Frame the questions.** Pick a shape from [swarm](../swarm/SKILL.md): a
   coverage matrix for one slice per worker, or a race for one brief on
   several models. Keep three to five workers, each with one bounded
   question. Each brief says not to change files.
4. **Write the briefs and set the effort.** Pick an effort per worker as you
   would for a native subagent: `low` for mechanical lookups, `medium` for
   routine reading, `high` or above for judgment. The reference says how to
   set it.
5. **Run the workers.** An OpenCode scout runs in your current directory and
   sees uncommitted work. It needs no commit or throwaway worktree. Start each
   scout there with the reference command. For agy or any worker that is not
   a scout, use a throwaway worktree:
   1. Those workers see only committed code. If the questions need
      uncommitted work, commit it first.
   2. Add `/.external-agents/` to the file that
      `git rev-parse --git-path info/exclude` names, if it is not there.
   3. Run `git worktree add --detach .external-agents/<stamp> HEAD`.
   4. Keep the output of `git rev-parse HEAD` and `git stash list`.
   5. Change to the new worktree and start the workers with the reference command.
6. **Verify.** Read each answer. Check each claim in the code before you use
   it. Drop claims you cannot confirm. For a race, apply the selection rule
   you declared in step 3.
7. **Check for changes and clean up.** For a throwaway worktree, return to
   your worktree. Run `git rev-parse HEAD` and `git stash list` again and
   compare them with the saved outputs. A difference is a worker's git change.
   Undo it, and say so in the report.
   Run `git worktree remove --force .external-agents/<stamp>`. This discards
   every file change the workers made.
8. **Report.** Give one report per [swarm](../swarm/SKILL.md#phase-d-report):
   the verified results, the harness and model of each worker, and the gaps.
   Then delete each OpenCode worker session as the reference says.

## Delegate

1. **Check the harness and choose the model** as in the questions steps.
   Use `high` effort or above when the model supports it.
2. **Fix the spec.** The spec is a file the worker can read. It names each
   requirement, the files in scope, and the commands that build and test the
   work. Number the requirements, such as `R1-csv-bom`. A spec with an open
   product decision goes back to the user first.
3. **Start clean.** The worker's diff must stand alone. Commit your own
   changes first, or use a new task worktree.
   Record the base commit and previous HEAD with `git rev-parse HEAD`. Record
   the branch with `git branch --show-current` and the output of `git stash list`.
4. **Run the builder.** At the delegate time limit, start an OpenCode builder
   with `--session ses_<stamp>_<id>` and `--title`. The brief points to the
   spec, asks it to build and test every requirement, and says to commit on
   the current branch in small commits. It asks for each requirement marked
   `done` or `not done` at the end. An agy delegate cannot commit. Keep the
   `conversation_id` from its result. At the end of the round, inspect and
   commit its changes yourself with a message that names the round.
5. **Review the round.** Check that HEAD is a descendant of the previous HEAD
   with `git merge-base --is-ancestor <previous-head> HEAD`. Check that the
   branch and `git stash list` match the saved values. If a check fails, stop
   and ask the user. Record the new HEAD for the next round. Review
   `git log <base>..` and `git diff <base>` against the spec. Use
   `git show <commit>` to review each commit.
   Check for uncommitted or out-of-scope changes. Mark each requirement met,
   partly met, or missing with `path:line` evidence. Run the spec's checks
   yourself. Write each gap as `path:line: finding` in
   `<run>/<id>-review-<n>.md`.
6. **Close gaps.** If gaps remain, resume the same OpenCode builder session
   and attach only the review file. For agy, resume its conversation with
   `--conversation <id>` and point it only to the review file. At the end of each agy round, inspect and
   commit its changes yourself with a message that names the round. Repeat
   step 5. Stop after three review rounds. Then finish any open gaps yourself
   or bring them to the user. Never edit the builder's commits in place; add
   your own commits on top.
7. **Report.** Give the requirement table, rounds used, builder and lead
   commits, check results, and branch. Publish per [ship-pr](../ship-pr/SKILL.md)
   only when the user asks. Then delete the OpenCode builder session as the
   reference says.
