import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { isMain } from "../scripts/is_main.ts";

const SKILL = resolve(dirname(fileURLToPath(import.meta.url)), "..", "skills", "using-rex");

function stripFrontmatter(text: string): string {
  if (text.startsWith("---\n")) {
    const end = text.indexOf("\n---\n", 4);
    if (end !== -1) return text.slice(end + 5).replace(/^\n+/, "");
  }
  return text;
}

function isHeadless(): boolean {
  return process.env.CLAUDE_CODE_ENTRYPOINT === "sdk-cli";
}

function main(): number {
  if (!process.env.REX_SESSION || isHeadless()) return 0;
  console.log(`Skill folder: ${SKILL}\n`);
  console.log(stripFrontmatter(readFileSync(join(SKILL, "SKILL.md"), "utf8")));
  return 0;
}

if (isMain(import.meta.url)) process.exit(main());
