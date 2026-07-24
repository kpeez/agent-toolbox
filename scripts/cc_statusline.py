#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime

R = "\033[0m"


def ansi(*codes):
    return "\033[" + ";".join(str(c) for c in codes) + "m"


home = os.environ.get("HOME", "")
data = json.load(sys.stdin)

# Path
cwd = data["workspace"]["current_dir"]
path_disp = ("~" + cwd[len(home) :]) if home and cwd.startswith(home) else cwd
path_label = f"{ansi('01', 34)}{path_disp}{R}"


# Git branch — read HEAD directly to avoid subprocess overhead
def git_branch(path):
    while path != os.path.dirname(path):
        head = os.path.join(path, ".git", "HEAD")
        if os.path.exists(head):
            line = open(head).read().strip()
            return (
                line.removeprefix("ref: refs/heads/") if line.startswith("ref:") else ""
            )
        path = os.path.dirname(path)
    return ""


branch = git_branch(cwd)

# Model name — strip "Claude " prefix, color by family
# Muted earth/jewel tones so the model name stays distinct from the neon effort colors below
model_colors = {
    "Opus": ansi("38;2;95;179;161"),  # verdigris
    "Sonnet": ansi("38;2;139;123;216"),  # iris
    "Haiku": ansi("38;2;217;164;65"),  # amber
    "Fable": ansi("38;2;162;91;140"),  # mulberry
}
model = (
    data["model"]["display_name"].replace(" (default)", "").replace(" (1M context)", "")
)
model_color = next((c for k, c in model_colors.items() if k in model), ansi(97))
model_label = f"{model_color}[{model}]{R}"
# Thinking effort — absent when model doesn't support it
effort = (data.get("effort") or {}).get("level", "")
effort_colors = {
    "low": ansi("38;2;255;200;0"),  # yellow
    "medium": ansi("38;2;80;200;80"),  # green
    "high": ansi("38;2;80;140;255"),  # blue
    "xhigh": ansi("38;2;160;80;255"),  # purple
    "max": ansi("38;2;255;100;180"),  # pink
}
effort_label = f"{effort_colors.get(effort, ansi(97))} {effort}{R}" if effort else ""

full_model_label = f"{model_label}{effort_label}"

# Context bar (12 chars) + token count — current_usage is null before first API call
BAR_WIDTH = 12
ctx = data["context_window"]
usage = ctx["current_usage"] or {}
ctx_used = (
    (usage.get("input_tokens") or 0)
    + (usage.get("cache_creation_input_tokens") or 0)
    + (usage.get("cache_read_input_tokens") or 0)
)
ctx_size = ctx["context_window_size"]
ctx_size_fmt = (
    f"{ctx_size / 1_000_000:.1f}M" if ctx_size >= 1_000_000 else f"{ctx_size // 1000}k"
)
pct = min(int(ctx["used_percentage"] or 0), 100)
filled = pct * BAR_WIDTH // 100
# Muted cyan — sits midway between the Opus teal and the high-effort blue, so it reads as
# its own color without competing; track stays above 3:1 on a dark background to remain visible
BAR_FILLED = ansi("38;2;169;200;209")
BAR_EMPTY = ansi("38;2;75;125;139")
BAR_TEXT = ansi("38;2;133;172;183")
bar = f"{BAR_FILLED}{'█' * filled}{R}{BAR_EMPTY}{'░' * (BAR_WIDTH - filled)}{R}"
pct_label = f"{BAR_TEXT}{pct}%{R}"
tok_label = f"{BAR_TEXT}({ctx_used / 1000:.1f}k/{ctx_size_fmt}){R}"

# Rate limits — absent for non-Pro/Max or before first API response; field is resets_at not reset_at
rl = data.get("rate_limits") or {}
fh = rl.get("five_hour") or {}


def fmt_reset(epoch):
    secs = max(0, int(epoch - datetime.now().timestamp()))
    h, m = divmod(secs // 60, 60)
    return f"{h}h {m}m left"


fh_label = (
    f"{ansi(33)}5h: {int(fh['used_percentage'])}% ({fmt_reset(fh['resets_at'])}){R}"
    if fh
    else ""
)

print(f"""\
{full_model_label} 📁 {path_label}{f" | 🌿 {branch}" if branch else ""}
{bar} {pct_label} {tok_label} | {fh_label}
{ansi(2, 37)}{data.get("transcript_path", "")}{R}""")
