/**
 * List this project's agent transcripts, newest first.
 *
 * Claude Code keeps one JSONL file per session in
 * ~/.claude/projects/<slug>/<session-id>.jsonl. The slug is the session's
 * working directory with every character that is not a letter or a digit
 * changed to "-". Subagent transcripts sit in
 * <slug>/<session-id>/subagents/*.jsonl.
 *
 * Codex keeps one rollout file per session in
 * ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl. Its first line is a
 * session_meta record that names the working directory.
 *
 * The script matches only the working directories of this repository: the main
 * checkout and each linked worktree. It prints paths and modification times. It
 * never prints transcript content, and it never lists a transcript of another
 * project.
 */

import { closeSync, openSync, readdirSync, readSync, realpathSync, statSync } from "node:fs";
import { homedir } from "node:os";
import { join, resolve, sep } from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const SCRIPT = realpathSync(fileURLToPath(import.meta.url));

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isDirectory(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** Return the main checkout and every worktree of the repository at cwd. */
function projectDirs(cwd: string): string[] {
  const result = spawnSync("git", ["-C", cwd, "worktree", "list", "--porcelain"], { encoding: "utf-8" });
  if (result.error || result.status !== 0) return [resolve(cwd)];
  const dirs = result.stdout
    .split(/\r\n|[\n\r]/)
    .filter((line) => line.startsWith("worktree "))
    .map((line) => line.slice("worktree ".length));
  return dirs.length > 0 ? dirs : [resolve(cwd)];
}

function claudeSlug(path: string): string {
  return path.replace(/[^A-Za-z0-9]/g, "-");
}

function claudeTranscripts(dirs: string[], subagents: boolean): string[] {
  const root = join(homedir(), ".claude", "projects");
  const found: string[] = [];
  for (const dir of dirs) {
    const project = join(root, claudeSlug(dir));
    if (!isDirectory(project)) continue;
    for (const name of readdirSync(project)) {
      if (name.endsWith(".jsonl")) found.push(join(project, name));
    }
    if (subagents) {
      for (const name of readdirSync(project)) {
        const sub = join(project, name, "subagents");
        if (!isDirectory(sub)) continue;
        for (const file of readdirSync(sub)) {
          if (file.endsWith(".jsonl")) found.push(join(sub, file));
        }
      }
    }
  }
  return found;
}

/** Read only the first line, as the Python version does; rollout files grow large. */
function firstLine(path: string): string {
  const fd = openSync(path, "r");
  try {
    const chunks: Buffer[] = [];
    const buf = Buffer.alloc(8192);
    for (;;) {
      const n = readSync(fd, buf, 0, buf.length, null);
      if (n === 0) break;
      const chunk = buf.subarray(0, n);
      const nl = chunk.indexOf(0x0a);
      if (nl >= 0) {
        chunks.push(chunk.subarray(0, nl));
        break;
      }
      chunks.push(Buffer.from(chunk));
    }
    return Buffer.concat(chunks).toString("utf-8");
  } finally {
    closeSync(fd);
  }
}

function codexCwd(path: string): string | null {
  let first: unknown;
  try {
    first = JSON.parse(firstLine(path));
  } catch {
    return null;
  }
  if (!isRecord(first)) return null;
  const payload = first.type === "session_meta" ? first.payload : first;
  if (isRecord(payload) && typeof payload.cwd === "string") return payload.cwd;
  return null;
}

function walkJsonl(root: string, found: string[]): void {
  for (const entry of readdirSync(root, { withFileTypes: true })) {
    const path = join(root, entry.name);
    if (entry.isDirectory()) {
      walkJsonl(path, found);
    } else if (entry.name.endsWith(".jsonl")) {
      found.push(path);
    }
  }
}

function codexTranscripts(dirs: string[], since: number): string[] {
  const root = join(process.env.CODEX_HOME || join(homedir(), ".codex"), "sessions");
  if (!isDirectory(root)) return [];
  const wanted = dirs.map(String);
  const candidates: string[] = [];
  walkJsonl(root, candidates);
  const found: string[] = [];
  for (const path of candidates) {
    if (statSync(path).mtimeMs / 1000 < since) continue;
    const cwd = codexCwd(path);
    if (cwd === null) continue;
    if (wanted.some((w) => cwd === w || cwd.startsWith(w + sep))) found.push(path);
  }
  return found;
}

const PROG = "transcripts.ts";
const USAGE = `usage: ${PROG} [-h] [--days DAYS] [--host {claude,codex,all}] [--subagents] [--exclude EXCLUDE] [--cwd CWD]`;

function usageError(message: string): never {
  process.stderr.write(`${USAGE}\n${PROG}: error: ${message}\n`);
  process.exit(2);
}

function helpText(): string {
  return (
    `${USAGE}\n\n` +
    "List this project's agent transcripts, newest first.\n\n" +
    "options:\n" +
    "  -h, --help            show this help message and exit\n" +
    "  --days DAYS           window in days (default 7; 0 for all)\n" +
    "  --host {claude,codex,all}\n" +
    "  --subagents           include Claude Code subagent transcripts\n" +
    "  --exclude EXCLUDE     session id to skip, such as the current one\n" +
    "  --cwd CWD             a directory in the repository (default: here)\n"
  );
}

type Args = { days: number; host: string; subagents: boolean; exclude: string[]; cwd: string };

function longOption(token: string, names: string[]): string {
  if (names.includes(token)) return token;
  const matches = names.filter((n) => n.startsWith(token));
  if (matches.length === 1) return matches[0];
  usageError(`unrecognized arguments: ${token}`);
}

function parseArgs(argv: string[]): Args | null {
  const args: Args = { days: 7, host: "all", subagents: false, exclude: [], cwd: process.cwd() };
  const names = ["--days", "--host", "--subagents", "--exclude", "--cwd"];
  for (let i = 0; i < argv.length; i++) {
    const token = argv[i];
    if (token === "-h" || token === "--help") return null;
    if (!token.startsWith("--")) usageError(`unrecognized arguments: ${token}`);
    const eq = token.indexOf("=");
    const name = longOption(eq >= 0 ? token.slice(0, eq) : token, names);
    const takesValue = name !== "--subagents";
    let value = eq >= 0 ? token.slice(eq + 1) : null;
    if (takesValue && value === null) {
      if (i + 1 >= argv.length) usageError(`argument ${name}: expected one argument`);
      value = argv[++i];
    }
    if (!takesValue && value !== null) usageError(`argument ${name}: ignored explicit argument '${value}'`);
    if (name === "--days") {
      const days = Number(value);
      if (value === "" || Number.isNaN(days)) usageError(`argument --days: invalid float value: '${value}'`);
      args.days = days;
    } else if (name === "--host") {
      if (value !== "claude" && value !== "codex" && value !== "all") {
        usageError(`argument --host: invalid choice: '${value}' (choose from 'claude', 'codex', 'all')`);
      }
      args.host = value;
    } else if (name === "--subagents") {
      args.subagents = true;
    } else if (name === "--exclude") {
      args.exclude.push(value as string);
    } else {
      args.cwd = value as string;
    }
  }
  return args;
}

function stamp(mtime: number): string {
  const d = new Date(mtime * 1000);
  const pad = (n: number): string => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function main(argv: string[]): number {
  const args = parseArgs(argv);
  if (args === null) {
    process.stdout.write(helpText());
    return 0;
  }
  const since = args.days <= 0 ? 0 : Date.now() / 1000 - args.days * 86400;
  const dirs = projectDirs(args.cwd);
  const paths: string[] = [];
  if (args.host === "claude" || args.host === "all") paths.push(...claudeTranscripts(dirs, args.subagents));
  if (args.host === "codex" || args.host === "all") paths.push(...codexTranscripts(dirs, since));

  const rows: Array<[number, string]> = [];
  for (const path of new Set(paths)) {
    const mtime = statSync(path).mtimeMs / 1000;
    if (mtime < since || args.exclude.some((s) => s !== "" && path.includes(s))) continue;
    rows.push([mtime, path]);
  }
  rows.sort((a, b) => b[0] - a[0] || (a[1] < b[1] ? 1 : a[1] > b[1] ? -1 : 0));
  for (const [mtime, path] of rows) {
    process.stdout.write(`${stamp(mtime)}\t${path}\n`);
  }
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

if (invokedDirectly()) process.exitCode = main(process.argv.slice(2));
