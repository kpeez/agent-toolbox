"""Prove the docs pipeline (spec 0014 behavior 10): every public
llmos_vault function and CLI verb carries the mandatory docstring
sections (when-to-use, when-NOT-to-use, output example, runnable
invocation), and `references/commands.md` matches what regenerating from
the live command tree produces. Verbs are discovered by walking the
package and the cyclopts app tree -- never a hardcoded list -- so a verb
added by a sibling slice is covered automatically once merged.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from pathlib import Path

import llmos_vault
from llmos_vault.cli import DEFAULT_REFERENCE_PATH, DEFAULT_SKILL_PATH, app
from llmos_vault.docs import iter_commands, render_reference, write_reference

MANDATORY_SECTIONS = ["Use when", "Do NOT use when", "Example output:", "Example invocation:"]


def _library_functions() -> list[tuple[str, object]]:
    functions = []
    for _, mod_name, _ in pkgutil.iter_modules(llmos_vault.__path__, prefix="llmos_vault."):
        if mod_name == "llmos_vault.cli":
            continue
        module = importlib.import_module(mod_name)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if name.startswith("_") or func.__module__ != mod_name:
                continue
            functions.append((f"{mod_name}.{name}", func))
    return functions


def _cli_verbs() -> list[tuple[str, object]]:
    return [(f"llmos-vault {name}", func) for name, func in iter_commands(app)]


DOCSTRING_TARGETS = sorted(_library_functions() + _cli_verbs())


def test_every_public_function_has_a_docstring():
    missing = [name for name, func in DOCSTRING_TARGETS if not inspect.getdoc(func)]

    assert not missing, f"functions with no docstring at all: {missing}"


def test_every_public_docstring_has_mandatory_sections():
    failures = []
    for name, func in DOCSTRING_TARGETS:
        doc = inspect.getdoc(func) or ""
        missing_sections = [section for section in MANDATORY_SECTIONS if section not in doc]
        if missing_sections:
            failures.append(f"{name} is missing: {', '.join(missing_sections)}")

    assert not failures, "\n".join(failures)


def test_docstring_check_discovers_functions_not_a_hardcoded_list():
    names = {name for name, _ in DOCSTRING_TARGETS}

    assert "llmos_vault.notes.read_note" in names
    assert "llmos_vault.graph.get_neighbors" in names
    assert "llmos-vault neighbors" in names
    assert "llmos-vault subgraph" in names


def test_generated_reference_contains_every_registered_verb():
    reference = render_reference(app)

    for name, _ in iter_commands(app):
        assert f"## `{name}`" in reference


def test_committed_reference_matches_regeneration(tmp_path: Path):
    regenerated_reference = tmp_path / "commands.md"
    regenerated_skill = tmp_path / "SKILL.md"
    regenerated_skill.write_text(DEFAULT_SKILL_PATH.read_text())

    write_reference(app, regenerated_reference, regenerated_skill)

    assert regenerated_reference.read_text() == DEFAULT_REFERENCE_PATH.read_text(), (
        "references/commands.md is stale -- run `uv run llmos-vault docs` to regenerate"
    )


def test_committed_skill_table_matches_regeneration(tmp_path: Path):
    regenerated_reference = tmp_path / "commands.md"
    regenerated_skill = tmp_path / "SKILL.md"
    regenerated_skill.write_text(DEFAULT_SKILL_PATH.read_text())

    write_reference(app, regenerated_reference, regenerated_skill)

    assert regenerated_skill.read_text() == DEFAULT_SKILL_PATH.read_text(), (
        "the skill's verb table is stale -- run `uv run llmos-vault docs` to regenerate"
    )


def test_regeneration_is_deterministic():
    assert render_reference(app) == render_reference(app)


def test_regeneration_has_no_timestamps():
    reference = render_reference(app)

    assert "generated on" not in reference.lower()
    assert "generated at" not in reference.lower()
