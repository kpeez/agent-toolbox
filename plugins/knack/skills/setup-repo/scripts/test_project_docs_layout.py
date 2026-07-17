from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT = Path(__file__).with_name("setup_project_docs.py")
RETIRED_LINKS = ("docs/specs", "docs/adrs", "specs", "adrs")


def run_setup(
    repo: Path,
    llmos: Path,
    *,
    project: str = "sample",
    worktree: bool = False,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPT),
        "--repo-root",
        str(repo),
        "--llmos-root",
        str(llmos),
        "--project",
        project,
    ]
    if worktree:
        command.append("--worktree")
    return subprocess.run(command, capture_output=True, text=True, check=False)


def snapshot(root: Path) -> dict[str, tuple[str, object, int, int]]:
    state: dict[str, tuple[str, object, int, int]] = {}
    for path in sorted(root.rglob("*")):
        relative = str(path.relative_to(root))
        stat = path.lstat()
        if path.is_symlink():
            state[relative] = (
                "symlink",
                os.readlink(path),
                stat.st_ino,
                stat.st_mtime_ns,
            )
        elif path.is_file():
            state[relative] = ("file", path.read_bytes(), stat.st_ino, stat.st_mtime_ns)
        else:
            state[relative] = ("directory", "", stat.st_ino, stat.st_mtime_ns)
    return state


def assert_topology(repo: Path, llmos: Path, project: str = "sample") -> None:
    canonical = llmos / "projects" / project
    assert (canonical / "specs").is_dir()
    assert (canonical / "adrs").is_dir()

    assert os.readlink(repo / "docs/agents") == str(canonical)
    assert (repo / "docs/agents").resolve(strict=True).is_dir()
    assert (repo / "docs/agents/specs").is_dir()
    assert (repo / "docs/agents/adrs").is_dir()
    for retired in (*RETIRED_LINKS, "docs/adr"):
        assert not (repo / retired).is_symlink()


def test_clean_setup_creates_exact_topology_and_is_idempotent(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    (repo / ".gitignore").write_text("build/\n")

    first = run_setup(repo, llmos)

    assert first.returncode == 0, first.stderr
    assert_topology(repo, llmos)
    assert (repo / ".gitignore").read_text().splitlines() == ["build/", "docs/agents"]
    before = snapshot(tmp_path)

    second = run_setup(repo, llmos)

    assert second.returncode == 0, second.stderr
    assert snapshot(tmp_path) == before


def test_retired_layout_links_are_replaced_by_the_single_agents_link(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    canonical = llmos / "projects/sample"
    (canonical / "specs").mkdir(parents=True)
    (canonical / "adrs").mkdir()
    repo.mkdir()
    (repo / "docs").mkdir()
    (repo / ".gitignore").write_text("build/\nspecs\nadrs\ndocs/specs\ndocs/adrs\n")
    (repo / "docs/specs").symlink_to(canonical / "specs", target_is_directory=True)
    (repo / "docs/adrs").symlink_to(canonical / "adrs", target_is_directory=True)
    (repo / "specs").symlink_to("docs/specs")
    (repo / "adrs").symlink_to("docs/adrs")
    spec = canonical / "specs/0001-example.md"
    spec.write_bytes(b"canonical spec\n")

    result = run_setup(repo, llmos)

    assert result.returncode == 0, result.stderr
    assert_topology(repo, llmos)
    assert (repo / ".gitignore").read_text().splitlines() == ["build/", "docs/agents"]
    assert spec.read_bytes() == b"canonical spec\n"


def test_wrong_agents_symlink_is_repaired_without_touching_unrelated_content(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    (repo / "docs").mkdir()
    unrelated = repo / "README.md"
    unrelated.write_bytes(b"keep these exact bytes\n")
    (repo / "docs/agents").symlink_to("wrong-target")

    result = run_setup(repo, llmos)

    assert result.returncode == 0, result.stderr
    assert_topology(repo, llmos)
    assert unrelated.read_bytes() == b"keep these exact bytes\n"


@pytest.mark.parametrize("managed_path", ["docs/agents", "docs/specs", "docs/adr"])
def test_cross_project_symlinks_abort_before_any_mutation(
    tmp_path: Path, managed_path: str
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    (repo / ".gitignore").write_text("keep-this-exactly\n")
    target = llmos / "projects/other/docs"
    target.mkdir(parents=True)
    link = repo / managed_path
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    assert "points into llmOS project 'other'" in result.stderr
    assert snapshot(tmp_path) == before


def test_legacy_singular_adr_symlink_is_removed_without_following_its_target(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    (repo / "docs").mkdir()
    legacy_target = tmp_path / "legacy-adr-target"
    legacy_target.mkdir()
    preserved = legacy_target / "0001-preserved.md"
    preserved.write_bytes(b"do not follow or delete\n")
    legacy_link = repo / "docs/adr"
    legacy_link.symlink_to(legacy_target, target_is_directory=True)

    result = run_setup(repo, llmos)

    assert result.returncode == 0, result.stderr
    assert_topology(repo, llmos)
    assert not legacy_link.exists()
    assert not legacy_link.is_symlink()
    assert preserved.read_bytes() == b"do not follow or delete\n"


@pytest.mark.parametrize("legacy_name", ["specs", "adr"])
def test_project_legacy_symlinks_remain_collisions(
    tmp_path: Path, legacy_name: str
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    legacy_target = tmp_path / "legacy-target"
    legacy_target.mkdir()
    project = llmos / "projects/sample"
    project.mkdir(parents=True)
    (project / legacy_name).symlink_to(legacy_target, target_is_directory=True)
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    if legacy_name == "specs":
        assert "canonical path must be a real directory" in result.stderr
    else:
        assert "legacy source must be a real directory, found symlink" in result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("gitignore_kind", ["directory", "symlink", "undecodable-file"])
def test_invalid_gitignore_aborts_before_any_migration(
    tmp_path: Path, gitignore_kind: str
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    project = llmos / "projects/sample"
    repo.mkdir()
    (project / "specs").mkdir(parents=True)
    (project / "specs/SPEC.md").write_bytes(b"legacy spec bytes\n")
    gitignore = repo / ".gitignore"
    if gitignore_kind == "directory":
        gitignore.mkdir()
        (gitignore / "keep.txt").write_text("untouched\n")
    elif gitignore_kind == "symlink":
        target = tmp_path / "external-gitignore"
        target.write_text("external content\n")
        gitignore.symlink_to(target)
    else:
        gitignore.write_bytes(b"\xff")
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    assert "collisions detected before mutation" in result.stderr
    assert str(gitignore) in result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("occupant_kind", ["file", "directory"])
def test_occupied_agents_path_aborts_before_mutation(
    tmp_path: Path, occupant_kind: str
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    path = repo / "docs/agents"
    path.parent.mkdir(parents=True, exist_ok=True)
    if occupant_kind == "file":
        path.write_text("occupied\n")
    else:
        path.mkdir()
        (path / "keep.txt").write_text("occupied\n")
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    assert "collisions detected before mutation" in result.stderr
    assert str(path) in result.stderr
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("occupied", RETIRED_LINKS)
@pytest.mark.parametrize("occupant_kind", ["file", "directory"])
def test_occupied_retired_path_aborts_before_mutation(
    tmp_path: Path, occupied: str, occupant_kind: str
) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    repo.mkdir()
    path = repo / occupied
    path.parent.mkdir(parents=True, exist_ok=True)
    if occupant_kind == "file":
        path.write_text("occupied\n")
    else:
        path.mkdir()
        (path / "keep.txt").write_text("occupied\n")
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    assert "retired layout path must be a symlink or absent" in result.stderr
    assert str(path) in result.stderr
    assert snapshot(tmp_path) == before


def test_legacy_content_migrates_losslessly_exactly_once(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    project = llmos / "projects/sample"
    repo.mkdir()
    (project / "adr").mkdir(parents=True)
    (project / "adr/0001-project.md").write_bytes(b"project adr\n")
    (repo / "docs/adr/deep").mkdir(parents=True)
    (repo / "docs/adr/deep/0002-repo.md").write_bytes(b"repo adr\xff")
    unrelated = repo / "keep.bin"
    unrelated.write_bytes(b"unrelated\x00\xff")

    first = run_setup(repo, llmos)

    assert first.returncode == 0, first.stderr
    assert (project / "adrs/0001-project.md").read_bytes() == b"project adr\n"
    assert (project / "adrs/deep/0002-repo.md").read_bytes() == b"repo adr\xff"
    assert not (project / "adr").exists()
    assert not (repo / "docs/adr").exists()
    assert (repo / "docs/agents/adrs/deep/0002-repo.md").read_bytes() == b"repo adr\xff"
    assert unrelated.read_bytes() == b"unrelated\x00\xff"
    before = snapshot(tmp_path)

    second = run_setup(repo, llmos)

    assert second.returncode == 0, second.stderr
    assert snapshot(tmp_path) == before


def test_existing_specs_directory_is_left_exactly_where_it_is(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    project = llmos / "projects/sample"
    repo.mkdir()
    (project / "specs/nested").mkdir(parents=True)
    (project / "specs/nested/spec.md").write_bytes(b"my spec content\n")

    # Also add some adrs to migrate
    (project / "adr").mkdir()
    (project / "adr/0001-project.md").write_bytes(b"project adr\n")

    first = run_setup(repo, llmos)

    assert first.returncode == 0, first.stderr
    assert_topology(repo, llmos)
    # Check that specs is EXACTLY where it was, not moved or nested inside docs or deleted
    assert (project / "specs/nested/spec.md").read_bytes() == b"my spec content\n"
    # Check that the adr migrated to adrs
    assert (project / "adrs/0001-project.md").read_bytes() == b"project adr\n"
    assert not (project / "adr").exists()


def test_nonidentical_legacy_collision_aborts_without_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    project = llmos / "projects/sample"
    repo.mkdir()
    (project / "adr").mkdir(parents=True)
    (project / "adr/0001.md").write_bytes(b"from project\n")
    (repo / "docs/adr").mkdir(parents=True)
    (repo / "docs/adr/0001.md").write_bytes(b"from repo\n")
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    assert "non-identical legacy content" in result.stderr
    assert snapshot(tmp_path) == before


def test_existing_canonical_collision_aborts_without_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    project = llmos / "projects/sample"
    repo.mkdir()
    (project / "adr").mkdir(parents=True)
    (project / "adr/ADR.md").write_bytes(b"legacy\n")
    (project / "adrs").mkdir(parents=True)
    (project / "adrs/ADR.md").write_bytes(b"canonical\n")
    before = snapshot(tmp_path)

    result = run_setup(repo, llmos)

    assert result.returncode == 2
    assert "non-identical legacy content already exists" in result.stderr
    assert snapshot(tmp_path) == before


def test_identical_canonical_content_is_not_overwritten(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    llmos = tmp_path / "llmos"
    project = llmos / "projects/sample"
    repo.mkdir()
    (project / "adr").mkdir(parents=True)
    (project / "adr/ADR.md").write_bytes(b"same bytes\n")
    (project / "adrs").mkdir(parents=True)
    canonical = project / "adrs/ADR.md"
    canonical.write_bytes(b"same bytes\n")
    canonical_inode = canonical.stat().st_ino

    result = run_setup(repo, llmos)

    assert result.returncode == 0, result.stderr
    assert canonical.read_bytes() == b"same bytes\n"
    assert canonical.stat().st_ino == canonical_inode
    assert not (project / "adr").exists()


def test_worktree_mode_recreates_safe_links_but_refuses_migration(
    tmp_path: Path,
) -> None:
    llmos = tmp_path / "llmos"
    canonical = llmos / "projects/sample"
    (canonical / "specs").mkdir(parents=True)
    (canonical / "adrs").mkdir()
    safe_repo = tmp_path / "safe-repo"
    safe_repo.mkdir()

    safe = run_setup(safe_repo, llmos, worktree=True)

    assert safe.returncode == 0, safe.stderr
    assert_topology(safe_repo, llmos)
    assert not (safe_repo / ".gitignore").exists()

    migrating_repo = tmp_path / "migrating-repo"
    (migrating_repo / "docs/adr").mkdir(parents=True)
    (migrating_repo / "docs/adr/0001.md").write_text("legacy\n")
    before = snapshot(tmp_path)

    refused = run_setup(migrating_repo, llmos, worktree=True)

    assert refused.returncode == 2
    assert "Run /setup-repo" in refused.stderr
    assert snapshot(tmp_path) == before
