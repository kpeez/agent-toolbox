# OpenCode

OpenCode status reporting to Rex is not verified.

## Verify OSC 7501 first

Start OpenCode in a block as below, send it a one-line task, and read the
block's records while it works and after it ends:

```sh
rex block call -s <session> -b <block> program_status
```

Records with `app` set by OpenCode mean `wait-status` works, and the steps in
the skill apply. An empty list means OpenCode does not report its state.

## Launch, interactive

```sh
rex run -s <session> --focus=false --keep-open --shell=none --label "[opencode] <task>" --cwd <worktree> --json -- "$(command -v opencode)"
```

## Without status reports: run headless

Run one turn with `opencode run` in a block, and wait for the program to exit:

```sh
rex run -s <session> --focus=false --keep-open --shell=none --label "[opencode] <task>" --cwd <worktree> --json -- "$(command -v opencode)" run "Read <brief file> and do what it says."
rex wait -s <session> --for 60m <block>
```

`rex wait` returns the exit status of `opencode run`. Read the report file
the brief names.
