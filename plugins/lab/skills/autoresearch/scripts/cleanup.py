#!/usr/bin/env python3
"""Safely archive a completed autoresearch run.

The command is conservative by default and only reports whether a run is
ready.  ``--apply --acknowledge-stopped-run`` creates
``RUN_NAME_archive.tar.zst`` and moves the verified original directory to a
system trash command, retaining only the archive, summary, and plot.

    cleanup.py RUN_DIR
    cleanup.py RUN_DIR --apply --acknowledge-stopped-run

The archive is staged outside the run directory.  The source is snapshotted
before and after staging, and the compressed tar is checked for integrity,
membership, and regular-file hashes before any retirement is attempted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import tarfile
from typing import BinaryIO, Iterable


REQUIRED_FILES = ("program.md", "EXPERIMENT_SUMMARY.md", "autoresearch-run.png")
RETAINED_FILES = frozenset(("EXPERIMENT_SUMMARY.md", "autoresearch-run.png"))
DEFAULT_ACTIVE_MARKERS = frozenset((".autoresearch-active", ".autoresearch-running", "RUNNING"))
CHUNK_SIZE = 1024 * 1024
SPACE_MARGIN = 10 * 1024 * 1024


class CleanupError(RuntimeError):
    """A non-destructive cleanup failure."""


@dataclass(frozen=True)
class Entry:
    """A no-follow snapshot entry relative to the run root."""

    rel: str
    kind: str
    size: int
    mode: int
    mtime_ns: int
    digest: str | None = None
    target: str | None = None


@dataclass(frozen=True)
class Snapshot:
    entries: dict[str, Entry]

    @property
    def regular_bytes(self) -> int:
        return sum(entry.size for entry in self.entries.values() if entry.kind == "file")


def fail(message: str) -> None:
    raise CleanupError(message)


def archive_name(run_dir: Path) -> str:
    if not run_dir.name or run_dir.name in {".", ".."}:
        fail(f"run directory has no usable name: {run_dir}")
    return f"{run_dir.name}_archive.tar.zst"


def _digest_regular(path: Path, expected: os.stat_result) -> tuple[str, int]:
    """Hash and verify a file using descriptors that are closed on every path."""

    flags = os.O_RDONLY | (os.O_NOFOLLOW if hasattr(os, "O_NOFOLLOW") else 0)
    try:
        fd = os.open(path, flags)
    except OSError as error:
        fail(f"cannot read regular file {path}: {error}")
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
            fail(f"file changed while opening {path}")
        digest = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            size += len(chunk)
        finished = os.fstat(fd)
        if (finished.st_size, finished.st_mtime_ns) != (expected.st_size, expected.st_mtime_ns) or size != expected.st_size:
            fail(f"file changed while hashing {path}")
        return digest.hexdigest(), size
    finally:
        os.close(fd)


def _relative_name(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        fail(f"path escaped run directory: {path}")
    return PurePosixPath(relative.as_posix()).as_posix()


def snapshot(run_dir: Path, excluded_root_names: Iterable[str] = ()) -> Snapshot:
    """Collect a stable, no-follow snapshot of supported filesystem entries."""

    entries: dict[str, Entry] = {}
    excluded = set(excluded_root_names)
    pending = [run_dir]
    while pending:
        directory = pending.pop()
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as error:
            fail(f"cannot inspect {directory}: {error}")
        for child in children:
            path = Path(child.path)
            rel = _relative_name(path, run_dir)
            if "/" not in rel and rel in excluded:
                continue
            try:
                info = os.lstat(path)
            except OSError as error:
                fail(f"cannot inspect {path}: {error}")
            mode = info.st_mode
            if stat.S_ISDIR(mode):
                entries[rel] = Entry(rel, "dir", 0, stat.S_IMODE(mode), info.st_mtime_ns)
                pending.append(path)
            elif stat.S_ISREG(mode):
                digest, size = _digest_regular(path, info)
                entries[rel] = Entry(rel, "file", size, stat.S_IMODE(mode), info.st_mtime_ns, digest=digest)
            elif stat.S_ISLNK(mode):
                try:
                    target = os.readlink(path)
                except OSError as error:
                    fail(f"cannot read symlink {path}: {error}")
                entries[rel] = Entry(rel, "symlink", 0, stat.S_IMODE(mode), info.st_mtime_ns, target=target)
            else:
                fail(f"unsupported special file in run: {path}")
    return Snapshot(entries)


def snapshot_equal(first: Snapshot, second: Snapshot) -> bool:
    return first.entries == second.entries


def validate_run_dir(run_dir: Path, archive: Path) -> None:
    if not run_dir.exists() or not run_dir.is_dir() or run_dir.is_symlink():
        fail(f"run directory must be a real directory: {run_dir}")
    for name in REQUIRED_FILES:
        path = run_dir / name
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            fail(f"required file is missing: {path}")
        except OSError as error:
            fail(f"cannot inspect required file {path}: {error}")
        if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
            fail(f"required file must be a nonempty regular file: {path}")
    if os.path.lexists(archive):
        try:
            info = os.lstat(archive)
        except OSError as error:
            fail(f"cannot inspect existing archive {archive}: {error}")
        if not stat.S_ISREG(info.st_mode):
            fail(f"archive destination exists and is not a regular file: {archive}")


def validate_retained_layout(run_dir: Path, archive: Path) -> Snapshot:
    """Validate the only resumable state: a completed lightweight run."""

    if not run_dir.exists() or not run_dir.is_dir() or run_dir.is_symlink():
        fail(f"run directory must be a real directory: {run_dir}")
    try:
        info = os.lstat(archive)
    except OSError as error:
        fail(f"cannot inspect existing archive {archive}: {error}")
    if not stat.S_ISREG(info.st_mode) or info.st_size == 0:
        fail(f"existing archive must be a nonempty regular file: {archive}")
    retained = snapshot(run_dir, excluded_root_names=(archive.name,))
    if set(retained.entries) != set(RETAINED_FILES):
        fail("an existing archive is only resumable when the run is already lightweight")
    for name in RETAINED_FILES:
        entry = retained.entries[name]
        if entry.kind != "file" or entry.size == 0:
            fail(f"retained file must be a nonempty regular file: {run_dir / name}")
    return retained


def active_markers(snap: Snapshot, markers: Iterable[str]) -> list[str]:
    return sorted(name for name in markers if name in snap.entries)


def _safe_member_name(name: str) -> str:
    normalized = name.rstrip("/")
    if not normalized or normalized.startswith("/"):
        fail(f"archive contains unsafe member name: {name!r}")
    parts = PurePosixPath(normalized).parts
    if any(part in {"", ".", ".."} for part in parts):
        fail(f"archive contains unsafe member name: {name!r}")
    return PurePosixPath(*parts).as_posix()


def _member_kind(member: tarfile.TarInfo) -> str:
    if member.isdir():
        return "dir"
    if member.isfile():
        return "file"
    if member.issym():
        return "symlink"
    if member.islnk():
        return "hardlink"
    fail(f"archive contains unsupported member type: {member.name!r}")


def _hash_member(fileobj: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = fileobj.read(CHUNK_SIZE)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def _archive_members(archive: Path) -> dict[str, tuple[str, str | None, int, str | None, int]]:
    """Read all members and content hashes from a zstd-compressed tar."""

    zstd = shutil.which("zstd")
    if not zstd:
        fail("zstd executable is required")
    integrity = subprocess.run([zstd, "-q", "-t", str(archive)], capture_output=True, text=True)
    if integrity.returncode:
        detail = integrity.stderr.strip() or "unknown zstd error"
        fail(f"compressed archive failed integrity check: {detail}")
    with subprocess.Popen([zstd, "-q", "-d", "-c", str(archive)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
        assert process.stdout is not None
        members: dict[str, tuple[str, str | None, int, str | None, int]] = {}
        try:
            with tarfile.open(fileobj=process.stdout, mode="r|*") as stream:
                for member in stream:
                    name = _safe_member_name(member.name)
                    if name in members:
                        fail(f"archive contains duplicate member: {name}")
                    kind = _member_kind(member)
                    digest = None
                    size = 0
                    target = member.linkname if kind in {"symlink", "hardlink"} else None
                    if kind == "file":
                        fileobj = stream.extractfile(member)
                        if fileobj is None:
                            fail(f"archive member has no readable content: {name}")
                        digest, size = _hash_member(fileobj)
                    members[name] = (kind, target, size, digest, stat.S_IMODE(member.mode))
        except (tarfile.TarError, OSError) as error:
            process.stdout.close()
            process.wait()
            fail(f"archive tar stream could not be read: {error}")
        except BaseException:
            process.stdout.close()
            process.wait()
            raise
        else:
            process.stdout.close()
        stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
        returncode = process.wait()
        if returncode:
            fail(f"zstd decompression failed: {stderr.strip() or returncode}")
    return members


def _resolve_hardlink(name: str, target: str, root_name: str) -> str:
    target_name = _safe_member_name(target)
    if target_name == root_name or target_name.startswith(root_name + "/"):
        return target_name
    return f"{root_name}/{target_name}"


def verify_archive(archive: Path, run_dir: Path, source: Snapshot | None, exact: bool) -> dict[str, tuple[str, str | None, int, str | None, int]]:
    members = _archive_members(archive)
    root_name = run_dir.name
    root = members.get(root_name)
    if root is None or root[0] != "dir":
        fail(f"archive is missing its run-directory root: {root_name}")
    if source is not None:
        expected: dict[str, Entry] = {root_name: Entry(root_name, "dir", 0, stat.S_IMODE(run_dir.stat().st_mode), 0)}
        expected.update({f"{root_name}/{rel}": entry for rel, entry in source.entries.items()})
        if exact and set(members) != set(expected):
            missing = sorted(set(expected) - set(members))
            extra = sorted(set(members) - set(expected))
            fail(f"archive membership differs from source (missing={missing[:3]!r}, extra={extra[:3]!r})")
        for name, entry in expected.items():
            member = members.get(name)
            if member is None:
                fail(f"archive is missing source entry: {name}")
            kind, target, size, digest, mode = member
            if entry.kind == "file":
                if kind == "hardlink":
                    link_name = _resolve_hardlink(name, target or "", root_name)
                    link_member = members.get(link_name)
                    if link_member is None or link_member[0] != "file":
                        fail(f"archive hardlink target is invalid: {name}")
                    digest, size = link_member[3], link_member[2]
                if kind != "file" and kind != "hardlink":
                    fail(f"archive type differs for {name}: expected file, got {kind}")
                if size != entry.size or digest != entry.digest or mode != entry.mode:
                    fail(f"archive content differs for {name}")
            elif entry.kind == "symlink":
                if kind != "symlink" or target != entry.target or mode != entry.mode:
                    fail(f"archive symlink differs for {name}")
            elif kind != entry.kind or mode != entry.mode:
                fail(f"archive type differs for {name}: expected {entry.kind}, got {kind}")
    if any(name != root_name and not name.startswith(root_name + "/") for name in members):
        fail("archive contains entries outside its run directory")
    required_members = {f"{root_name}/{name}" for name in REQUIRED_FILES}
    missing_required = sorted(required_members - set(members))
    if missing_required:
        fail(f"archive is missing required source members: {missing_required!r}")
    for name in required_members:
        member = members[name]
        if member[0] == "hardlink":
            member = members.get(_resolve_hardlink(name, member[1] or "", root_name), ("missing", None, 0, None, 0))
        if member[0] != "file" or member[2] == 0:
            fail(f"required archive member is not a nonempty regular file: {name}")
    return members


def write_archive(run_dir: Path, archive: Path, source: Snapshot) -> Path:
    zstd = shutil.which("zstd")
    if not zstd:
        fail("zstd executable is required")
    check_space(run_dir, source)
    with subprocess.Popen([zstd, "-q", "-T0", "-o", str(archive), "-"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as process:
        assert process.stdin is not None
        try:
            with tarfile.open(fileobj=process.stdin, mode="w|", format=tarfile.PAX_FORMAT, dereference=False) as stream:
                stream.add(run_dir, arcname=run_dir.name, recursive=False)
                for rel in sorted(source.entries, key=lambda name: (name.count("/"), name)):
                    stream.add(run_dir / Path(rel), arcname=f"{run_dir.name}/{rel}", recursive=False)
        except BaseException:
            process.stdin.close()
            process.kill()
            process.wait()
            raise
        finally:
            if not process.stdin.closed:
                process.stdin.close()
        stderr = process.stderr.read().decode(errors="replace") if process.stderr else ""
        if process.wait():
            fail(f"zstd could not create archive: {stderr.strip() or 'unknown error'}")
    verify_archive(archive, run_dir, source, exact=True)
    return archive


def check_space(run_dir: Path, source: Snapshot) -> None:
    needed = (2 * source.regular_bytes + 4096 * len(source.entries) + SPACE_MARGIN)
    free = shutil.disk_usage(run_dir.parent).free
    if free < needed:
        fail(f"insufficient free space beside run ({free} bytes free, {needed} required)")


def find_trash() -> str:
    for command in ("trash", "trash-put"):
        found = shutil.which(command)
        if found:
            return found
    fail("a recoverable trash command (trash or trash-put) is required for --apply")


def stage_lightweight(run_dir: Path, archive: Path, source: Snapshot) -> Path:
    """Create the final three-entry directory beside the original run."""

    staging = run_dir.parent / f".{run_dir.name}.cleanup-staging"
    staging.mkdir(mode=0o700)
    print(f"cleanup staging: {staging}", file=sys.stderr, flush=True)
    staged_archive = staging / archive.name
    write_archive(run_dir, staged_archive, source)
    for name in RETAINED_FILES:
        source_path = run_dir / name
        destination = staging / name
        shutil.copyfile(source_path, destination, follow_symlinks=False)
        shutil.copystat(source_path, destination, follow_symlinks=False)
        expected = source.entries[name]
        info = os.lstat(destination)
        digest, size = _digest_regular(destination, info)
        if digest != expected.digest or size != expected.size or stat.S_IMODE(info.st_mode) != expected.mode:
            fail(f"staged retained file differs from source: {name}")
    if set(os.listdir(staging)) != {archive.name, *RETAINED_FILES}:
        fail(f"staging directory has unexpected contents: {staging}")
    staging.chmod(stat.S_IMODE(run_dir.stat().st_mode))
    return staging


def publish_lightweight(run_dir: Path, staging: Path, source: Snapshot, trash_command: str) -> None:
    """Keep the original whole through verification and replacement installation."""

    recovery = run_dir.parent / f".{run_dir.name}.cleanup-original"
    if os.path.lexists(recovery):
        fail(f"recovery path already exists: {recovery}")
    if not snapshot_equal(source, snapshot(run_dir)):
        fail(f"run changed before retirement; originals and staging retained: {staging}")
    print(f"cleanup original recovery: {recovery}", file=sys.stderr, flush=True)
    # Staging's exclusive mkdir serializes cooperating cleanup invocations.
    # The caller must stop all writers; renaming cannot freeze open descriptors.
    os.rename(run_dir, recovery)
    try:
        if not snapshot_equal(source, snapshot(recovery)):
            fail("original changed during rename")
        if os.path.lexists(run_dir):
            fail("run path reappeared; refusing to replace it")
        os.rename(staging, run_dir)
        archive = run_dir / archive_name(run_dir)
        retained = validate_retained_layout(run_dir, archive)
        verify_archive(archive, run_dir, source, exact=True)
        for name in RETAINED_FILES:
            if retained.entries[name] != source.entries[name]:
                fail(f"retained file changed: {name}")
        if not snapshot_equal(source, snapshot(recovery)):
            fail("original changed after replacement; stopped-run precondition was violated")
        result = subprocess.run([trash_command, str(recovery)], capture_output=True, text=True)
        if result.returncode or os.path.lexists(recovery):
            fail(f"trash did not complete: {result.stderr.strip() or result.stdout.strip()}")
    except BaseException:
        print(f"cleanup interrupted; inspect original recovery {recovery}, "
              f"staging {staging}, and run {run_dir}; nothing is permanently deleted",
              file=sys.stderr, flush=True)
        raise


def cleanup_run(run_dir: Path, apply: bool, acknowledged: bool, markers: Iterable[str]) -> dict[str, object]:
    run_dir = run_dir.absolute()
    if run_dir.is_symlink():
        fail(f"run directory must not be a symlink: {run_dir}")
    run_dir = run_dir.resolve()
    for suffix in ("staging", "original"):
        interrupted = run_dir.parent / f".{run_dir.name}.cleanup-{suffix}"
        if os.path.lexists(interrupted):
            fail(f"unfinished cleanup exists; inspect without deleting: {interrupted}")
    archive = run_dir / archive_name(run_dir)
    if os.path.lexists(archive):
        retained = validate_retained_layout(run_dir, archive)
        verify_archive(archive, run_dir, retained, exact=False)
        return {"status": "already-clean", "archive": str(archive), "trashed": 0}
    validate_run_dir(run_dir, archive)
    source = snapshot(run_dir, excluded_root_names=(archive.name,))
    found_markers = active_markers(source, markers)
    if found_markers:
        fail(f"run appears active; stop it and remove marker(s) before cleanup: {found_markers}")
    second = snapshot(run_dir, excluded_root_names=(archive.name,))
    if not snapshot_equal(source, second):
        fail("run is changing; wait for a stopped run before cleanup")
    source = second
    if apply and not acknowledged:
        fail("--apply requires explicit --acknowledge-stopped-run")
    if not shutil.which("zstd"):
        fail("zstd executable is required for archive creation")
    trash_command = find_trash()
    check_space(run_dir, source)
    if not apply:
        return {"status": "ready", "archive": str(archive), "entries": len(source.entries)}
    staging = stage_lightweight(run_dir, archive, source)
    # Re-check the source after writing and before moving anything.  A changed
    # source leaves a verified sibling staging directory plus all originals.
    after_archive = snapshot(run_dir, excluded_root_names=(archive.name,))
    if not snapshot_equal(source, after_archive):
        fail(f"run changed while archiving; verified staging retained at {staging}")
    publish_lightweight(run_dir, staging, source, trash_command)
    return {"status": "archived", "archive": str(run_dir / archive.name), "trashed": 1}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", help="completed autoresearch run directory")
    parser.add_argument("--apply", action="store_true", help="publish the archive and move originals to recoverable trash")
    parser.add_argument("--acknowledge-stopped-run", action="store_true", help="confirm that the evaluator is stopped (required with --apply)")
    parser.add_argument("--active-marker", action="append", default=[], help="additional run-relative marker that means the run is active")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    markers = set(DEFAULT_ACTIVE_MARKERS) | set(args.active_marker)
    try:
        result = cleanup_run(Path(args.run_dir), args.apply, args.acknowledge_stopped_run, markers)
    except (CleanupError, OSError) as error:
        print(f"cleanup: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
