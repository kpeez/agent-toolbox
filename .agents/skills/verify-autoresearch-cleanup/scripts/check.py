#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Crash the real autoresearch cleanup CLI at every crash point and check each rule.

A first run of ``cleanup.py --apply --acknowledge-stopped-run`` lists the crash
points: each filesystem change that the process makes, as the audit hook in
``crash_hook/`` sees it. For each crash point and for SIGKILL and SIGINT, a new
run is stopped just before that change, the rules are checked, and the same
command runs again.

Exit 0 when every rule holds and each mutant breaks the rule it targets; 1
otherwise. ``--no-mutants`` skips the mutants.
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
REPO = SKILL.parent.parent.parent
CLEANUP = (
    REPO / "plugins" / "lab" / "skills" / "autoresearch" / "scripts" / "cleanup.py"
)
HOOK = SKILL / "scripts" / "crash_hook"
RUN = "2026-08-22"
ARCHIVE = f"{RUN}_archive.tar.zst"
STAGING, RECOVERY = f".{RUN}.cleanup-staging", f".{RUN}.cleanup-original"
LIGHTWEIGHT = {ARCHIVE, "EXPERIMENT_SUMMARY.md", "autoresearch-run.png"}
RULES = ("OriginalRecoverable", "RerunSafe", "InterruptNamesRecovery")
FILES = {
    "program.md": b"# original program\n",
    "EXPERIMENT_SUMMARY.md": b"# verified summary\n",
    "autoresearch-run.png": b"PNG fixture bytes\n",
    "results.jsonl": b'{"id": 0}\n',
    ".hidden": b"hidden provenance\n",
    "logs/exp000.log": b"baseline\n",
}

MUTANTS = {
    "trash-before-install": (
        "OriginalRecoverable",
        [
            (
                '            fail("run path reappeared; refusing to replace it")\n',
                (
                    '            fail("run path reappeared; refusing to replace it")\n'
                    "        subprocess.run([trash_command, str(recovery)], capture_output=True, text=True)\n"
                ),
            ),
            (
                (
                    "        if not snapshot_equal(source, snapshot(recovery)):\n"
                    '            fail("original changed after replacement; stopped-run precondition was violated")\n'
                    "        result = subprocess.run([trash_command, str(recovery)], capture_output=True, text=True)\n"
                    "        if result.returncode or os.path.lexists(recovery):\n"
                ),
                "        if False:\n",
            ),
        ],
    ),
    "ignore-unfinished-cleanup": (
        "RerunSafe",
        [
            ("        if os.path.lexists(interrupted):\n", "        if False:\n"),
        ],
    ),
    "silent-interrupt": (
        "InterruptNamesRecovery",
        [
            (
                '        print(f"cleanup interrupted; inspect original recovery {recovery}, "\n',
                '        print(f"cleanup interrupted; inspect "\n',
            ),
        ],
    ),
}


def make_case(root):
    run = root / "work" / RUN
    (run / "logs").mkdir(parents=True)
    for rel, data in FILES.items():
        (run / rel).write_bytes(data)
    (run / "train.sh").write_bytes(b"#!/bin/sh\n")
    (run / "train.sh").chmod(0o755)
    (root / "outside.txt").write_bytes(b"outside the run\n")
    (run / "external-link").symlink_to(root / "outside.txt")
    (root / "bin").mkdir()
    trash = root / "bin" / "trash"
    trash.write_text('#!/bin/sh\nmkdir -p "$FAKE_TRASH" && mv "$1" "$FAKE_TRASH/"\n')
    trash.chmod(0o755)


def tree(top):
    """Every entry under ``top`` without following links: kind, mode, and bytes or link target."""
    out = {}
    for path in sorted(top.rglob("*")):
        info = path.lstat()
        mode = info.st_mode & 0o7777
        if path.is_symlink():
            out[path.relative_to(top).as_posix()] = ("symlink", mode, os.readlink(path))
        elif path.is_dir():
            out[path.relative_to(top).as_posix()] = ("dir", mode, None)
        else:
            out[path.relative_to(top).as_posix()] = (
                "file",
                mode,
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
    return out


def archive_tree(archive):
    """The run as an independent zstd and tarfile read of ``archive`` sees it; None when unreadable."""
    data = subprocess.run(
        ["zstd", "-q", "-d", "-c", str(archive)], capture_output=True, check=False
    )
    if data.returncode:
        return None
    out = {}
    try:
        with tarfile.open(fileobj=io.BytesIO(data.stdout), mode="r:") as stream:
            for member in stream:
                if member.name == RUN:
                    continue
                rel = member.name.removeprefix(RUN + "/")
                if member.issym():
                    out[rel] = ("symlink", member.mode, member.linkname)
                elif member.isdir():
                    out[rel] = ("dir", member.mode, None)
                elif member.isfile():
                    out[rel] = (
                        "file",
                        member.mode,
                        hashlib.sha256(stream.extractfile(member).read()).hexdigest(),
                    )
                else:
                    return None
    except tarfile.TarError:
        return None
    return out


def cleanup(script, root, extra):
    env = {
        **os.environ,
        "PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "FAKE_TRASH": str(root / "Trash"),
        "PYTHONDONTWRITEBYTECODE": "1",
        **extra,
    }
    argv = [
        "uv",
        "run",
        "--script",
        str(script),
        str(root / "work" / RUN),
        "--apply",
        "--acknowledge-stopped-run",
    ]
    process = subprocess.Popen(
        argv,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        out, err = process.communicate(timeout=120)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return process.returncode, out, err


def crash_points(script):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        make_case(root)
        code, _, err = cleanup(script, root, {"PYTHONPATH": str(HOOK)})
        if code:
            sys.exit(f"a full cleanup run failed (exit {code}):\n{err}")
        return [
            line.split(": ", 1)[1]
            for line in err.splitlines()
            if line.startswith("crash-point ")
        ]


def crash(script, index, how, points):
    """Stop a new run before crash point ``index`` (no stop when it is past the last) and check each rule."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        make_case(root)
        work, run = root / "work", root / "work" / RUN
        original = tree(run)
        code, _, err = cleanup(
            script,
            root,
            {
                "PYTHONPATH": str(HOOK),
                "CLEANUP_CRASH_AT": str(index),
                "CLEANUP_CRASH_SIGNAL": how,
            },
        )
        if index < len(points) and f"crash-point {index}: " not in err:
            sys.exit(
                f"crash point {index} ({points[index]}) was not reached; the run is not deterministic:\n{err}"
            )
        broken = {}
        places = [run, work / RECOVERY]
        if not any(
            place.is_dir() and tree(place) == original for place in places
        ) and not (run.is_dir() and archive_tree(run / ARCHIVE) == original):
            broken["OriginalRecoverable"] = (
                "no complete copy in the run folder, the recovery folder, or the installed archive"
            )
        if (
            how == "INT"
            and (work / RECOVERY).exists()
            and f"cleanup interrupted; inspect original recovery {work / RECOVERY}"
            not in err
        ):
            broken["InterruptNamesRecovery"] = (
                "the interrupted run does not name the recovery folder"
            )
        before = tree(root)
        code, out, err = cleanup(script, root, {})
        leftovers = [
            work / name for name in (STAGING, RECOVERY) if os.path.lexists(work / name)
        ]
        if code == 0:
            if (
                leftovers
                or not run.is_dir()
                or set(os.listdir(run)) != LIGHTWEIGHT
                or archive_tree(run / ARCHIVE) != original
                or json.loads(out)["status"] not in ("archived", "already-clean")
            ):
                broken["RerunSafe"] = (
                    f"the rerun exited 0 but did not finish cleanly; left {[p.name for p in leftovers]}"
                )
        elif not any(str(path) in err for path in leftovers) or tree(root) != before:
            broken["RerunSafe"] = (
                f"the rerun refused without naming a leftover folder, or changed files: {err.strip()}"
            )
        return broken


def explore(script):
    points = crash_points(script)
    cases = [
        (how, index) for how in ("KILL", "INT") for index in range(len(points) + 1)
    ]
    with ThreadPoolExecutor(max_workers=os.cpu_count()) as pool:
        results = list(
            pool.map(lambda case: crash(script, case[1], case[0], points), cases)
        )
    broken = {}
    for (how, index), result in zip(cases, results):
        for rule, why in result.items():
            broken.setdefault(rule, (how, index, why))
    return points, broken


def describe(points, how, index, why):
    where = (
        f"before crash point {index} ({points[index]})"
        if index < len(points)
        else "after the full run"
    )
    return f"SIG{how} {where}: {why}"


def mutate(tmp, name):
    text = CLEANUP.read_text()
    for old, new in MUTANTS[name][1]:
        if text.count(old) != 1:
            sys.exit(
                f"mutant {name} no longer applies to cleanup.py; update it in scripts/check.py"
            )
        text = text.replace(old, new)
    script = Path(tmp) / name / "cleanup.py"
    script.parent.mkdir()
    script.write_text(text)
    return script


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--no-mutants", action="store_true")
    args = ap.parse_args()
    if not shutil.which("zstd"):
        sys.exit("zstd is required")

    points, broken = explore(CLEANUP)
    print(
        f"{len(points)} crash points in cleanup.py --apply; each one under SIGKILL and SIGINT, then a rerun:"
    )
    for index, point in enumerate(points):
        print(f"  {index}. {point}")
    ok = not broken
    for rule in RULES:
        print(
            f"{rule}: "
            + (
                f"breaks, {describe(points, *broken[rule])}"
                if rule in broken
                else "holds"
            )
        )
    if not args.no_mutants:
        with tempfile.TemporaryDirectory() as tmp:
            for name, (rule, _) in MUTANTS.items():
                mutant_points, mutant_broken = explore(mutate(tmp, name))
                caught = rule in mutant_broken
                ok &= caught
                print(
                    f"mutant {name}: "
                    + (
                        f"caught by {rule}, {describe(mutant_points, *mutant_broken[rule])}"
                        if caught
                        else f"NOT CAUGHT by {rule} (the check cannot fail)"
                    )
                )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
