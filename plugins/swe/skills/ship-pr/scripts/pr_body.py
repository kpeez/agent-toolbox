#!/usr/bin/env python3
"""Build a pull-request body from templates/pr-body.md, or check a published one.

render: fill each {slot} of the template from <slot>.md in a folder. The agent
writes slot content only; the headings come from the template.
check: confirm a body is the template with its slots filled, as CI does.
Both reject a heading inside a slot and any requester attribution.
"""

import argparse
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "pr-body.md"
SLOT = re.compile(r"\{(\w+)\}")
LINK = re.compile(r"^(?:Fixes|Part of) [\w#/.-]+$")
FENCE = re.compile(r"^\s*(```|~~~)")

VERBS = (
    r"(?:wants?|wanted|asked|asks|requested|requests|said|says|prefers?|preferred"
    r"|approved|approves|decided|decides|instructed|insisted|told|chose)"
)
ATTRIBUTION = [
    rf"(?i)\b(?:the |our )?user {VERBS}\b",
    rf"(?i)\byou {VERBS}\b",
    r"(?i)\b(?:as|per) (?:you|the user|requested|asked|instructed|discussed|agreed)\b",
    r"(?i)\bper (?:your|the user'?s|their|his|her) (?:request|ask|instructions?|wishes)\b",
    r"(?i)\b(?:requested|asked for|approved) by\b",
    r"(?i)\b(?:in|from|during) (?:the|this|our) (?:chat|conversation|session)\b",
    rf"\b(?!(?:This|That|It|Which|What)\b)[A-Z][a-z]+ {VERBS}\b",
    r"\b[A-Z][a-z]+'s (?:request|ask|decisions?|preference|instructions?)\b",
]


def slot_errors(name, text):
    if not text.strip():
        return [f"{name}: empty."]
    errors = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = re.sub(r"`[^`]*`", "", line)
        if re.match(r"^#{1,6} ", prose):
            errors.append(f"{name} line {number}: heading '{line.strip()}'. The template owns all headings.")
        for pattern in ATTRIBUTION:
            match = re.search(pattern, prose)
            if match:
                errors.append(
                    f"{name} line {number}: requester attribution '{match.group(0)}'. "
                    "Describe the change and the problem it solves, not who asked."
                )
    return errors


def render(folder, link):
    template = TEMPLATE.read_text(encoding="utf-8")
    slots, errors = {}, []
    for name in SLOT.findall(template):
        path = Path(folder) / f"{name}.md"
        if not path.is_file():
            errors.append(f"{name}: missing {path}.")
            continue
        slots[name] = path.read_text(encoding="utf-8").strip()
        errors += slot_errors(name, slots[name])
    if link and not LINK.match(link):
        errors.append(f"link '{link}' must be 'Fixes <key>' or 'Part of <key>'.")
    if errors:
        return None, errors
    body = SLOT.sub(lambda m: slots[m.group(1)], template).rstrip("\n") + "\n"
    return (body + f"\n{link}\n" if link else body), []


def check(body):
    template = TEMPLATE.read_text(encoding="utf-8").rstrip("\n")
    names = SLOT.findall(template)
    pattern = "".join(
        re.escape(part) if i % 2 == 0 else f"(?P<{part}>.+?)"
        for i, part in enumerate(SLOT.split(template))
    )
    match = re.fullmatch(pattern + r"(?:\n\n(?P<link>(?:Fixes|Part of) \S+))?\n*", body.replace("\r\n", "\n"), re.S)
    if not match:
        return ["body does not match templates/pr-body.md. Build it with `pr_body.py render`."]
    return [e for name in names for e in slot_errors(name, match.group(name))]


def hook():
    """PreToolUse hook: block `gh pr create|edit` unless the body file passes check."""
    import json
    import shlex

    event = json.load(sys.stdin)
    command = (event.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgh\s+pr\s+(?:create|edit)\b", command):
        return 0
    try:
        words = shlex.split(command)
    except ValueError:
        words = command.split()
    is_create = re.search(r"\bgh\s+pr\s+create\b", command) is not None
    body_file = None
    for i, word in enumerate(words):
        if word in ("--body", "-b") or word.startswith("--body="):
            return block("inline --body is not allowed. Build the body with `pr_body.py render`, then pass --body-file.")
        if word == "--fill" or word.startswith("--fill-"):
            return block("--fill writes the body from commits. Build it with `pr_body.py render`, then pass --body-file.")
        if word in ("--body-file", "-F") and i + 1 < len(words):
            body_file = words[i + 1]
        elif word.startswith("--body-file="):
            body_file = word.split("=", 1)[1]
    if body_file is None:
        return block("gh pr create needs --body-file from `pr_body.py render`.") if is_create else 0
    if body_file == "-":
        return block("--body-file - reads stdin, which this hook cannot check. Pass the rendered file.")
    path = Path(event.get("cwd") or ".") / Path(body_file).expanduser()
    if not path.is_file():
        return block(f"body file {path} does not exist yet. Run `pr_body.py render` first.")
    text = path.read_text(encoding="utf-8")
    if repo_has_own_template(Path(event.get("cwd") or ".")):
        errors = slot_errors("body", text)
        errors = [e for e in errors if "heading" not in e]
    else:
        errors = check(text)
    return block("\n".join(errors)) if errors else 0


def repo_has_own_template(cwd):
    root = next((d for d in [cwd.resolve(), *cwd.resolve().parents] if (d / ".git").exists()), None)
    if root is None:
        return False
    for folder in (root, root / ".github", root / "docs"):
        if folder.is_dir() and any(
            p.name.lower() in ("pull_request_template.md", "pull_request_template") for p in folder.iterdir()
        ):
            return True
    return False


def block(reason):
    script = Path(__file__).resolve()
    print(f"PR body blocked by ship-pr: {reason}\nRender: python3 {script} render <slot-folder> -o body.md", file=sys.stderr)
    return 2


def main():
    if sys.argv[1:] == ["hook"]:
        return hook()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("render", help="build the body from <slot>.md files")
    r.add_argument("folder", help="folder with one <slot>.md file per template slot")
    r.add_argument("--link", help="closing line, such as 'Fixes ABC-123' or 'Part of #12'")
    r.add_argument("-o", "--output", required=True, help="body file to pass to gh --body-file")
    c = sub.add_parser("check", help="check a finished body, or - for stdin")
    c.add_argument("body_file")
    args = parser.parse_args()

    if args.command == "render":
        body, errors = render(args.folder, args.link)
        if body is not None:
            Path(args.output).write_text(body, encoding="utf-8")
    else:
        text = sys.stdin.read() if args.body_file == "-" else Path(args.body_file).read_text(encoding="utf-8")
        errors = check(text)
    for error in errors:
        print(f"pr_body: {error}", file=sys.stderr)
    if errors:
        return 1
    print(f"pr_body: ok{' -> ' + args.output if args.command == 'render' else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
