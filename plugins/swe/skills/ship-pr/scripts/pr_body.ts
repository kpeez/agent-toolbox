/**
 * Build a pull-request body from templates/pr-body.md, or check a published one.
 *
 * render: fill each {slot} of the template from <slot>.md in a folder. The agent
 * writes slot content only; the headings come from the template.
 * check: confirm a body is the template with its slots filled, as CI does.
 * Both reject a heading inside a slot and any requester attribution.
 */

import { existsSync, readFileSync, readdirSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT = realpathSync(fileURLToPath(import.meta.url));
const TEMPLATE = resolve(dirname(SCRIPT), "..", "templates", "pr-body.md");
const SLOT = /\{(\w+)\}/g;
// Python's $ also matches just before one trailing newline; linkValid below keeps that.
const LINK = /^(?:Closes|Fixes|Part of) [\p{L}\p{N}_#/.-]+$/u;
const FENCE = /^\s*(```|~~~)/;

const VERBS =
  "(?:wants?|wanted|asked|asks|requested|requests|said|says|prefers?|preferred" +
  "|approved|approves|decided|decides|instructed|insisted|told|chose)";
const REQUESTER_VERBS = "(?:asked|asks|requested|requests|wants|wanted|told|instructed|insisted)";
const ATTRIBUTION: RegExp[] = [
  new RegExp(`\\b(?:the |our )?user ${VERBS}\\b`, "i"),
  new RegExp(`\\byou ${VERBS}\\b`, "i"),
  /\b(?:as|per) (?:you|the user|requested|asked|instructed|discussed|agreed)\b/i,
  /\bper (?:your|the user'?s|their|his|her) (?:request|ask|instructions?|wishes)\b/i,
  /\b(?:requested|asked for|approved) by\b/i,
  /\b(?:in|from|during) (?:the|this|our) (?:chat|conversation|session)\b/i,
  new RegExp(`\\b(?!(?:This|That|It|Which|What)\\b)[A-Z][a-z]+ ${REQUESTER_VERBS}\\b`),
  /\b[A-Z][a-z]+'s (?:request|ask|decisions?|preference|instructions?)\b/,
];
const SEGMENT_SEPARATORS = new Set([";", "&&", "||", "|", "&", "\n", "(", ")", "`"]);
const WRAPPERS = new Set(["{", "env", "command", "exec", "time"]);
const ENV_ASSIGNMENT = /^[A-Za-z_][A-Za-z0-9_]*=/;

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isFile(path: string): boolean {
  try {
    return statSync(path).isFile();
  } catch {
    return false;
  }
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** Split like Python str.splitlines(): no trailing empty line, exotic boundaries included. */
function splitLines(text: string): string[] {
  if (text === "") return [];
  const parts = text.split(/\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/);
  if (parts[parts.length - 1] === "") parts.pop();
  return parts;
}

// The lexer mirrors shlex.shlex(posix=True, punctuation_chars=True) with
// whitespace " \t\r", commenters "", and wordchars extended by "!#$%+,:@[]^{}";
// punctuation_chars=True also adds "~-./*?=" to wordchars. States: " " start,
// "a" word, "c" punctuation run, the two quote chars, and the escape char.
const WORDCHARS = new Set(
  "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" +
    "ßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ" +
    "~-./*?=" +
    "!#$%+,:@[]^{}",
);
const PUNCTUATION = new Set("();<>|&");
const LEX_WHITESPACE = new Set(" \t\r");
const QUOTES = new Set(["'", '"']);
const ESCAPE = "\\";

function* shlexTokens(input: string): Generator<string> {
  // Iterate code points, as Python does; a surrogate half is not a character.
  const chars = Array.from(input);
  let pos = 0;
  const pushback: string[] = [];
  let state = " ";
  let escapedstate = " ";
  const nextChar = (): string => {
    if (pushback.length > 0) return pushback.pop() as string;
    return pos < chars.length ? chars[pos++] : "";
  };
  while (state !== "end") {
    let token = "";
    let quoted = false;
    for (;;) {
      const ch = nextChar();
      if (state === " ") {
        if (ch === "") {
          state = "end";
          break;
        }
        if (LEX_WHITESPACE.has(ch)) {
          if (token || quoted) break;
          continue;
        }
        if (ch === ESCAPE) {
          escapedstate = "a";
          state = ESCAPE;
          continue;
        }
        if (WORDCHARS.has(ch)) {
          token = ch;
          state = "a";
          continue;
        }
        if (PUNCTUATION.has(ch)) {
          token = ch;
          state = "c";
          continue;
        }
        if (QUOTES.has(ch)) {
          state = ch;
          continue;
        }
        token = ch;
        break;
      }
      if (state === "'" || state === '"') {
        quoted = true;
        if (ch === "") throw new Error("No closing quotation");
        if (ch === state) {
          state = "a";
          continue;
        }
        if (ch === ESCAPE && state === '"') {
          escapedstate = state;
          state = ESCAPE;
          continue;
        }
        token += ch;
        continue;
      }
      if (state === ESCAPE) {
        if (ch === "") throw new Error("No escaped character");
        // Inside double quotes only " and \ lose the backslash; elsewhere it stays literal.
        if ((escapedstate === "'" || escapedstate === '"') && ch !== ESCAPE && ch !== escapedstate) {
          token += ESCAPE;
        }
        token += ch;
        state = escapedstate;
        continue;
      }
      if (state === "a") {
        if (ch === "") {
          state = "end";
          break;
        }
        if (LEX_WHITESPACE.has(ch)) {
          state = " ";
          break;
        }
        if (QUOTES.has(ch)) {
          state = ch;
          continue;
        }
        if (ch === ESCAPE) {
          escapedstate = "a";
          state = ESCAPE;
          continue;
        }
        if (WORDCHARS.has(ch)) {
          token += ch;
          continue;
        }
        pushback.push(ch);
        state = " ";
        break;
      }
      // state "c": a run of punctuation characters forms one token.
      if (ch === "") {
        state = "end";
        break;
      }
      if (LEX_WHITESPACE.has(ch)) {
        state = " ";
        break;
      }
      if (PUNCTUATION.has(ch)) {
        token += ch;
        continue;
      }
      pushback.push(ch);
      state = " ";
      break;
    }
    if (!quoted && token === "") return;
    yield token;
  }
}

// Python str.split() whitespace (str.isspace). JS \s differs: it adds BOM and lacks \x1c-\x1f and \x85.
const PY_WHITESPACE = /[\t\n\v\f\r \x1c-\x1f\x85\xa0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/;

/** Tokenize a shell command and split it into command segments. */
export function splitSegments(command: string): string[][] {
  command = command.replaceAll("\\\n", " ");
  let tokens: string[];
  try {
    tokens = [...shlexTokens(command)];
  } catch {
    tokens = [];
    for (const line of splitLines(command)) {
      tokens.push(...line.split(PY_WHITESPACE).filter((t) => t !== ""));
      tokens.push("\n");
    }
  }
  const segments: string[][] = [];
  let current: string[] = [];
  for (const token of tokens) {
    if (SEGMENT_SEPARATORS.has(token)) {
      if (current.length > 0) {
        segments.push(current);
        current = [];
      }
    } else {
      current.push(token);
    }
  }
  if (current.length > 0) segments.push(current);
  return segments;
}

/** Drop leading env assignments and wrappers, and reduce a path to `gh`. */
export function commandWords(segment: string[]): string[] {
  const words = [...segment];
  while (words.length > 0 && (ENV_ASSIGNMENT.test(words[0]) || WRAPPERS.has(words[0]))) {
    words.shift();
  }
  if (words.length > 0) words[0] = words[0].split("/").pop() as string;
  return words;
}

function extractBase(args: string[]): string | null {
  let base: string | null = null;
  for (let i = 0; i < args.length; i++) {
    const word = args[i];
    if ((word === "--base" || word === "-B") && i + 1 < args.length) {
      base = args[i + 1];
    } else if (word.startsWith("--base=")) {
      base = word.split("=").slice(1).join("=");
    } else if (word.startsWith("-B=")) {
      base = word.split("=").slice(1).join("=");
    } else if (word.startsWith("-B") && word.length > 2) {
      base = word.slice(2);
    }
  }
  return base;
}

function gitOutput(args: string[], cwd: string): string | null {
  const result = spawnSync("git", args, { cwd, encoding: "utf-8", timeout: 2000 });
  if (result.error || result.status !== 0) return null;
  return result.stdout.trim();
}

function repoUsesGhStack(cwd: string): boolean {
  const common = gitOutput(["rev-parse", "--git-common-dir"], cwd);
  if (!common) return false;
  const commonDir = isAbsolute(common) ? common : join(cwd, common);
  return isFile(join(commonDir, "gh-stack"));
}

function repoTrunks(cwd: string): Set<string> {
  const head = gitOutput(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd);
  if (head) {
    const trunk = head.startsWith("origin/") ? head.slice("origin/".length) : head;
    if (trunk) return new Set([trunk]);
  }
  return new Set(["main", "master"]);
}

function repoHasOwnTemplate(cwd: string): boolean {
  const chain: string[] = [];
  let dir = resolve(cwd);
  for (;;) {
    chain.push(dir);
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  const root = chain.find((d) => existsSync(join(d, ".git")));
  if (root === undefined) return false;
  for (const folder of [root, join(root, ".github"), join(root, "docs")]) {
    if (!isDirectory(folder)) continue;
    const found = readdirSync(folder).some((name) => {
      const lower = name.toLowerCase();
      return lower === "pull_request_template.md" || lower === "pull_request_template";
    });
    if (found) return true;
  }
  return false;
}

export function slotErrors(name: string, text: string): string[] {
  if (text.trim() === "") return [`${name}: empty.`];
  const errors: string[] = [];
  let inFence = false;
  const lines = splitLines(text);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const number = i + 1;
    if (FENCE.test(line)) {
      inFence = !inFence;
      continue;
    }
    if (inFence) continue;
    const prose = line.replace(/`[^`]*`/g, "");
    if (/^#{1,6} /.test(prose)) {
      errors.push(`${name} line ${number}: heading '${line.trim()}'. The template owns all headings.`);
    }
    for (const pattern of ATTRIBUTION) {
      const match = pattern.exec(prose);
      if (match) {
        errors.push(
          `${name} line ${number}: requester attribution '${match[0]}'. ` +
            "Describe the change and the problem it solves, not who asked.",
        );
      }
    }
  }
  return errors;
}

export function render(folder: string, link: string | null): { body: string | null; errors: string[] } {
  const template = readFileSync(TEMPLATE, "utf-8");
  const slots: Record<string, string> = {};
  const errors: string[] = [];
  for (const match of template.matchAll(SLOT)) {
    const name = match[1];
    const path = join(folder, `${name}.md`);
    if (!isFile(path)) {
      errors.push(`${name}: missing ${path}.`);
      continue;
    }
    slots[name] = readFileSync(path, "utf-8").trim();
    errors.push(...slotErrors(name, slots[name]));
  }
  if (link && !linkValid(link)) {
    errors.push(`link '${link}' must be 'Closes <key>', 'Fixes <key>', or 'Part of <key>'.`);
  }
  if (errors.length > 0) return { body: null, errors };
  const body = template.replace(SLOT, (_m, name: string) => slots[name]).replace(/\n+$/, "") + "\n";
  return { body: link ? `${body}\n${link}\n` : body, errors: [] };
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function linkValid(link: string): boolean {
  return LINK.test(link) || (link.endsWith("\n") && LINK.test(link.slice(0, -1)));
}

export function check(body: string): string[] {
  const template = readFileSync(TEMPLATE, "utf-8").replace(/\n+$/, "");
  const names = [...template.matchAll(SLOT)].map((m) => m[1]);
  const pattern = template
    .split(SLOT)
    .map((part, i) => (i % 2 === 0 ? escapeRegex(part) : `(?<${part}>.+?)`))
    .join("");
  const full = new RegExp(`^(?:${pattern}(?:\\n\\n(?<link>(?:Closes|Fixes|Part of) \\S+))?\\n*)$`, "s");
  const match = full.exec(body.replaceAll("\r\n", "\n"));
  if (!match) {
    return ["body does not match templates/pr-body.md. Build it with `pr_body.ts render`."];
  }
  const groups = match.groups ?? {};
  const errors: string[] = [];
  for (const name of names) errors.push(...slotErrors(name, groups[name] ?? ""));
  return errors;
}

/** Python repr() for the branch names that reach the block message. */
function pyRepr(text: string): string {
  const quote = text.includes("'") && !text.includes('"') ? '"' : "'";
  const escaped = text
    .replace(/\\/g, "\\\\")
    .replace(/\n/g, "\\n")
    .replace(/\r/g, "\\r")
    .replace(/\t/g, "\\t")
    .replaceAll(quote, `\\${quote}`);
  return quote + escaped + quote;
}

function expanduser(path: string): string {
  if (path === "~") return homedir();
  if (path.startsWith("~/")) return join(homedir(), path.slice(2));
  return path;
}

function block(reason: string): number {
  process.stderr.write(
    `PR body blocked by ship-pr: ${reason}\nRender: ${process.versions.bun ? "bun" : "node"} ${SCRIPT} render <slot-folder> -o body.md\n`,
  );
  return 2;
}

function blockStack(reason: string): number {
  process.stderr.write(`PR base blocked by ship-pr: ${reason}\n`);
  return 2;
}

function checkPrSegment(action: string, args: string[], cwd: string): number {
  const base = extractBase(args);
  if (base !== null && repoUsesGhStack(cwd) && !repoTrunks(cwd).has(base)) {
    return blockStack(
      `this repo uses gh-stack, so --base ${pyRepr(base)} is not allowed. ` +
        "Publish stacked branches with `gh stack link` or `gh stack submit` instead, " +
        "then update each PR body with `gh pr edit <n> --body-file <rendered>`.",
    );
  }
  let bodyFile: string | null = null;
  for (let i = 0; i < args.length; i++) {
    const word = args[i];
    if (word === "--body" || word.startsWith("--body=") || word.startsWith("-b")) {
      return block("inline --body is not allowed. Build the body with `pr_body.ts render`, then pass --body-file.");
    }
    if (word === "--fill" || word.startsWith("--fill-")) {
      return block("--fill writes the body from commits. Build it with `pr_body.ts render`, then pass --body-file.");
    }
    if ((word === "--body-file" || word === "-F") && i + 1 < args.length) {
      bodyFile = args[i + 1];
    } else if (word.startsWith("--body-file=")) {
      bodyFile = word.split("=").slice(1).join("=");
    } else if (word.startsWith("-F") && word.length > 2) {
      bodyFile = word.startsWith("-F=") ? word.slice(3) : word.slice(2);
    }
  }
  if (bodyFile === null) {
    return action === "create" ? block("gh pr create needs --body-file from `pr_body.ts render`.") : 0;
  }
  if (bodyFile === "-") {
    return block("--body-file - reads stdin, which this hook cannot check. Pass the rendered file.");
  }
  const expanded = expanduser(bodyFile);
  const path = isAbsolute(expanded) ? expanded : join(cwd, expanded);
  if (!isFile(path)) {
    return block(`body file ${path} does not exist yet. Run \`pr_body.ts render\` first.`);
  }
  const text = readFileSync(path, "utf-8");
  let errors: string[];
  if (repoHasOwnTemplate(cwd)) {
    errors = slotErrors("body", text).filter((e) => !e.includes("heading"));
  } else {
    errors = check(text);
  }
  return errors.length > 0 ? block(errors.join("\n")) : 0;
}

/** PreToolUse hook: enforce PR body checks and gh-stack publishing on `gh pr create|edit`. */
function hook(): number {
  const event: unknown = JSON.parse(readFileSync(0, "utf-8"));
  if (!isRecord(event)) throw new TypeError("hook event must be an object");
  const toolInput = event.tool_input || {};
  if (!isRecord(toolInput)) throw new TypeError("tool_input must be an object");
  const command = toolInput.command ?? "";
  if (!command) return 0;
  if (typeof command !== "string") throw new TypeError("command must be a string");
  const cwd = event.cwd || ".";
  if (typeof cwd !== "string") throw new TypeError("cwd must be a string");
  for (const segment of splitSegments(command)) {
    const words = commandWords(segment);
    if (words.length >= 3 && words[0] === "gh" && words[1] === "pr" && (words[2] === "create" || words[2] === "edit")) {
      const rc = checkPrSegment(words[2], words.slice(3), cwd);
      if (rc !== 0) return rc;
    }
  }
  return 0;
}

const PROG = basename(process.argv[1] ?? "pr_body.ts");
const USAGE = `usage: ${PROG} [-h] {render,check} ...`;

function usageError(message: string): never {
  process.stderr.write(`${USAGE}\n${PROG}: error: ${message}\n`);
  process.exit(2);
}

function helpText(): string {
  return (
    `${USAGE}\n\n` +
    "Build a pull-request body from templates/pr-body.md, or check a published one.\n\n" +
    "positional arguments:\n" +
    "  {render,check}\n" +
    "    render        build the body from <slot>.md files\n" +
    "    check         check a finished body, or - for stdin\n\n" +
    "options:\n" +
    "  -h, --help      show this help message and exit\n"
  );
}

type Cli =
  | { kind: "help" }
  | { kind: "render"; folder: string; link: string | null; output: string }
  | { kind: "check"; bodyFile: string };

/** Resolve a long option by exact name or unique prefix, as argparse does. */
function longOption(token: string, names: string[]): string {
  if (names.includes(token)) return token;
  const matches = names.filter((n) => n.startsWith(token));
  if (matches.length === 1) return matches[0];
  usageError(`unrecognized arguments: ${token}`);
}

function parseCli(argv: string[]): Cli {
  let sub: string | null = null;
  let rest: string[] = [];
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token === "-h" || token === "--help") return { kind: "help" };
    if (token.startsWith("-") && token !== "-") usageError(`unrecognized arguments: ${token}`);
    sub = token;
    rest = argv.slice(i + 1);
    break;
  }
  if (sub === null) usageError("the following arguments are required: command");
  if (sub !== "render" && sub !== "check") {
    usageError(`argument command: invalid choice: '${sub}' (choose from 'render', 'check')`);
  }
  const positionals: string[] = [];
  let link: string | null = null;
  let output: string | null = null;
  let onlyPositionals = false;
  for (let i = 0; i < rest.length; i++) {
    const token = rest[i];
    if (!onlyPositionals && token === "--") {
      onlyPositionals = true;
      continue;
    }
    if (!onlyPositionals && (token === "-h" || token === "--help")) return { kind: "help" };
    if (!onlyPositionals && token.startsWith("--")) {
      if (sub === "check") usageError(`unrecognized arguments: ${token}`);
      const eq = token.indexOf("=");
      const name = longOption(eq >= 0 ? token.slice(0, eq) : token, ["--link", "--output"]);
      let value = eq >= 0 ? token.slice(eq + 1) : null;
      if (value === null) {
        if (i + 1 >= rest.length) usageError(`argument ${name}: expected one argument`);
        value = rest[++i];
      }
      if (name === "--link") link = value;
      else output = value;
      continue;
    }
    if (!onlyPositionals && token.startsWith("-") && token !== "-") {
      if (sub === "check" || !token.startsWith("-o")) usageError(`unrecognized arguments: ${token}`);
      let value = token.length > 2 ? token.slice(2) : null;
      if (value === null) {
        if (i + 1 >= rest.length) usageError("argument -o/--output: expected one argument");
        value = rest[++i];
      }
      output = value;
      continue;
    }
    positionals.push(token);
  }
  if (sub === "render") {
    if (positionals.length === 0) usageError("the following arguments are required: folder");
    if (output === null) usageError("the following arguments are required: -o/--output");
    if (positionals.length > 1) usageError(`unrecognized arguments: ${positionals.slice(1).join(" ")}`);
    return { kind: "render", folder: positionals[0], link, output };
  }
  if (positionals.length === 0) usageError("the following arguments are required: body_file");
  if (positionals.length > 1) usageError(`unrecognized arguments: ${positionals.slice(1).join(" ")}`);
  return { kind: "check", bodyFile: positionals[0] };
}

function main(): number {
  const argv = process.argv.slice(2);
  if (argv.length === 1 && argv[0] === "hook") return hook();
  const cli = parseCli(argv);
  if (cli.kind === "help") {
    process.stdout.write(helpText());
    return 0;
  }
  let errors: string[];
  if (cli.kind === "render") {
    const result = render(cli.folder, cli.link);
    if (result.body !== null) writeFileSync(cli.output, result.body, "utf-8");
    errors = result.errors;
  } else {
    const text = cli.bodyFile === "-" ? readFileSync(0, "utf-8") : readFileSync(cli.bodyFile, "utf-8");
    errors = check(text);
  }
  for (const error of errors) process.stderr.write(`pr_body: ${error}\n`);
  if (errors.length > 0) return 1;
  process.stdout.write(`pr_body: ok${cli.kind === "render" ? ` -> ${cli.output}` : ""}\n`);
  return 0;
}

function invokedDirectly(): boolean {
  const entry = process.argv[1];
  if (!entry) return false;
  try {
    return realpathSync(resolve(entry)) === SCRIPT;
  } catch {
    return false;
  }
}

if (invokedDirectly()) process.exitCode = main();
