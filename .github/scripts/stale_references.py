#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Fail when a tracked file points at a path, heading, skill, or step that does not exist.

Agents follow pointers literally, so a rename or removal that leaves a pointer behind sends
them to nothing. This checks the pointers that have a resolvable form:

- a Markdown link to a repo path, and its `#anchor` against the target's headings;
- a `<plugin>:<name>` skill or agent name, also in JSON and in the eval corpus;
- a `"route/<plugin>/<name>"` eval target, against the plugin's playbooks and skills;
- "the X section" and a backticked step handle, when the sentence names one file;
- a bare `#N`, because this repo's PR numbers restarted on 2026-11-17.

A section or step reference that names no file is skipped and counted. Step-line
parentheses are `evals/skills/facets.py check`'s job, not this script's. EVIDENCE.md
records past runs, so the skill names in it are exempt.
"""

import re
import subprocess
import sys
import urllib.parse
from functools import cache
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
SKIP = re.compile(r"(^|/)(fixtures|node_modules)/")
FENCE = re.compile(r"^\s*(```|~~~)")
CODE = re.compile(r"``.+?``|`[^`]+`")
LINK = re.compile(r"\[([^\]]*)\]\(<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\)")
REF_DEF = re.compile(r"^\s*\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"")
STEP_DEF = re.compile(r"^(?:\s*\d+\.\s+`|#{2,4}\s+)?(\d+-[a-z0-9][a-z0-9-]*)`?:?")
HANDLE = re.compile(r"`(\d+-[a-z0-9][a-z0-9-]*)`")
SECTION = re.compile(r"\b(sections?)\b")
ITEM = re.compile(r"\"[^\"]+\"|[A-Z0-9][\w./+-]*(?: [\w'/-]+){0,4}")
BARE_PR = re.compile(r"(?<![\w/&#\]])#(\d+)\b")
ROUTE = re.compile(r"\"route/([a-z]+)/([a-z][a-z0-9-]*)\"")
DEFINED = re.compile(r"\"([^\"]+)\" section")
HISTORY = re.compile(r"(^|/)EVIDENCE\.md$")


def tracked():
    out = subprocess.run(
        ["git", "-C", ROOT, "ls-files", "-z"], capture_output=True, check=True
    )
    return [p for p in out.stdout.decode().split("\0") if p and not SKIP.search(p)]


def slug(text):
    text = LINK.sub(r"\1", text).replace("`", "").replace("*", "").strip().lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


@cache
def outline(path):
    """Return a file's anchors, normalized heading names, and step handles."""
    anchors, names, steps, seen, fenced = set(), set(), set(), {}, False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        anchors.update(HTML_ANCHOR.findall(line))
        names.update(slug(n).replace("-", " ") for n in DEFINED.findall(line))
        if heading := HEADING.match(line):
            base = slug(heading.group(2))
            count = seen.get(base, 0)
            seen[base] = count + 1
            anchors.add(base if count == 0 else f"{base}-{count}")
            names.add(slug(heading.group(2)).replace("-", " "))
        elif bold := re.fullmatch(r"\*\*(.+?)\*\*:?", line.strip()):
            names.add(slug(bold.group(1)).replace("-", " "))
        if step := STEP_DEF.match(line):
            steps.add(step.group(1))
    return anchors, names, steps


def plugin_of(rel):
    parts = rel.split("/")
    return parts[1] if parts[0] == "plugins" and len(parts) > 2 else None


def resolve_name(plugin, name):
    """Resolve a bare skill, principle, playbook, or reference name inside one plugin."""
    base = ROOT / "plugins" / plugin
    hits = {
        base / "skills" / name / "SKILL.md",
        base / "skills" / f"principle-{name}" / "SKILL.md",
        base / "references" / f"{name}.md",
    }
    hits = {p for p in hits if p.is_file()}
    hits |= set(base.glob(f"skills/*/playbooks/{name}.md")) | set(
        base.glob(f"skills/*/references/{name}.md")
    )
    return hits.pop() if len(hits) == 1 else None


def resolve_path(source, target):
    target = urllib.parse.unquote(target)
    if not target:
        return source
    path = (
        (ROOT / target.lstrip("/"))
        if target.startswith("/")
        else (source.parent / target)
    )
    return path.resolve()


def pointers(rel, source, text):
    """Every file a sentence points at: links, backticked names or paths, and `x router`."""
    found, plugin = [], plugin_of(rel)
    for match in LINK.finditer(text):
        target = match.group(2).split("#")[0]
        if not re.match(r"[a-z][a-z0-9+.-]*:", target):
            found.append((match.start(), resolve_path(source, target)))
    for match in re.finditer(
        r"`([^`\s]+)`|\b([a-z][a-z0-9-]+) (?:router|skill|playbook)\b", text
    ):
        token = match.group(1) or match.group(2)
        hit = (
            resolve_name(plugin, token)
            if plugin and re.fullmatch(r"[a-z][a-z0-9-]*", token)
            else None
        )
        if hit is None and token.endswith(".md"):
            hit = next(
                (p for p in (source.parent / token, ROOT / token) if p.is_file()), None
            )
        if hit is not None:
            found.append((match.start(), hit.resolve()))
    return [
        (pos, p) for pos, p in found if p.suffix in {".md", ".toml"} and p.is_file()
    ]


def referent(rel, source, sentence, end, step_line):
    """The one file a reference ending at `end` names, or None when it names no file or several."""
    after = [
        p for pos, p in pointers(rel, source, sentence[end : end + 80]) if pos < 12
    ]
    if re.match(r"\s+(?:of|in)\b", sentence[end:]):
        return after[0] if after else None
    files = {p for _, p in pointers(rel, source, sentence)}
    if not files and step_line:
        files = {p for p in (resolve_name(plugin_of(rel), n) for n in step_line) if p}
    return files.pop() if len(files) == 1 else None


def section_names(sentence, end):
    """Parse "the A, B, and C" that ends at `end` into its items, or None."""
    words = list(re.finditer(r"\b(?:the|its|The|Its)\s", sentence[:end]))
    for word in reversed(words[-6:]):
        body = sentence[word.end() : end].strip()
        items = [i for i in re.split(r",\s*(?:and\s+)?|\s+and\s+", body) if i]
        if items and all(ITEM.fullmatch(i) for i in items):
            return [i.strip('"') for i in items]
    return None


def units(lines):
    """Yield (line number, text, offsets) per sentence of prose, outside fences."""
    block, fenced = [], False

    def flush():
        if block:
            text, offsets = "", []
            for number, line in block:
                offsets.append((len(text), number))
                text += line.strip() + " "
            for match in re.finditer(r".+?(?:(?<!\b\d)[.!?;|](?=\s)|$)", text):
                start = max(n for o, n in offsets if o <= match.start())
                yield start, match.group(0)
            block.clear()

    for number, line in enumerate(lines, 1):
        if FENCE.match(line):
            fenced = not fenced
            yield from flush()
            continue
        if fenced:
            continue
        if (
            not line.strip()
            or re.match(r"\s*([-*|#>]|\d+\.)\s|\s*\|", line)
            or STEP_DEF.match(line)
        ):
            yield from flush()
        if line.strip():
            block.append((number, line))
    yield from flush()


def check_file(rel, errors, stats):
    source = ROOT / rel
    lines = source.read_text(encoding="utf-8").splitlines()
    markdown, prose = rel.endswith(".md"), rel.endswith((".md", ".toml"))
    names = re.compile(rf"(?<![\w-])({'|'.join(PLUGINS)}):([a-z][a-z0-9-]*)(?![\w-])")
    fenced = False
    for number, line in enumerate(lines, 1):
        for match in () if HISTORY.search(rel) else names.finditer(line):
            plugin, name = match.groups()
            base = ROOT / "plugins" / plugin
            stats["names"] += 1
            if not (
                (base / "skills" / name / "SKILL.md").is_file()
                or (base / "agents" / f"{name}.md").is_file()
            ):
                errors.append(
                    f"{rel}:{number} names {plugin}:{name}, which is not a skill or agent of the "
                    f"{plugin} plugin; name an existing one or restore it."
                )
        for match in ROUTE.finditer(line):
            plugin, name = match.groups()
            base = ROOT / "plugins" / plugin
            stats["names"] += 1
            if not (
                (base / "skills" / name / "SKILL.md").is_file()
                or any(base.glob(f"skills/*/playbooks/{name}.md"))
            ):
                errors.append(
                    f"{rel}:{number} targets route/{plugin}/{name}, which is not a playbook or skill "
                    f"of the {plugin} plugin; target an existing one or restore it."
                )
        if not markdown:
            continue
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        plain = CODE.sub(lambda m: " " * len(m.group(0)), line)
        targets = [m.group(2) for m in LINK.finditer(plain)] + REF_DEF.findall(plain)
        for target in targets:
            if re.match(r"[a-z][a-z0-9+.-]*:", target) or re.search(r"[<{$*]", target):
                continue
            stats["links"] += 1
            path_part, _, anchor = target.partition("#")
            path = resolve_path(source, path_part)
            shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
            if not path.exists():
                errors.append(
                    f"{rel}:{number} links to {shown}, which does not exist; "
                    f"point it at an existing path or restore the file."
                )
            elif (
                anchor
                and path.is_file()
                and path.suffix == ".md"
                and anchor.lower() not in outline(path)[0]
            ):
                errors.append(
                    f"{rel}:{number} links to heading #{anchor} of {shown}, which has no such "
                    f"heading; point it at an existing heading or restore the heading."
                )
        for match in BARE_PR.finditer(LINK.sub(lambda m: " " * len(m.group(0)), plain)):
            if not HEADING.match(line) or match.start() > 0:
                errors.append(
                    f"{rel}:{number} cites #{match.group(1)} bare. This repo's PR numbers restarted "
                    f"on 2026-11-17, so it links to the wrong PR or none; write a full URL or a commit SHA."
                )
    if not prose:
        return
    for number, sentence in units(lines):
        parens = re.search(
            r"\(([a-z][a-z0-9-]*(?:, [a-z][a-z0-9-]*)*)\)\s*$", lines[number - 1]
        )
        step_line = (
            parens.group(1).split(", ")
            if parens and STEP_DEF.match(lines[number - 1])
            else []
        )
        plain = CODE.sub(lambda m: " " * len(m.group(0)), sentence)
        for match in SECTION.finditer(plain):
            items = section_names(plain, match.start())
            if not items:
                continue
            stats["sections"] += 1
            path = referent(rel, source, sentence, match.end(), step_line)
            if path is None:
                stats["skipped"] += 1
                continue
            known = outline(path)[1]
            for item in items:
                if slug(item).replace("-", " ") not in known:
                    errors.append(
                        f'{rel}:{number} names section "{item}" of {path.relative_to(ROOT)}, which has '
                        f"no such heading; point it at an existing heading or restore the heading."
                    )
        definition = STEP_DEF.match(sentence)
        for match in HANDLE.finditer(sentence):
            if (
                definition
                and definition.group(1) == match.group(1)
                and sentence.find(match.group(0)) < 8
            ):
                continue
            stats["steps"] += 1
            path = referent(rel, source, sentence, match.end(), [])
            if path is None:
                stats["skipped"] += 1
            elif match.group(1) not in outline(path)[2]:
                errors.append(
                    f"{rel}:{number} names step {match.group(1)} of {path.relative_to(ROOT)}, which has "
                    f"no such step; point it at an existing step or restore the step."
                )


PLUGINS = sorted(p.name for p in (ROOT / "plugins").iterdir() if p.is_dir())


def main():
    errors, stats = (
        [],
        dict.fromkeys(["links", "names", "sections", "steps", "skipped"], 0),
    )
    for rel in tracked():
        if rel.endswith((".md", ".toml", ".json", ".jsonl")) and (ROOT / rel).is_file():
            check_file(rel, errors, stats)
    print(
        *errors,
        f"{len(errors)} stale reference(s). Checked {stats['links']} links, {stats['names']} skill names and eval targets, "
        f"{stats['sections']} section and {stats['steps']} step references; skipped {stats['skipped']} "
        f"that name no single file.",
        sep="\n",
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
