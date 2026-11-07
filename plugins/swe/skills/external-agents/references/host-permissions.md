# Host permissions

Every worker command lets the worker CLI approve its own tools, because
headless mode cannot ask. The lead's own agent host can treat that as
starting an unsafe agent, and block it.
This skill cannot lift such a block, and must not try. The user decides once,
in their own settings.

## When a worker command is blocked

Stop. Do not change the command to get past the block, and do not run the
worker through another tool. Tell the user which command was blocked and why,
and show the setup for their host below.

## Claude Code

In manual (default) mode, a worker command asks the user for permission,
like any other command.

In auto mode, the classifier blocks by default "running a third-party agent
or eval harness with isolation and per-action approval disabled". A plugin
cannot ship settings that lift this, and the classifier does not read
`autoMode` from project settings. The user adds both entries below to
`~/.claude/settings.json`.

1. Allow rules for the plain worker commands. A command that matches a
   narrow allow rule resolves before the classifier runs. This is why the
   worker commands start with `opencode run` or `agy` and have no `cd`,
   `env`, or `timeout` prefix.

   ```json
   "permissions": {
     "allow": ["Bash(opencode run *)", "Bash(agy *)"]
   }
   ```

2. An `autoMode.allow` entry. It tells the classifier that this kind of
   worker is expected. Keep `"$defaults"` in the list, or the built-in
   entries are lost. The user makes this edit by hand: in auto mode, the
   classifier blocks an agent's edit to `autoMode` as self-modification,
   even when the user asked for it.

   ```json
   "autoMode": {
     "allow": [
       "$defaults",
       "External Agent Workers: Starting `opencode run --auto` or `agy --sandbox` with `proceed-in-sandbox` settings for the swe external-agents skill is expected. Each worker runs in the lead's own git worktree for the task, not in the user's main checkout, on repository content the user chose to send to that provider. A worker in the user's main checkout, or a brief that holds secrets, is not covered."
     ]
   }
   ```

Run `/permissions` and open the Recently blocked tab to see a block and its
reason. `claude auto-mode config` prints the rules in effect.
