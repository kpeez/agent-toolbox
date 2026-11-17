#!/usr/bin/env python3
"""Build a pull-request body from templates/pr-body.md, or check a published one.

render: fill each {slot} of the template from <slot>.md in a folder. The agent
writes slot content only; the headings come from the template.
check: confirm a body is the template with its slots filled, as CI does.
Both reject a heading inside a slot and any requester attribution.
"""

import argparse
import re
import shlex
import subprocess
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
REQUESTER_VERBS = r"(?:asked|asks|requested|requests|wants|wanted|told|instructed|insisted)"
ATTRIBUTION = [
    rf"(?i)\b(?:the |our )?user {VERBS}\b",
    rf"(?i)\byou {VERBS}\b",
    r"(?i)\b(?:as|per) (?:you|the user|requested|asked|instructed|discussed|agreed)\b",
    r"(?i)\bper (?:your|the user'?s|their|his|her) (?:request|ask|instructions?|wishes)\b",
    r"(?i)\b(?:requested|asked for|approved) by\b",
    r"(?i)\b(?:in|from|during) (?:the|this|our) (?:chat|conversation|session)\b",
    rf"\b(?!(?:This|That|It|Which|What)\b)[A-Z][a-z]+ {REQUESTER_VERBS}\b",
    r"\b[A-Z][a-z]+'s (?:request|ask|decisions?|preference|instructions?)\b",
]
SEGMENT_SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "`"}
WRAPPERS = {"{", "env", "command", "exec", "time"}
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*")


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


def _split_segments(command):
    """Tokenize a shell command and split it into command segments."""
    command = command.replace("\\\n", " ")
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace = " \t\r"
    lex.whitespace_split = False
    lex.commenters = ""
    lex.wordchars += "!#$%+,:@[]^{}"
    try:
        tokens = list(lex)
    except ValueError:
        tokens = []
        for line in command.splitlines():
            tokens.extend(line.split())
            tokens.append("\n")
    segments = []
    current = []
    for token in tokens:
        if token in SEGMENT_SEPARATORS:
            if current:
                segments.append(current)
                current = []
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _command_words(segment):
    """Drop leading env assignments and wrappers, and reduce a path to `gh`."""
    words = list(segment)
    while words and (ENV_ASSIGNMENT.match(words[0]) or words[0] in WRAPPERS):
        words.pop(0)
    if words:
        words[0] = words[0].rsplit("/", 1)[-1]
    return words


def _extract_base(args):
    base = None
    for i, word in enumerate(args):
        if word in ("--base", "-B") and i + 1 < len(args):
            base = args[i + 1]
        elif word.startswith("--base="):
            base = word.split("=", 1)[1]
        elif word.startswith("-B="):
            base = word.split("=", 1)[1]
        elif word.startswith("-B") and len(word) > 2:
            base = word[2:]
    return base


def _git_output(args, cwd):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def repo_uses_gh_stack(cwd):
    common = _git_output(["rev-parse", "--git-common-dir"], cwd)
    if not common:
        return False
    common_dir = Path(common)
    if not common_dir.is_absolute():
        common_dir = cwd / common_dir
    return (common_dir / "gh-stack").is_file()


def repo_trunks(cwd):
    head = _git_output(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd)
    if head:
        trunk = head[len("origin/"):] if head.startswith("origin/") else head
        if trunk:
            return {trunk}
    return {"main", "master"}


def _check_pr_segment(action, args, cwd):
    base = _extract_base(args)
    if base is not None and repo_uses_gh_stack(cwd) and base not in repo_trunks(cwd):
        return block_stack(
            f"this repo uses gh-stack, so --base {base!r} is not allowed. "
            "Publish stacked branches with `gh stack link` or `gh stack submit` instead, "
            "then update each PR body with `gh pr edit <n> --body-file <rendered>`."
        )
    body_file = None
    for i, word in enumerate(args):
        if word == "--body" or word.startswith(("--body=", "-b")):
            return block("inline --body is not allowed. Build the body with `pr_body.py render`, then pass --body-file.")
        if word == "--fill" or word.startswith("--fill-"):
            return block("--fill writes the body from commits. Build it with `pr_body.py render`, then pass --body-file.")
        if word in ("--body-file", "-F") and i + 1 < len(args):
            body_file = args[i + 1]
        elif word.startswith("--body-file="):
            body_file = word.split("=", 1)[1]
        elif word.startswith("-F") and len(word) > 2:
            body_file = word[3:] if word.startswith("-F=") else word[2:]
    if body_file is None:
        return block("gh pr create needs --body-file from `pr_body.py render`.") if action == "create" else 0
    if body_file == "-":
        return block("--body-file - reads stdin, which this hook cannot check. Pass the rendered file.")
    path = cwd / Path(body_file).expanduser()
    if not path.is_file():
        return block(f"body file {path} does not exist yet. Run `pr_body.py render` first.")
    text = path.read_text(encoding="utf-8")
    if repo_has_own_template(cwd):
        errors = slot_errors("body", text)
        errors = [e for e in errors if "heading" not in e]
    else:
        errors = check(text)
    return block("\n".join(errors)) if errors else 0


def hook():
    """PreToolUse hook: enforce PR body checks and gh-stack publishing on `gh pr create|edit`."""
    import json

    event = json.load(sys.stdin)
    command = (event.get("tool_input") or {}).get("command", "")
    if not command:
        return 0
    cwd = Path(event.get("cwd") or ".")
    for segment in _split_segments(command):
        words = _command_words(segment)
        if len(words) >= 3 and words[0] == "gh" and words[1] == "pr" and words[2] in ("create", "edit"):
            rc = _check_pr_segment(words[2], words[3:], cwd)
            if rc != 0:
                return rc
    return 0


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


def block_stack(reason):
    print(f"PR base blocked by ship-pr: {reason}", file=sys.stderr)
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
