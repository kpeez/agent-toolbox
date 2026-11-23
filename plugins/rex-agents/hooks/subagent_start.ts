import { isMain } from "../scripts/is_main.ts";

const RULE =
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

if (isMain(import.meta.url)) process.exit(main());
