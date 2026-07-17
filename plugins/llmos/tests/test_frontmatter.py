"""Prove `llmos_vault.frontmatter`: the one canonical YAML-frontmatter
reader/writer (ADR-0004 -- "one frontmatter owner"). Normalization fixes key
order, the blank line after YAML, trailing whitespace, and the trailing
newline, without touching body content or wikilink quoting in YAML values.
"""

from __future__ import annotations

from pathlib import Path

from llmos_vault.frontmatter import append_unique, normalize, parse, serialize, set_scalar

FIXTURES = Path(__file__).parent / "fixtures" / "vault" / "notes"


def test_parse_splits_properties_and_body():
    properties, body = parse((FIXTURES / "normalized.md").read_text())

    assert properties["created"] == "2026-07-01"
    assert properties["authors"] == ["claude"]
    assert body.startswith("# Normalized fixture note")


def test_wikilink_quoting_preserved_in_parsed_value():
    properties, _ = parse((FIXTURES / "normalized.md").read_text())

    assert properties["categories"] == ["[[Knowledge]]"]


def test_round_trip_of_already_normalized_note_is_byte_identical():
    text = (FIXTURES / "normalized.md").read_text()

    assert normalize(text) == text


def test_normalize_twice_equals_normalize_once():
    text = (FIXTURES / "messy.md").read_text()

    once = normalize(text)
    twice = normalize(once)

    assert twice == once


def test_normalize_fixes_key_order():
    text = (FIXTURES / "messy.md").read_text()

    normalized = normalize(text)
    properties, _ = parse(normalized)

    assert list(properties.keys()) == sorted(properties.keys())


def test_normalize_adds_blank_line_after_yaml():
    text = (FIXTURES / "messy.md").read_text()

    normalized = normalize(text)

    assert "\n---\n\n#" in normalized


def test_normalize_strips_trailing_whitespace():
    text = (FIXTURES / "messy.md").read_text()

    normalized = normalize(text)

    for line in normalized.splitlines():
        assert line == line.rstrip()


def test_normalize_ends_with_single_trailing_newline():
    text = (FIXTURES / "messy.md").read_text()

    normalized = normalize(text)

    assert normalized.endswith("\n")
    assert not normalized.endswith("\n\n")


def test_normalize_preserves_body_content():
    text = (FIXTURES / "messy.md").read_text()

    normalized = normalize(text)

    assert "[[Some Other Note]]" in normalized
    assert "Body content, including a wikilink" in normalized


def test_serialize_quotes_wikilink_values():
    properties = {"categories": ["[[Knowledge]]"]}

    rendered = serialize(properties, "# body\n")

    assert '  - "[[Knowledge]]"' in rendered


def test_serialize_leaves_plain_scalars_unquoted():
    properties = {"created": "2026-07-01", "status": "active"}

    rendered = serialize(properties, "# body\n")

    assert "created: 2026-07-01\n" in rendered
    assert "status: active\n" in rendered


def test_set_scalar_sets_a_value():
    properties = {"status": "active"}

    set_scalar(properties, "updated", "2026-07-17")

    assert properties["updated"] == "2026-07-17"


def test_set_scalar_refuses_to_rewrite_created():
    properties = {"created": "2026-07-01"}

    try:
        set_scalar(properties, "created", "2026-07-17")
        raised = False
    except ValueError:
        raised = True

    assert raised
    assert properties["created"] == "2026-07-01"


def test_append_unique_appends_when_absent():
    properties = {"authors": ["claude"]}

    append_unique(properties, "authors", "codex")

    assert properties["authors"] == ["claude", "codex"]


def test_append_unique_is_a_no_op_when_already_present():
    properties = {"authors": ["claude", "codex"]}

    append_unique(properties, "authors", "codex")

    assert properties["authors"] == ["claude", "codex"]


def test_append_unique_creates_the_list_when_key_absent():
    properties: dict = {}

    append_unique(properties, "authors", "claude")

    assert properties["authors"] == ["claude"]


def test_empty_scalar_parses_as_empty_string_not_list():
    text = "---\ncreated: 2026-07-01\nnote:\n---\n\n# body\n"

    properties, _ = parse(text)

    assert properties["note"] == ""


def test_explicit_empty_list_still_parses_as_list():
    text = "---\ncreated: 2026-07-01\ntags: []\n---\n\n# body\n"

    properties, _ = parse(text)

    assert properties["tags"] == []


def test_empty_scalar_round_trips_byte_identically():
    text = "---\ncreated: 2026-07-01\nnote:\n---\n\n# body\n"

    assert normalize(text) == text


def test_normalize_empty_scalar_twice_equals_once():
    text = "---\nnote:\ncreated: 2026-07-01\n---\n\n# body\n"

    once = normalize(text)
    twice = normalize(once)

    assert twice == once


def test_parse_inline_flow_list():
    text = "---\ntags: [alpha, beta]\n---\n\n# body\n"

    properties, _ = parse(text)

    assert properties["tags"] == ["alpha", "beta"]


def test_parse_inline_flow_list_with_single_item():
    text = "---\ntags: [alpha]\n---\n\n# body\n"

    properties, _ = parse(text)

    assert properties["tags"] == ["alpha"]


def test_normalize_converts_inline_list_to_canonical_block_style():
    text = "---\ntags: [alpha, beta]\n---\n\n# body\n"

    normalized = normalize(text)

    assert "tags:\n  - alpha\n  - beta\n" in normalized


def test_normalize_inline_list_is_idempotent():
    text = "---\ntags: [alpha, beta]\n---\n\n# body\n"

    once = normalize(text)
    twice = normalize(once)

    assert twice == once
