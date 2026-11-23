/**
 * PreToolUse hook: mirror each background Bash command into its own Rex block.
 *
 * Rewrites a Bash call only when all of these hold: `run_in_background` is true,
 * the permission mode is `auto` or `bypassPermissions`, REX_SESSION is set, `rex`
 * is on PATH, REX_AGENTS_MIRROR is not `0`, the command is not
 * already mirrored, and the command does not start with `rex ` (a driven
 * agent's wait-status call must not get its own tab). The hook returns
 * `updatedInput` and no permission decision. Claude Code checks permission
 * rules against each subcommand of the returned command, so a deny rule for
 * the original command still blocks the wrapped form (tested with
 * `Bash(touch:*)` and `Bash(git clean:*)`).
 *
 * In a mode that prompts, the wrapped command does not match the user's allow
 * rules and trips Claude Code's brace-and-quote check, so an allowed command
 * would prompt. Those modes keep the command unchanged.
 */

import { accessSync, constants, readFileSync, statSync } from "node:fs";
import { delimiter, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isMain } from "../scripts/is_main.ts";
import { runtimeFlags } from "../scripts/runtime_flags.ts";

const MIRROR = resolve(dirname(fileURLToPath(import.meta.url)), "..", "scripts", "rex_mirror.ts");
const LABEL_MAX = 60;
const MIRROR_MODES = new Set(["auto", "bypassPermissions"]);
const SAFE = /^[a-zA-Z0-9_@%+=:,./-]+$/;
// Python str.split() whitespace: JS \s plus \x1c-\x1f and \x85, minus \ufeff.
const WHITESPACE = /[\t-\r\x1c-\x1f\x20\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;

/** Quote one shell word the way Python shlex.quote does. */
function shquote(s: string): string {
  if (s.length > 0 && SAFE.test(s)) return s;
  return "'" + s.replaceAll("'", "'\\''") + "'";
}

function which(name: string): string | null {
  for (const dir of (process.env.PATH ?? "").split(delimiter)) {
    const p = join(dir, name);
    try {
      accessSync(p, constants.X_OK);
      if (statSync(p).isFile()) return p;
    } catch {
      // not executable or not there: keep searching
    }
  }
  return null;
}

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function labelFor(toolInput: Record<string, unknown>, agentId: unknown): string {
  const raw = toolInput.description || toolInput.command || "";
  const text = String(raw).split(WHITESPACE).filter((s) => s.length > 0).join(" ").slice(0, LABEL_MAX);
  return `${agentId ? "[claude:sub]" : "[claude]"} ${text}`;
}

/**
 * Run the command in a subshell, then print its status as the marker rex_mirror.ts reads.
 *
 * The subshell keeps the command's own EXIT trap, `exec`, and `exit` from
 * skipping the marker. The newline before `)` ends a trailing comment. The
 * `:;` prefix keeps an empty or comment-only command valid in bash and sh,
 * which reject `( )` and `( # note )` with exit 2. zsh accepts both.
 */
export function mirrored(command: string, label: string, sessionId: string, runtime: string): string {
  return (
    `{ ( :; ${command}\n ); printf '\\n__rex_rc=%d\\n' "$?"; } 2>&1 | ` +
    [shquote(runtime), ...runtimeFlags(), shquote(MIRROR), shquote(label), shquote(sessionId)].join(" ")
  );
}

type MirrorDecision = {
  hookSpecificOutput: {
    hookEventName: "PreToolUse";
    updatedInput: Record<string, unknown>;
  };
};

/** Return the hook output for one PreToolUse event, or null to leave the call alone. */
function decide(data: unknown, env: Record<string, string | undefined>): MirrorDecision | null {
  if (!isRecord(data)) return null;
  const toolInput = isRecord(data.tool_input) ? data.tool_input : {};
  const command = toolInput.command;
  if (data.tool_name !== "Bash" || typeof command !== "string") return null;
  if (toolInput.run_in_background !== true) return null;
  if (typeof data.permission_mode !== "string" || !MIRROR_MODES.has(data.permission_mode)) return null;
  if (!env.REX_SESSION || env.REX_AGENTS_MIRROR === "0") return null;
  if (!which("rex")) return null;
  if (command.includes("rex_mirror.ts") || command.startsWith("rex ")) return null;
  const label = labelFor(toolInput, data.agent_id);
  const updated = { ...toolInput, command: mirrored(command, label, String(data.session_id ?? ""), process.execPath) };
  return { hookSpecificOutput: { hookEventName: "PreToolUse", updatedInput: updated } };
}

function main(): number {
  const out = decide(JSON.parse(readFileSync(0, "utf8")), process.env);
  if (out) console.log(JSON.stringify(out));
  return 0;
}

if (isMain(import.meta.url)) process.exit(main());
