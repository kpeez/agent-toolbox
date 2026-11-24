import { existsSync, readFileSync, readdirSync, realpathSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT = realpathSync(fileURLToPath(import.meta.url));
const TEMPLATE = resolve(dirname(SCRIPT), "..", "templates", "pr-body.md");
const SLOT = /\{(\w+)\}/g;
const LINK = /^(?:Closes|Fixes|Part of) [\p{L}\p{N}_#/.-]+$/u;
const FENCE_OPENER = /^( {0,3})(`{3,}|~{3,})(.*)$/;
const NESTED_FENCE_OPENER = /^( *)(`{3,}|~{3,})(.*)$/;
const FENCE_CLOSER = /^(\s*)(`{3,}|~{3,})[ \t]*$/;
const ANY_FENCE_LINE = /^\s*(```|~~~)/;
const HEADING = /^ {0,3}#{1,6}(?:[ \t]|$)/;
const LOOSE_HEADING = /^#{1,6} /;
const CONTAINER_MARKERS = /^(?:\s*>\s?|\s*(?:[-*+]|\d{1,9}[.)])[ \t]+)*/;

type Fence = { char: string; length: number; inContainer: boolean };
type FenceReading = (line: string) => boolean;

function fenceOpener(line: string, nested: boolean): Fence | null {
  const bare = line.replace(CONTAINER_MARKERS, "");
  const m = (nested ? NESTED_FENCE_OPENER : FENCE_OPENER).exec(bare);
  if (!m || (m[2][0] === "`" && m[3].includes("`"))) return null;
  return { char: m[2][0], length: m[2].length, inContainer: bare !== line };
}

function commonMarkFences(nested: boolean): FenceReading {
  let fence: Fence | null = null;
  return (line) => {
    if (fence) {
      const m = FENCE_CLOSER.exec(fence.inContainer ? line.replace(CONTAINER_MARKERS, "") : line);
      if (m && m[2][0] === fence.char && m[2].length >= fence.length && (nested || /^ {0,3}$/.test(m[1]))) fence = null;
      return true;
    }
    fence = fenceOpener(line, nested);
    return fence !== null;
  };
}

function toggledFences(): FenceReading {
  let open = false;
  return (line) => {
    if (ANY_FENCE_LINE.test(line)) {
      open = !open;
      return true;
    }
    return open;
  };
}

function stripCodeSpans(line: string): string {
  let out = "";
  let i = 0;
  while (i < line.length) {
    if (line[i] === "\\" && i + 1 < line.length) {
      out += line.slice(i, i + 2);
      i += 2;
      continue;
    }
    if (line[i] !== "`") {
      out += line[i++];
      continue;
    }
    const open = /^`+/.exec(line.slice(i))![0];
    let close = -1;
    for (const m of line.slice(i + open.length).matchAll(/`+/g)) {
      if (m[0].length === open.length) {
        close = i + open.length + m.index + m[0].length;
        break;
      }
    }
    if (close === -1) {
      out += open;
      i += open.length;
    } else {
      out += " ";
      i = close;
    }
  }
  return out;
}

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

interface Word {
  text: string;
  hasExpansion: boolean;
}
interface Heredoc {
  body: string;
  quoted: boolean;
}
interface SimpleCommand {
  words: Word[];
  heredocs: Heredoc[];
}

const OPERATORS = ["&&", "||", ";;", ";&", "|&", ";", "|", "&", "(", ")"];
const REDIRECT = /(?:\d+|\{\w+\})?(?:<<<|<<-|<<|<>|<&|>>|>&|>\||&>>|&>|<|>)/y;
const WORD_END = new Set([" ", "\t", "\n", ";", "&", "|", "(", ")", "<", ">"]);

class ShellParser {
  pos = 0;
  private pending: { delimiter: string; stripTabs: boolean; heredoc: Heredoc }[] = [];
  readonly src: string;
  readonly out: SimpleCommand[];
  constructor(src: string, out: SimpleCommand[]) {
    this.src = src;
    this.out = out;
  }

  list(inSubstitution: boolean): void {
    let command: SimpleCommand = { words: [], heredocs: [] };
    let depth = 0;
    const flush = (): void => {
      if (command.words.length > 0 || command.heredocs.length > 0) this.out.push(command);
      command = { words: [], heredocs: [] };
    };
    const src = this.src;
    while (this.pos < src.length) {
      const ch = src[this.pos];
      if (ch === " " || ch === "\t") {
        this.pos++;
      } else if (ch === "\\" && src[this.pos + 1] === "\n") {
        this.pos += 2;
      } else if (ch === "#") {
        const end = src.indexOf("\n", this.pos);
        this.pos = end < 0 ? src.length : end;
      } else if (ch === "\n") {
        this.pos++;
        flush();
        this.readHeredocs();
      } else if ((ch === "<" || ch === ">") && src[this.pos + 1] === "(") {
        command.words.push(this.word());
      } else if (src.startsWith("((", this.pos) && this.arithmeticEnd(this.pos + 2) > 0) {
        // An arithmetic command: `<<` in `(( x = 1 << 3 ))` is a shift, not a heredoc.
        this.pos = this.arithmeticEnd(this.pos + 2);
      } else if (this.redirect(command)) {
        continue;
      } else {
        const op = OPERATORS.find((o) => src.startsWith(o, this.pos));
        if (op === undefined) {
          const start = this.pos;
          command.words.push(this.word());
          if (this.pos === start) this.pos++;
          continue;
        }
        this.pos += op.length;
        flush();
        if (op === "(") depth++;
        if (op === ")" && depth-- === 0 && inSubstitution) return;
      }
    }
    flush();
  }

  private redirect(command: SimpleCommand): boolean {
    REDIRECT.lastIndex = this.pos;
    const match = REDIRECT.exec(this.src);
    if (!match) return false;
    this.pos += match[0].length;
    while (this.src[this.pos] === " " || this.src[this.pos] === "\t") this.pos++;
    const start = this.pos;
    const target = this.word();
    const op = match[0].replace(/^(?:\d+|\{\w+\})/, "");
    if (op === "<<" || op === "<<-") {
      const heredoc = { body: "", quoted: /['"\\]/.test(this.src.slice(start, this.pos)) };
      command.heredocs.push(heredoc);
      this.pending.push({ delimiter: target.text, stripTabs: op === "<<-", heredoc });
    }
    return true;
  }

  private readHeredocs(): void {
    for (const { delimiter, stripTabs, heredoc } of this.pending) {
      const lines: string[] = [];
      while (this.pos < this.src.length) {
        const end = this.src.indexOf("\n", this.pos);
        const line = this.src.slice(this.pos, end < 0 ? this.src.length : end);
        this.pos = end < 0 ? this.src.length : end + 1;
        if ((stripTabs ? line.replace(/^\t+/, "") : line) === delimiter) break;
        lines.push(line);
      }
      heredoc.body = lines.join("\n");
      if (!heredoc.quoted) new ShellParser(heredoc.body, this.out).heredocBody();
    }
    this.pending = [];
  }

  private word(): Word {
    const src = this.src;
    let text = "";
    let hasExpansion = false;
    if (src[this.pos] === "<" || src[this.pos] === ">") {
      const start = this.pos;
      this.pos += 2;
      this.list(true);
      return { text: src.slice(start, this.pos), hasExpansion: true };
    }
    while (this.pos < src.length && !WORD_END.has(src[this.pos])) {
      const ch = src[this.pos];
      if (ch === "\\") {
        if (src[this.pos + 1] !== "\n") text += src[this.pos + 1] ?? "";
        this.pos += 2;
      } else if (ch === "'") {
        const end = src.indexOf("'", this.pos + 1);
        text += src.slice(this.pos + 1, end < 0 ? src.length : end);
        this.pos = end < 0 ? src.length : end + 1;
      } else if (ch === '"') {
        this.pos++;
        const part = this.quotedString();
        text += part.text;
        hasExpansion ||= part.hasExpansion;
      } else {
        const expansion = this.consumeExpansionCollectingCommands();
        if (expansion === null) {
          text += ch;
          this.pos++;
        } else {
          text += expansion;
          hasExpansion = true;
        }
      }
    }
    return { text, hasExpansion };
  }

  quotedString(): Word {
    return this.doubleQuotedText(true);
  }

  heredocBody(): Word {
    return this.doubleQuotedText(false);
  }

  private doubleQuotedText(closes: boolean): Word {
    const src = this.src;
    let text = "";
    let hasExpansion = false;
    while (this.pos < src.length) {
      const ch = src[this.pos];
      if (closes && ch === '"') {
        this.pos++;
        break;
      }
      if (ch === "\\" && '$`"\\\n'.includes(src[this.pos + 1] ?? "")) {
        if (src[this.pos + 1] !== "\n") text += src[this.pos + 1];
        this.pos += 2;
        continue;
      }
      const expansion = this.consumeExpansionCollectingCommands();
      if (expansion === null) {
        text += ch;
        this.pos++;
      } else {
        text += expansion;
        hasExpansion = true;
      }
    }
    return { text, hasExpansion };
  }

  /** The end of `$(( ... ))` when its parentheses close with `))`, else 0: `$((cmd) )` is a command. */
  private arithmeticEnd(from: number): number {
    let depth = 2;
    for (let i = from; i < this.src.length; i++) {
      if (this.src[i] === "(") depth++;
      if (this.src[i] === ")" && --depth === 1) return this.src[i + 1] === ")" ? i + 2 : 0;
    }
    return 0;
  }

  private consumeExpansionCollectingCommands(): string | null {
    const src = this.src;
    const start = this.pos;
    const next = src[start + 1] ?? "";
    if (src[start] === "`") {
      let inner = "";
      this.pos++;
      while (this.pos < src.length && src[this.pos] !== "`") {
        if (src[this.pos] === "\\" && "$`\\".includes(src[this.pos + 1] ?? "")) this.pos++;
        inner += src[this.pos++];
      }
      this.pos++;
      new ShellParser(inner, this.out).list(false);
    } else if (src[start] !== "$") {
      return null;
    } else if (src.startsWith("$((", start) && this.arithmeticEnd(start + 3) > 0) {
      this.pos = this.arithmeticEnd(start + 3);
    } else if (next === "(") {
      this.pos += 2;
      this.list(true);
    } else if (next === "{") {
      this.pos += 2;
      while (this.pos < src.length && src[this.pos] !== "}") {
        if (src[this.pos] === '"') {
          this.pos++;
          this.quotedString();
        } else if (this.consumeExpansionCollectingCommands() === null) {
          this.pos++;
        }
      }
      this.pos++;
    } else if (next === "'") {
      const end = src.slice(start + 2).search(/(?<!\\)'/);
      this.pos = end < 0 ? src.length : start + 3 + end;
    } else if (/[\w@*#?$!-]/.test(next)) {
      this.pos += /\w/.test(next) ? 1 + /^\w+/.exec(src.slice(start + 1))![0].length : 2;
    } else {
      return null;
    }
    this.pos = Math.min(this.pos, src.length);
    return src.slice(start, this.pos);
  }
}

// `and`, `or`, and `not` are fish keywords.
const RESERVED = new Set(["!", "{", "}", "if", "then", "elif", "else", "fi", "while", "until", "do", "done", "time", "-p", "and", "or", "not"]);
const ASSIGNMENT = /^[A-Za-z_]\w*(?:\[[^\]]*\])?\+?=/;
const SHELLS = new Set(["bash", "sh", "zsh", "dash", "ksh", "fish", "nu"]);
const WRAPPER_OPTIONS_WITH_VALUE: Record<string, Set<string>> = {
  env: new Set(["-u", "-C", "-P", "-S", "--unset", "--chdir"]),
  command: new Set(),
  exec: new Set(["-a"]),
  nohup: new Set(),
  sudo: new Set(["-u", "-g", "-C", "-D", "-p", "-r", "-t", "-T", "-U", "-R", "--user", "--group", "--prompt", "--chdir"]),
  xargs: new Set(["-I", "-J", "-L", "-n", "-P", "-R", "-s", "-S", "-E", "-d", "-a", "--arg-file", "--delimiter", "--max-args", "--max-procs"]),
  nice: new Set(["-n", "--adjustment"]),
  timeout: new Set(["-s", "-k", "--signal", "--kill-after"]),
};
const WRAPPER_POSITIONAL_ARGS_BEFORE_COMMAND: Record<string, number> = { timeout: 1 };
const DEPTH_LIMIT = 8;

function parseCommands(src: string): SimpleCommand[] {
  const out: SimpleCommand[] = [];
  new ShellParser(src, out).list(false);
  return out;
}

function commandNameIsUnresolved(words: Word[], index: number): boolean {
  return index >= words.length || words[index].hasExpansion;
}

function blockReason(words: Word[], heredocs: Heredoc[], cwd: string, depth: number): string | null {
  let i = 0;
  while (i < words.length && (RESERVED.has(words[i].text) || ASSIGNMENT.test(words[i].text))) i++;
  if (commandNameIsUnresolved(words, i) || depth > DEPTH_LIMIT) return null;
  // nu runs an external command written `^gh`.
  const name = (words[i].text.split("/").pop() as string).replace(/^\^/, "");
  const args = words.slice(i + 1);
  const nested = (src: string): string | null => {
    for (const command of parseCommands(src)) {
      const reason = blockReason(command.words, command.heredocs, cwd, depth + 1);
      if (reason !== null) return reason;
    }
    return null;
  };
  if (name === "for" || name === "select" || name === "case") return null;
  if (name === "command" && /^-[vV]/.test(args[0]?.text ?? "")) return null;
  if (name in WRAPPER_OPTIONS_WITH_VALUE) {
    const takesValue = WRAPPER_OPTIONS_WITH_VALUE[name];
    let j = 0;
    while (j < args.length && args[j].text.startsWith("-")) {
      const text = args[j].text;
      if (text === "--") {
        j++;
        break;
      }
      const split = name === "env" ? /^(?:-S|--split-string=?)(.*)$/s.exec(text) : null;
      if (split) {
        const rest = args.slice(j + 1).map((w) => w.text);
        return nested((split[1] === "" ? rest : [split[1], ...rest]).join(" "));
      }
      j += takesValue.has(text) ? 2 : 1;
    }
    return blockReason(args.slice(j + (WRAPPER_POSITIONAL_ARGS_BEFORE_COMMAND[name] ?? 0)), heredocs, cwd, depth + 1);
  }
  if (name === "eval") return nested(args.map((w) => w.text).join(" "));
  if (SHELLS.has(name)) {
    let runsString = false;
    for (let j = 0; j < args.length; j++) {
      const text = args[j].text;
      if (/^[-+][oO]$/.test(text) || text === "--rcfile" || text === "--init-file") j++;
      else if (/^-[A-Za-z]*c/.test(text) || text === "--command" || text === "--commands") runsString = true;
      else if (text === "--" || !/^[-+]/.test(text)) return runsString ? nested(text === "--" ? (args[j + 1]?.text ?? "") : text) : null;
    }
    return runsString ? null : nested(heredocs.map((h) => h.body).join("\n"));
  }
  if (name !== "gh") return null;
  const texts = args.map((w) => w.text);
  if (texts[0] === "pr" && ["create", "new", "edit"].includes(texts[1])) {
    return checkPrSegment(texts[1] === "edit" ? "edit" : "create", texts.slice(2), cwd);
  }
  if (texts[0] === "api") return checkApi(texts.slice(1));
  return null;
}

const API_VALUE_FLAGS = new Set(["-X", "--method", "-f", "--raw-field", "-F", "--field", "-H", "--header", "--input", "-q", "--jq", "-t", "--template", "--hostname", "-p", "--preview", "--cache"]);
const PULLS_ENDPOINT = /^\/?repos\/[^/]+\/[^/]+\/pulls(?:\/[^/?]+)?\/?(?:\?.*)?$/;

function checkApi(args: string[]): string | null {
  let endpoint: string | null = null;
  let method: string | null = null;
  let sendsFields = false;
  let setsBodyOrBase = false;
  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    const flag = /^(-[A-Za-z]|--[\w-]+)/.exec(arg)?.[0] ?? "";
    const attached = arg.startsWith("--") ? arg.slice(flag.length + 1) : arg.slice(2);
    const value = API_VALUE_FLAGS.has(arg) ? (args[++i] ?? "") : attached;
    if (["-X", "--method"].includes(flag)) method = value.toUpperCase();
    else if (["-f", "--raw-field", "-F", "--field", "--input"].includes(flag)) {
      sendsFields = true;
      setsBodyOrBase ||= flag === "--input" || /^(?:body|base)=/.test(value);
    }
    else if (!arg.startsWith("-") && endpoint === null) endpoint = arg;
  }
  method ??= sendsFields ? "POST" : "GET";
  if (endpoint === null || !PULLS_ENDPOINT.test(endpoint)) return null;
  if (method !== "POST" && !(method === "PATCH" && setsBodyOrBase)) return null;
  return blockMessage(
    `gh api ${method} ${endpoint} creates or edits a pull request without the body check. ` +
      "Use `gh pr create` or `gh pr edit` with --body-file.",
  );
}

function checkCommand(command: string, cwd: string): string | null {
  for (const simple of parseCommands(command)) {
    const reason = blockReason(simple.words, simple.heredocs, cwd, 0);
    if (reason !== null) return reason;
  }
  return null;
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

function slotErrors(name: string, text: string): string[] {
  if (text.trim() === "") return [`${name}: empty.`];
  if (text.trim() === `{${name}}`) return [`${name}: still holds the template placeholder {${name}}.`];
  const errors: string[] = [];
  const readings = [toggledFences(), commonMarkFences(false), commonMarkFences(true)];
  const lines = text.split(/\r\n|\r|\n/);
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const number = i + 1;
    const [toggledCode, strictCode, nestedCode] = readings.map((inCode) => inCode(line));
    const commonMarkProse = !strictCode && !nestedCode;
    const prose: string[] = [];
    if (commonMarkProse) prose.push(stripCodeSpans(line));
    if (!toggledCode) prose.push(line.replace(/`[^`]*`/g, ""));
    const heading =
      (commonMarkProse && HEADING.test(line.replace(CONTAINER_MARKERS, ""))) ||
      (!toggledCode && LOOSE_HEADING.test(line.replace(/`[^`]*`/g, "")));
    if (heading) {
      errors.push(`${name} line ${number}: heading '${line.trim()}'. The template owns all headings.`);
    }
    for (const pattern of ATTRIBUTION) {
      const match = prose.map((text) => pattern.exec(text)).find((m) => m !== null);
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
  if (link && !LINK.test(link)) {
    errors.push(`link '${link}' must be 'Closes <key>', 'Fixes <key>', or 'Part of <key>'.`);
  }
  if (errors.length > 0) return { body: null, errors };
  const body = template.replace(SLOT, (_m, name: string) => slots[name]).replace(/\n+$/, "") + "\n";
  return { body: link ? `${body}\n${link}\n` : body, errors: [] };
}

function escapeRegex(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
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

function expanduser(path: string): string {
  if (path === "~") return homedir();
  if (path.startsWith("~/")) return join(homedir(), path.slice(2));
  return path;
}

function blockMessage(reason: string): string {
  return `PR body blocked by ship-pr: ${reason}\nRender: ${process.versions.bun ? "bun" : "node"} ${SCRIPT} render <slot-folder> -o body.md\n`;
}

function checkPrSegment(action: string, args: string[], cwd: string): string | null {
  const base = extractBase(args);
  if (base !== null && repoUsesGhStack(cwd) && !repoTrunks(cwd).has(base)) {
    return (
      `PR base blocked by ship-pr: this repo uses gh-stack, so --base ${JSON.stringify(base)} is not allowed. ` +
      "Publish stacked branches with `gh stack link` or `gh stack submit` instead, " +
      "then update each PR body with `gh pr edit <n> --body-file <rendered>`.\n"
    );
  }
  let bodyFile: string | null = null;
  for (let i = 0; i < args.length; i++) {
    const word = args[i];
    if (word === "--body" || word.startsWith("--body=") || word.startsWith("-b")) {
      return blockMessage("inline --body is not allowed. Build the body with `pr_body.ts render`, then pass --body-file.");
    }
    if (word === "--fill" || word.startsWith("--fill-")) {
      return blockMessage("--fill writes the body from commits. Build it with `pr_body.ts render`, then pass --body-file.");
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
    return action === "create" ? blockMessage("gh pr create needs --body-file from `pr_body.ts render`.") : null;
  }
  if (bodyFile === "-") {
    return blockMessage("--body-file - reads stdin, which this hook cannot check. Pass the rendered file.");
  }
  const expanded = expanduser(bodyFile);
  const path = isAbsolute(expanded) ? expanded : join(cwd, expanded);
  if (!isFile(path)) {
    return blockMessage(`body file ${path} does not exist yet. Run \`pr_body.ts render\` first.`);
  }
  const text = readFileSync(path, "utf-8");
  let errors: string[];
  if (repoHasOwnTemplate(cwd)) {
    errors = slotErrors("body", text).filter((e) => !/ line \d+: heading '/.test(e));
  } else {
    errors = check(text);
  }
  return errors.length > 0 ? blockMessage(errors.join("\n")) : null;
}

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
  const reason = checkCommand(command, cwd);
  if (reason === null) return 0;
  process.stderr.write(reason);
  return 2;
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

function longOption(token: string, names: string[]): string {
  if (names.includes(token)) return token;
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
