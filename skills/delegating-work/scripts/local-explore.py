#!/usr/bin/env python3
"""Local codebase explorer: gather files, ask a local ollama model, print a summary.

The point is token savings: file contents and the generation never enter the
parent (Opus) context. Only the returned summary does. Call it directly via Bash:

    local-explore "How does auth work?" src/ lib/auth.py
    local-explore --dry-run "..." src/        # show what would be sent, no model call

It is read-only and only talks to localhost, so it is safe to auto-approve.
"""

import argparse
import glob
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
    ".agent",
    ".next",
    "target",
    ".idea",
    ".vscode",
    "specs",
}
SKIP_EXT = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".lock",
    ".bin",
    ".so",
    ".dylib",
    ".o",
    ".a",
    ".woff",
    ".woff2",
    ".ttf",
    ".ico",
    ".svg",
    ".mp4",
    ".mp3",
    ".webp",
    ".pyc",
    ".wasm",
}
MAX_FILE_BYTES = 1_000_000  # skip files larger than this (likely generated)

SYSTEM = (
    "You are a code exploration assistant. A more capable parent agent will act on "
    "your answer, so be faithful and precise. Answer ONLY from the provided file "
    "contents. Cite file paths for claims. If the answer is not in the files, say so "
    "plainly. Be concise — the parent wants a tight summary, not a retelling."
)


def iter_files(targets):
    seen = set()
    for target in targets:
        p = Path(target)
        if p.is_dir():
            paths = (Path(r) / f for r, _, fs in os.walk(p) for f in fs)
        elif p.is_file():
            paths = [p]
        else:
            paths = (Path(m) for m in glob.glob(target, recursive=True))
        for path in paths:
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in SKIP_EXT or path in seen:
                continue
            seen.add(path)
            yield path


def read_text(path):
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data[:8192]:  # binary
        return None
    return data.decode("utf-8", errors="replace")


def gather(targets, char_budget):
    parts, used, included, truncated = [], 0, [], []
    for path in sorted(iter_files(targets)):
        text = read_text(path)
        if text is None:
            continue
        header = f"\n### {path}\n"
        remaining = char_budget - used - len(header)
        if remaining <= 0:
            break
        if len(text) > remaining:
            text = text[:remaining] + "\n... [truncated]\n"
            truncated.append(str(path))
        parts.append(header + text)
        used += len(header) + len(text)
        included.append(str(path))
    return "".join(parts), included, truncated


def auto_ctx(question, content, predict):
    """Smallest power-of-two window (4K..32K) that holds prompt + output.

    num_ctx sizes the KV cache, so matching it to the input keeps the memory
    footprint down — which is what lets you run more explorers concurrently.
    """
    need = (len(SYSTEM) + len(question) + len(content)) // 4 + predict + 512
    n = 4096
    while n < need and n < 32768:
        n *= 2
    return min(n, 32768)


def ask(host, model, num_ctx, num_predict, question, content):
    payload = {
        "model": model,
        "stream": False,
        "options": {"num_ctx": num_ctx, "num_predict": num_predict},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Question: {question}\n\nFiles:\n{content}"},
        ],
    }
    req = urllib.request.Request(
        f"{host}/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["message"]["content"]


def main():
    ap = argparse.ArgumentParser(
        description="Explore a codebase with a local ollama model."
    )
    ap.add_argument("question", help="what to find out")
    ap.add_argument("paths", nargs="+", help="files, dirs, or globs to read")
    ap.add_argument(
        "--model", default="gpt-oss:20b"
    )  # MoE: ~2x faster + better than qwen3.5:9b for this
    ap.add_argument(
        "--max-tokens", type=int, default=24000, help="input budget (~chars/4)"
    )
    ap.add_argument(
        "--ctx", type=int, default=0, help="ollama num_ctx (0 = auto-size to input)"
    )
    ap.add_argument("--predict", type=int, default=1024, help="max output tokens")
    ap.add_argument(
        "--host", default=os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print gathered files + size, no model call",
    )
    args = ap.parse_args()

    content, included, truncated = gather(args.paths, args.max_tokens * 4)
    if not included:
        sys.exit("local-explore: no readable files matched the given paths")

    num_ctx = args.ctx or auto_ctx(args.question, content, args.predict)

    if args.dry_run:
        print(
            f"{len(included)} files, ~{len(content) // 4} tokens "
            f"({len(content)} chars), num_ctx={num_ctx}, {len(truncated)} truncated",
            file=sys.stderr,
        )
        print("\n".join(included))
        return

    try:
        print(ask(args.host, args.model, num_ctx, args.predict, args.question, content))
    except urllib.error.URLError as e:
        sys.exit(
            f"local-explore: cannot reach ollama at {args.host} ({e}). Is `ollama serve` running?"
        )
    if truncated:
        print(f"\n[note] truncated: {', '.join(truncated)}", file=sys.stderr)


if __name__ == "__main__":
    main()
