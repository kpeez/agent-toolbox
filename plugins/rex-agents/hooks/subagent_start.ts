/**
 * SubagentStart hook: tell a subagent in a Rex pane to leave panes and sessions alone.
 */

export const RULE =
  "You are a subagent. Never open, rename, or arrange Rex panes or sessions. " +
  "In auto or bypassPermissions mode, your background commands are mirrored into Rex automatically.";

function main(): number {
  if (!process.env.REX_SESSION) return 0;
  console.log(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "SubagentStart",
        additionalContext: RULE,
      },
    }),
  );
  return 0;
}

if (import.meta.main) process.exit(main());
