"""Git facts capture for taskstate. Stdlib only."""
from __future__ import annotations

import hashlib
import os
import subprocess
import time

EMPTY_HASH = hashlib.sha256(b"").hexdigest()


def _remaining(deadline):
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("facts deadline exceeded")
    return remaining


def _git(args, cwd=None, timeout=10):
    try:
        out = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return None
    if out.returncode != 0:
        return None
    return out.stdout


def _git_text(args, cwd=None, timeout=10):
    out = _git(args, cwd=cwd, timeout=timeout)
    if out is None:
        return None
    try:
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return None


def git_dir(cwd=None, timeout=10):
    """Absolute git dir path, or None if not in a repo."""
    raw = _git_text(["rev-parse", "--git-dir"], cwd=cwd, timeout=timeout)
    if not raw:
        return None
    if not os.path.isabs(raw):
        top = _git_text(["rev-parse", "--show-toplevel"], cwd=cwd,
                        timeout=timeout)
        # For bare-ish layouts fall back to cwd-relative resolution.
        base = top or (cwd or os.getcwd())
        raw = os.path.join(base, raw)
    return os.path.abspath(raw)


def collect(cwd=None, timeout=10, deadline=None):
    """Return dict(head, branch, worktree, diff_hash, git_dir). Nulls outside git."""
    cwd = cwd or os.getcwd()
    budget = _remaining(deadline)
    gd = git_dir(cwd=cwd, timeout=min(timeout, budget) if budget is not None else timeout)
    if gd is None:
        return {"head": None, "branch": None, "worktree": None,
                "diff_hash": None, "git_dir": None}
    budget = _remaining(deadline)
    top = _git_text(["rev-parse", "--show-toplevel"], cwd=cwd,
                    timeout=min(timeout, budget) if budget is not None else timeout) or cwd
    budget = _remaining(deadline)
    head = _git_text(["rev-parse", "HEAD"], cwd=top,
                     timeout=min(timeout, budget) if budget is not None else timeout)
    budget = _remaining(deadline)
    branch = _git_text(["rev-parse", "--abbrev-ref", "HEAD"], cwd=top,
                       timeout=min(timeout, budget) if budget is not None else timeout)
    budget = _remaining(deadline)
    worktree = _git_text(["rev-parse", "--show-toplevel"], cwd=top,
                         timeout=min(timeout, budget) if budget is not None else timeout)
    if branch == "":
        branch = None
    budget = _remaining(deadline)
    diff_hash = _diff_hash(top, timeout=min(timeout, budget) if budget is not None else timeout,
                           deadline=deadline, head_known=head is not None)
    return {"head": head, "branch": branch, "worktree": worktree,
            "diff_hash": diff_hash, "git_dir": gd}


def _diff_hash(cwd, timeout=10, deadline=None, head_known=True):
    budget = _remaining(deadline)
    h = hashlib.sha256()
    diff = _git(["diff", "HEAD", "--binary", "--no-color", "--no-ext-diff",
                 "--no-textconv"], cwd=cwd,
                timeout=min(timeout, budget) if budget is not None else timeout)
    if diff is None:
        return EMPTY_HASH if not head_known else None
    h.update(diff if isinstance(diff, bytes) else bytes(diff))
    budget = _remaining(deadline)
    raw = _git(["ls-files", "--others", "--exclude-standard", "-z"], cwd=cwd,
               timeout=min(timeout, budget) if budget is not None else timeout)
    if raw is None:
        return None
    for name in sorted(raw.split(b"\x00")):
        _remaining(deadline)
        if not name:
            continue
        try:
            rel = name.decode("utf-8", errors="replace")
        except Exception:
            return None
        full = os.path.join(cwd, rel)
        h.update(b"\x00" + name + b"\x00")
        try:
            with open(full, "rb") as fh:
                while True:
                    _remaining(deadline)
                    chunk = fh.read(65536)
                    if not chunk:
                        break
                    h.update(chunk)
        except OSError:
            return None
    return h.hexdigest()
