#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Oracle for the shlex parity test: the original Python command splitter.

Reads a JSON list of command strings on stdin. Writes a JSON list with one
entry per command: {"error": bool, "segments": [[token, ...], ...]}. "error"
is true when shlex raised ValueError, so the segments came from the
whitespace-split fallback. The body of `split_segments` is the code that
pr_body.py ran before the TypeScript port (commit bed647d^).
"""

import json
import shlex
import sys

SEGMENT_SEPARATORS = {";", "&&", "||", "|", "&", "\n", "(", ")", "`"}


def split_segments(command):
    command = command.replace("\\\n", " ")
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace = " \t\r"
    lex.whitespace_split = False
    lex.commenters = ""
    lex.wordchars += "!#$%+,:@[]^{}"
    error = False
    try:
        tokens = list(lex)
    except ValueError:
        error = True
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
    return error, segments


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    commands = json.load(sys.stdin)
    out = [dict(zip(("error", "segments"), split_segments(c))) for c in commands]
    json.dump(out, sys.stdout)
