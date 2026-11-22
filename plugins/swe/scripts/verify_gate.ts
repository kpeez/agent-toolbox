/**
 * Commit gate: a commit needs a passing verify record for each verify skill its files touch.
 *
 * run: run a check command and record the verdict from its exit code, bound to a hash of the tree.
 * hook: PreToolUse on Bash; act only on `git commit`. SWE_VERIFY_GATE is off, observe (default), or enforce.
 * session-start: print the `run` command template when the repo has a verify-* skill.
 */

import { appendFileSync, copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, realpathSync, rmSync, statSync, utimesSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { commandWords, splitSegments } from "../skills/ship-pr/scripts/pr_body.ts";

const SCRIPT = realpathSync(fileURLToPath(import.meta.url));
const ENV_ASSIGNMENT = /^[A-Za-z_][A-Za-z0-9_]*=/;
const ENV_FLAGS_WITH_VALUE = new Set(["-u", "--unset", "-C", "--chdir", "-S", "--split-string"]);
const SUDO_FLAGS_WITH_VALUE = new Set(["-u", "-g", "-h", "-p", "-C", "-r", "-t", "-U", "-D", "-R", "-T"]);
const SHELLS = new Set(["sh", "bash", "zsh", "dash", "ksh", "fish"]);
const SHELL_KEYWORDS = new Set(["then", "do", "else", "elif", "if", "while", "until", "!", "{"]);
const PLAIN_WRAPPERS = new Set(["env", "command", "exec", "time", "nohup"]);
const NICE_FLAGS_WITH_VALUE = new Set(["-n", "--adjustment"]);
const TIMEOUT_FLAGS_WITH_VALUE = new Set(["-k", "--kill-after", "-s", "--signal"]);
const FLAGS_WITH_VALUE_BEFORE_HELP = new Set(["-m", "-F", "-C", "-c", "-t", "--message", "--file", "--trailer", "--author", "--date", "--reuse-message", "--reedit-message", "--template", "--cleanup"]);
const MAX_SHELL_DEPTH = 3;
const ESCAPE_LINE = /^[ \t]*Verification: none \(.*\S.*\)[ \t]*$/m;
const MAX_BLOCKS_PER_SESSION = 2;
const SKILL_FOLDERS = [".agents/skills", ".claude/skills"];

type Verdict = "VERIFIED" | "NOT VERIFIED" | "INCONCLUSIVE";
type Mode = "off" | "observe" | "enforce";
type Skill = { name: string; paths: string[] | null };
type Repo = { root: string; gitDir: string };

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function git(cwd: string, args: string[], env?: Record<string, string>): string | null {
  const result = spawnSync("git", args, {
    cwd,
    encoding: "utf-8",
    timeout: 10000,
    env: env ? { ...process.env, ...env } : process.env,
    maxBuffer: 64 * 1024 * 1024,
  });
  if (result.error || result.status !== 0) return null;
  return result.stdout;
}

function findRepo(cwd: string): Repo | null {
  const out = git(cwd, ["rev-parse", "--show-toplevel", "--absolute-git-dir"]);
  if (out === null) return null;
  const [root, gitDir] = out.split("\n");
  return root && gitDir ? { root, gitDir } : null;
}

function gateDir(repo: Repo): string {
  return join(repo.gitDir, "swe-verify");
}

function treeHash(repo: Repo): string | null {
  mkdirSync(gateDir(repo), { recursive: true });
  const index = join(gateDir(repo), `tmp-index-${process.pid}`);
  try {
    const real = join(repo.gitDir, "index");
    if (existsSync(real)) {
      copyFileSync(real, index);
      // Git trusts a cached entry that is older than the index file. Keep the old mtime, or an edit made right after the last index write goes unseen.
      const { atime, mtime } = statSync(real);
      utimesSync(index, atime, mtime);
    }
    const env = { GIT_INDEX_FILE: index };
    if (git(repo.root, ["add", "-A"], env) === null) return null;
    return git(repo.root, ["write-tree"], env)?.trim() ?? null;
  } finally {
    rmSync(index, { force: true });
  }
}

function stripYamlComment(s: string): string {
  let quote = "";
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (quote !== "") {
      if (c === quote) quote = "";
    } else if (c === '"' || c === "'") {
      quote = c;
    } else if (c === "#" && (i === 0 || /\s/.test(s[i - 1]))) {
      return s.slice(0, i);
    }
  }
  return s;
}

function unquote(s: string): string {
  return stripYamlComment(s).trim().replace(/^(["'])(.*)\1$/, "$2");
}

function splitTopLevel(s: string): string[] {
  const parts: string[] = [];
  let depth = 0;
  let current = "";
  for (const c of s) {
    if (c === "{") depth++;
    if (c === "}") depth = Math.max(0, depth - 1);
    if (c === "," && depth === 0) {
      parts.push(current);
      current = "";
    } else {
      current += c;
    }
  }
  parts.push(current);
  return parts;
}

function inlinePaths(value: string): string[] {
  let v = stripYamlComment(value).trim();
  if (v.startsWith("[") && v.endsWith("]")) {
    v = v.slice(1, -1);
  } else {
    const whole = /^(["'])(.*)\1$/.exec(v);
    if (whole && !whole[2].includes(whole[1])) v = whole[2];
  }
  return splitTopLevel(v).map(unquote).filter((p) => p !== "");
}

function parseFrontmatter(text: string, fallbackName: string): Skill {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let name = fallbackName;
  let paths: string[] | null = null;
  if (lines[0]?.trim() !== "---") return { name, paths };
  const end = lines.indexOf("---", 1);
  const block = lines.slice(1, end === -1 ? lines.length : end);
  for (let i = 0; i < block.length; i++) {
    const nameMatch = /^name:\s*(.+)$/.exec(block[i]);
    if (nameMatch) name = unquote(nameMatch[1]);
    const pathsMatch = /^paths:\s*(.*)$/.exec(block[i]);
    if (!pathsMatch) continue;
    const inline = stripYamlComment(pathsMatch[1]).trim();
    const items: string[] = [];
    if (inline) {
      items.push(...inlinePaths(inline));
    } else {
      for (let j = i + 1; j < block.length; j++) {
        const item = /^\s*-\s+(.+)$/.exec(block[j]);
        if (!item) break;
        items.push(unquote(item[1]));
      }
    }
    paths = items.filter((p) => p !== "");
  }
  return { name, paths };
}

function verifySkills(root: string): Skill[] {
  const seen = new Set<string>();
  const skills: Skill[] = [];
  for (const folder of SKILL_FOLDERS) {
    const base = join(root, folder);
    if (!existsSync(base)) continue;
    for (const entry of readdirSync(base).sort()) {
      if (!entry.startsWith("verify-")) continue;
      const file = join(base, entry, "SKILL.md");
      if (!existsSync(file)) continue;
      const real = realpathSync(file);
      if (seen.has(real)) continue;
      seen.add(real);
      skills.push(parseFrontmatter(readFileSync(file, "utf-8"), entry));
    }
  }
  return skills;
}

function expandBraces(g: string): string[] {
  let depth = 0;
  let open = -1;
  for (let i = 0; i < g.length; i++) {
    const c = g[i];
    if (c === "\\") {
      i++;
    } else if (c === "{") {
      if (depth === 0) open = i;
      depth++;
    } else if (c === "}") {
      if (depth === 0) throw new Error("unmatched }");
      depth--;
      if (depth === 0) {
        const before = g.slice(0, open);
        const alternatives = splitTopLevel(g.slice(open + 1, i)).flatMap(expandBraces);
        const after = expandBraces(g.slice(i + 1));
        return alternatives.flatMap((a) => after.map((rest) => before + a + rest));
      }
    }
  }
  if (depth !== 0) throw new Error("unmatched {");
  return [g];
}

function globBody(g: string): string {
  let out = "";
  for (let i = 0; i < g.length; i++) {
    const c = g[i];
    if (c === "*" && g[i + 1] === "*") {
      if (g[i + 2] === "/") {
        out += "(?:.*/)?";
        i += 2;
      } else {
        out += ".*";
        i += 1;
      }
    } else if (c === "*") {
      out += "[^/]*";
    } else if (c === "?") {
      out += "[^/]";
    } else if (c === "[") {
      let k = i + 1;
      const negated = g[k] === "!" || g[k] === "^";
      if (negated) k++;
      const from = k;
      if (g[k] === "]") k++;
      const close = g.indexOf("]", k);
      if (close === -1) throw new Error("unclosed [");
      out += `[${negated ? "^" : ""}${g.slice(from, close).replace(/[\\[]/g, "\\$&")}]`;
      i = close;
    } else if (c === "\\" && i + 1 < g.length) {
      out += g[++i].replace(/[.+^${}()|[\]\\*?]/g, "\\$&");
    } else {
      out += c.replace(/[.+^${}()|[\]\\]/g, "\\$&");
    }
  }
  return out;
}

// Our own matcher: path.matchesGlob is missing or experimental on some runtimes.
// A pattern with no slash matches at any depth, as in Claude Code's path rules.
function compileGlob(glob: string): RegExp | null {
  try {
    let g = glob.replace(/^\.\//, "");
    if (g === "") return null;
    const anyDepth = !g.includes("/");
    g = g.replace(/^\//, "");
    if (g.endsWith("/")) g += "**";
    const alternatives = expandBraces(g).map(globBody);
    return new RegExp(`^${anyDepth ? "(?:.*/)?" : ""}(?:${alternatives.join("|")})$`);
  } catch {
    return null;
  }
}

function matchesAny(globs: string[], file: string): boolean {
  return globs.some((g) => compileGlob(g)?.test(file) ?? true);
}

function changedFiles(repo: Repo, tree: string, headTree: string | null): string[] | null {
  const base = headTree ?? git(repo.root, ["hash-object", "-t", "tree", "/dev/null"])?.trim();
  if (!base) return null;
  const out = git(repo.root, ["diff-tree", "-r", "--name-only", "-z", "--no-renames", base, tree]) ?? "";
  return out.split("\0").filter((f) => f !== "");
}

function warnOnce(repo: Repo, key: string, message: string): void {
  const marker = join(gateDir(repo), "warned", Buffer.from(key).toString("hex").slice(0, 120));
  if (existsSync(marker)) return;
  mkdirSync(dirname(marker), { recursive: true });
  writeFileSync(marker, "");
  process.stderr.write(`verify_gate: ${message}\n`);
}

function recordPath(repo: Repo, tree: string, skill: string): string {
  return join(gateDir(repo), tree, `${skill}.json`);
}

function readRecord(path: string): { verdict?: string } | null {
  try {
    const parsed: unknown = JSON.parse(readFileSync(path, "utf-8"));
    return isRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function hasVerifiedRecordAtOtherTree(repo: Repo, tree: string, skill: string): boolean {
  if (!existsSync(gateDir(repo))) return false;
  for (const dir of readdirSync(gateDir(repo))) {
    if (dir === tree || !/^[0-9a-f]{40,64}$/.test(dir)) continue;
    if (readRecord(join(gateDir(repo), dir, `${skill}.json`))?.verdict === "VERIFIED") return true;
  }
  return false;
}

function runCommand(skill: string): string {
  const root = process.env.CLAUDE_PLUGIN_ROOT || dirname(dirname(SCRIPT));
  return `sh ${join(root, "scripts", "run-ts")} ${join(root, "scripts", "verify_gate.ts")} run --skill ${skill} -- <the check command>`;
}

function run(argv: string[]): number {
  const dash = argv.indexOf("--");
  const flags = dash === -1 ? argv : argv.slice(0, dash);
  const command = dash === -1 ? [] : argv.slice(dash + 1);
  const skill = flags[0] === "--skill" ? flags[1] : undefined;
  if (!skill || !/^[\w.-]+$/.test(skill) || command.length === 0) {
    process.stderr.write("usage: verify_gate.ts run --skill <name> -- <command...>\n");
    return 2;
  }
  const repo = findRepo(process.cwd());
  if (repo === null) {
    process.stderr.write("verify_gate: run inside a git repository\n");
    return 2;
  }
  const before = treeHash(repo);
  if (before === null) {
    process.stderr.write("verify_gate: could not hash the working tree\n");
    return 2;
  }
  const result = spawnSync(command[0], command.slice(1), { stdio: "inherit" });
  if (result.error) process.stderr.write(`verify_gate: ${result.error.message}\n`);
  const exit = result.status ?? (result.error ? 127 : 1);
  const after = treeHash(repo);
  const verdict: Verdict = after !== before ? "INCONCLUSIVE" : exit === 0 ? "VERIFIED" : "NOT VERIFIED";
  const path = recordPath(repo, before, skill);
  mkdirSync(dirname(path), { recursive: true });
  const record = { tree: before, skill, verdict, command, exit, at: new Date().toISOString() };
  writeFileSync(path, `${JSON.stringify(record, null, 2)}\n`);
  process.stdout.write(`verify_gate: ${skill} ${verdict} (tree ${before.slice(0, 10)})\n`);
  return verdict === "INCONCLUSIVE" && exit === 0 ? 3 : exit;
}

type GitCommit = { cwd: string; args: string[] };

function asksForHelp(args: string[]): boolean {
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--help" || args[i] === "-h") return true;
    if (FLAGS_WITH_VALUE_BEFORE_HELP.has(args[i]) || /^-[A-Za-z]*[mFCct]$/.test(args[i])) i++;
  }
  return false;
}

function gitCommitSegment(words: string[], cwd: string): GitCommit | null {
  if (words[0] !== "git") return null;
  let dir = cwd;
  let i = 1;
  while (i < words.length && words[i] !== "commit") {
    const w = words[i];
    if (w === "-C" && i + 1 < words.length) {
      dir = resolve(dir, words[i + 1]);
      i += 2;
    } else if ((w === "-c" || w === "--git-dir" || w === "--work-tree" || w === "--namespace") && i + 1 < words.length) {
      i += 2;
    } else if (w.startsWith("-")) {
      i += 1;
    } else {
      return null;
    }
  }
  if (i >= words.length) return null;
  const args = words.slice(i + 1);
  return asksForHelp(args) ? null : { cwd: dir, args };
}

function stripHeredocs(command: string): string {
  const lines = command.split("\n");
  const kept: string[] = [];
  let quote = "";
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    let cut = line.length;
    const pending: { delimiter: string; indented: boolean }[] = [];
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (quote === "'") {
        if (c === "'") quote = "";
      } else if (c === "\\") {
        i++;
      } else if (quote === '"') {
        if (c === '"') quote = "";
      } else if (c === "'" || c === '"') {
        quote = c;
      } else if (c === "#" && (i === 0 || /[\s;&|(]/.test(line[i - 1]))) {
        cut = i;
        break;
      } else if (c === "(" && line[i + 1] === "(") {
        let depth = 0;
        let k = i;
        for (; k < line.length; k++) {
          if (line[k] === "(") depth++;
          if (line[k] === ")" && --depth === 0) break;
        }
        i = k;
      } else if (c === "<" && line[i + 1] === "<" && line[i + 2] === "<") {
        i += 2;
      } else if (c === "<" && line[i + 1] === "<") {
        const m = /^<<(-?)\s*(?:'([^']+)'|"([^"]+)"|([^\s;&|()<>'"]+))/.exec(line.slice(i));
        if (m) {
          pending.push({ delimiter: m[2] ?? m[3] ?? m[4], indented: m[1] === "-" });
          i += m[0].length - 1;
        }
      }
    }
    kept.push(line.slice(0, cut));
    if (quote !== "") continue;
    for (const { delimiter, indented } of pending) {
      while (li + 1 < lines.length) {
        li++;
        if ((indented ? lines[li].replace(/^\t+/, "") : lines[li]) === delimiter) break;
      }
    }
  }
  return kept.join("\n");
}

function normalizeWords(input: string[]): string[] {
  let words = input;
  for (;;) {
    const first = words[0];
    if (first === undefined) return words;
    const name = basename(first);
    if (first.startsWith("-")) {
      words = words.slice(ENV_FLAGS_WITH_VALUE.has(first) ? 2 : 1);
    } else if (ENV_ASSIGNMENT.test(first) || SHELL_KEYWORDS.has(first) || PLAIN_WRAPPERS.has(name)) {
      words = words.slice(1);
    } else if (name === "sudo") {
      words = words.slice(1);
      while (words[0]?.startsWith("-")) words = words.slice(SUDO_FLAGS_WITH_VALUE.has(words[0]) ? 2 : 1);
    } else if (name === "nice") {
      words = words.slice(1);
      while (words[0]?.startsWith("-")) words = words.slice(NICE_FLAGS_WITH_VALUE.has(words[0]) ? 2 : 1);
    } else if (name === "timeout") {
      words = words.slice(1);
      while (words[0]?.startsWith("-")) words = words.slice(TIMEOUT_FLAGS_WITH_VALUE.has(words[0]) ? 2 : 1);
      words = words.slice(1);
    } else {
      return [name, ...words.slice(1)];
    }
  }
}

function shellPayload(words: string[]): string | null {
  if (!SHELLS.has(words[0])) return null;
  const at = words.findIndex((w, i) => i > 0 && /^-[A-Za-z]*c[A-Za-z]*$/.test(w));
  return at === -1 ? null : (words[at + 1] ?? null);
}

function cdTarget(words: string[], dir: string, sessionCwd: string): string {
  const target = words.slice(1).find((w) => w === "-" || !w.startsWith("-"));
  if (target === undefined || target === "-") return sessionCwd;
  return resolve(dir, target === "~" || target.startsWith("~/") ? join(homedir(), target.slice(1)) : target);
}

function findCommits(command: string, sessionCwd: string, depth = 0): GitCommit[] {
  const commits: GitCommit[] = [];
  let dir = sessionCwd;
  for (const segment of splitSegments(stripHeredocs(command))) {
    const words = normalizeWords(commandWords(segment));
    if (words[0] === "cd") {
      dir = cdTarget(words, dir, sessionCwd);
      continue;
    }
    const payload = shellPayload(words);
    if (payload !== null) {
      if (depth < MAX_SHELL_DEPTH) commits.push(...findCommits(payload, dir, depth + 1));
      continue;
    }
    const commit = gitCommitSegment(words, dir);
    if (commit !== null) commits.push(commit);
  }
  return commits;
}

function commitMessages(commit: GitCommit, command: string): string[] {
  const messages: string[] = [];
  const args = commit.args;
  const readFile = (file: string) => {
    if (file === "-" || file === "/dev/stdin") {
      messages.push(command);
      return;
    }
    try {
      messages.push(readFileSync(isAbsolute(file) ? file : join(commit.cwd, file), "utf-8"));
    } catch {
      return;
    }
  };
  for (let i = 0; i < args.length; i++) {
    const w = args[i];
    if (w === "--") break;
    if (w === "--message" && i + 1 < args.length) {
      messages.push(args[++i]);
    } else if (w === "--file" && i + 1 < args.length) {
      readFile(args[++i]);
    } else if (w === "--trailer" && i + 1 < args.length) {
      messages.push(args[++i]);
    } else if (w.startsWith("--trailer=")) {
      messages.push(w.slice("--trailer=".length));
    } else if (w.startsWith("--message=")) {
      messages.push(w.slice("--message=".length));
    } else if (w.startsWith("--file=")) {
      readFile(w.slice("--file=".length));
    } else if (/^-[A-Za-z]+/.test(w) && !w.startsWith("--")) {
      const letters = w.slice(1);
      const at = letters.search(/[mF]/);
      if (at === -1) continue;
      const rest = letters.slice(at + 1);
      const value = rest !== "" ? rest : args[++i];
      if (value === undefined) continue;
      if (letters[at] === "m") messages.push(value);
      else readFile(value);
    }
  }
  return messages;
}

function blocksPath(repo: Repo, session: string): string {
  return join(gateDir(repo), "blocks", session.replace(/[^A-Za-z0-9_-]/g, "_"));
}

function blockCount(repo: Repo, session: string): number {
  try {
    return Number.parseInt(readFileSync(blocksPath(repo, session), "utf-8"), 10) || 0;
  } catch {
    return 0;
  }
}

function logLine(repo: Repo, entry: Record<string, unknown>): void {
  mkdirSync(gateDir(repo), { recursive: true });
  appendFileSync(join(gateDir(repo), "log.jsonl"), `${JSON.stringify({ at: new Date().toISOString(), ...entry })}\n`);
}

function modeFromEnv(): Mode {
  const mode = process.env.SWE_VERIFY_GATE;
  return mode === "off" || mode === "enforce" ? mode : "observe";
}

function checkCommit(commit: GitCommit, command: string, session: string): number {
  const mode = modeFromEnv();
  if (mode === "off") return 0;
  const repo = findRepo(commit.cwd);
  if (repo === null) return 0;
  const skills = verifySkills(repo.root);
  if (skills.length === 0) return 0;
  if (commitMessages(commit, command).some((m) => ESCAPE_LINE.test(m))) return 0;

  const headTree = git(repo.root, ["rev-parse", "--verify", "-q", "HEAD^{tree}"])?.trim() || null;
  const tracked = (git(repo.root, ["ls-files", "-z"]) ?? "").split("\0");
  for (const skill of skills) {
    if (skill.paths === null) {
      warnOnce(repo, `nopaths-${skill.name}`, `${skill.name} sets no paths, so no commit requires it. Add a paths list to its SKILL.md.`);
      continue;
    }
    for (const glob of skill.paths) {
      const re = compileGlob(glob);
      if (re === null) {
        warnOnce(repo, `unparseable-${skill.name}-${glob}`, `cannot parse path glob "${glob}" in ${skill.name}. The skill is required for every commit that changes any file.`);
      } else if (headTree !== null && !tracked.some((f) => re.test(f))) {
        warnOnce(repo, `stale-${skill.name}-${glob}`, `${skill.name} path glob "${glob}" matches no tracked file. The list may be stale.`);
      }
    }
  }

  const tree = treeHash(repo);
  if (tree === null) return 0;
  const changed = changedFiles(repo, tree, headTree);
  if (changed === null) return 0;
  const required = skills.filter((s) => s.paths !== null && changed.some((f) => matchesAny(s.paths as string[], f))).map((s) => s.name);
  const missing = required.filter((name) => readRecord(recordPath(repo, tree, name))?.verdict !== "VERIFIED");
  if (missing.length === 0) return 0;

  if (mode === "observe") {
    logLine(repo, { session_id: session, tree, required, missing, decision: "would-block" });
    return 0;
  }
  const count = blockCount(repo, session);
  if (count >= MAX_BLOCKS_PER_SESSION) {
    writeFileSync(blocksPath(repo, session), "0");
    logLine(repo, { session_id: session, tree, required, missing, decision: "allowed-after-blocks" });
    return 0;
  }
  mkdirSync(dirname(blocksPath(repo, session)), { recursive: true });
  writeFileSync(blocksPath(repo, session), String(count + 1));
  logLine(repo, { session_id: session, tree, required, missing, decision: "blocked" });

  const lines = ["Commit blocked by the verify gate: no passing verify result for the files in this commit."];
  for (const name of missing) {
    const stale = hasVerifiedRecordAtOtherTree(repo, tree, name);
    lines.push(`- ${name}: ${stale ? "verify result is stale: files changed since the run." : "no VERIFIED result for this tree."}`);
    lines.push(`  Run: ${runCommand(name)}`);
  }
  lines.push('To commit without a check, add a line to the commit message: "Verification: none (<reason>)".');
  process.stderr.write(`${lines.join("\n")}\n`);
  return 2;
}

function hook(): number {
  try {
    const event: unknown = JSON.parse(readFileSync(0, "utf-8"));
    if (!isRecord(event) || !isRecord(event.tool_input)) return 0;
    const command = event.tool_input.command;
    if (typeof command !== "string" || !command.includes("commit")) return 0;
    const cwd = typeof event.cwd === "string" ? event.cwd : process.cwd();
    const session = typeof event.session_id === "string" ? event.session_id : "unknown";
    for (const commit of findCommits(command, cwd)) {
      const rc = checkCommit(commit, command, session);
      if (rc !== 0) return rc;
    }
    return 0;
  } catch (error) {
    process.stderr.write(`verify_gate: skipped, ${error instanceof Error ? error.message : String(error)}\n`);
    return 0;
  }
}

function sessionStart(): number {
  let cwd = process.cwd();
  try {
    const event: unknown = JSON.parse(readFileSync(0, "utf-8"));
    if (isRecord(event) && typeof event.cwd === "string") cwd = event.cwd;
  } catch {
    cwd = process.cwd();
  }
  const repo = findRepo(cwd);
  if (repo === null || verifySkills(repo.root).length === 0) return 0;
  process.stdout.write(
    `Commit gate: run each verify-* skill's check as \`${runCommand("<skill-name>")}\`; a commit that touches a skill's paths needs its VERIFIED result.\n`,
  );
  return 0;
}

function main(): number {
  const [command, ...rest] = process.argv.slice(2);
  if (command === "run") return run(rest);
  if (command === "hook") return hook();
  if (command === "session-start") return sessionStart();
  process.stderr.write("usage: verify_gate.ts run --skill <name> -- <command...> | hook | session-start\n");
  return 2;
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
