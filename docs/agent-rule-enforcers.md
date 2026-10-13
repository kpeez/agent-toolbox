# Agent rule enforcers

This table pairs each rule that stops a repeated agent mistake with what
enforces it. The `correct` skill in `plugins/swe` adds a row when it adds an
enforcer for a mistake class that occurred twice. Each row names the past
mistakes, the enforcer's path, and the command that runs it. To check the
table, run each row's command and confirm that its enforcer still exists and
still fails on the recorded mistake.

| Rule | Past mistakes | Level | Enforcer | Command |
|---|---|---|---|---|
