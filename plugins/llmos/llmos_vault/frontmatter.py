"""The one canonical YAML-frontmatter reader/writer for the vault.

Hooks and every later verb import this module in-process (ADR-0004) -- no
second serializer may exist. Values are stored unquoted; quoting is decided
on output from content alone (a wikilink like `[[Knowledge]]` is always
quoted, since bare `[` opens a YAML flow sequence), which keeps parse+
serialize idempotent without having to remember each value's original
quoting style.

Properties serialize in sorted key order, with exactly one blank line after
the closing `---`, no trailing whitespace on any line, and exactly one
trailing newline at end of file. Body content is never touched beyond that.
"""

from __future__ import annotations

Property = str | list[str]


def _is_wikilink(value: str) -> bool:
    return value.startswith("[[") and value.endswith("]]")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def parse(text: str) -> tuple[dict[str, Property], str]:
    """Split `text` into (properties, body); raises if there is no frontmatter.

    Use when the note is known to require a frontmatter block -- a missing
    block is a real error, not something to paper over.
    Do NOT use when walking arbitrary vault files that may lack frontmatter
    -- use `llmos_vault.links.read_frontmatter`, which tolerates a bare body.

    Example output:
        ({'topics': ['gardening']}, '# Alpha\\n...')

    Example invocation:
        from llmos_vault.frontmatter import parse
        parse("---\\ntopics: gardening\\n---\\n\\n# Alpha\\n")

    Args:
        text: Full file text, frontmatter block plus body.

    Raises:
        ValueError: The text has no `---`-delimited frontmatter block.
    """
    if not text.startswith("---\n"):
        raise ValueError("note has no frontmatter block (must start with '---')")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("note's frontmatter block is never closed with '---'")
    body = text[end + len("\n---\n") :].lstrip("\n")

    properties: dict[str, Property] = {}
    current: str | None = None
    for line in text[4:end].splitlines():
        if line.startswith("  - ") and current is not None:
            existing = properties[current]
            assert isinstance(existing, list)
            existing.append(_unquote(line[4:].strip()))
            continue
        key, _, value = line.partition(":")
        current = key.strip()
        value = value.strip()
        if value == "" or value == "[]":
            properties[current] = []
        else:
            properties[current] = _unquote(value)
    return properties, body


def serialize(properties: dict[str, Property], body: str) -> str:
    """Render `properties` + `body` as a normalized note (sorted keys, one
    blank line after `---`, no trailing whitespace, one trailing newline).

    Use when writing a note back to disk after changing its properties or
    body -- every mutation path renders through this so the file stays in
    the vault's one canonical shape.
    Do NOT use when you have raw file text, not parsed properties/body --
    call `parse` (or `read_frontmatter`) first.

    Example output:
        '---\\ntopics:\\n  - gardening\\n---\\n\\n# Alpha\\n'

    Example invocation:
        from llmos_vault.frontmatter import serialize
        serialize({"topics": ["gardening"]}, "# Alpha\\n")

    Args:
        properties: Frontmatter properties to render.
        body: Note body text.
    """
    lines = ["---"]
    for key in sorted(properties):
        value = properties[key]
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
                continue
            lines.append(f"{key}:")
            for item in value:
                rendered = f'"{item}"' if _is_wikilink(item) else item
                lines.append(f"  - {rendered}")
        else:
            rendered = f'"{value}"' if _is_wikilink(value) else value
            lines.append(f"{key}: {rendered}")
    lines.append("---")
    lines.append("")

    body_lines = [line.rstrip() for line in body.splitlines()]
    while body_lines and body_lines[-1] == "":
        body_lines.pop()

    return "\n".join(lines + body_lines) + "\n"


def normalize(text: str) -> str:
    """Parse then re-serialize `text`, fixing key order, blank line, trailing
    whitespace, and trailing newline. Idempotent: normalize(normalize(x)) ==
    normalize(x).

    Use when a hook or CLI verb needs to re-format a note's frontmatter
    without changing any property values -- the PostToolUse stamp/format hook
    calls this on every vault write.
    Do NOT use when you also need to change a property's value -- parse,
    mutate with `set_scalar`/`append_unique`, then `serialize` instead.

    Example output:
        '---\\ntopics:\\n  - gardening\\n---\\n\\n# Alpha\\n'

    Example invocation:
        from llmos_vault.frontmatter import normalize
        normalize("---\\ntopics: gardening\\n---\\n# Alpha")

    Args:
        text: Full file text, frontmatter block plus body.
    """
    properties, body = parse(text)
    return serialize(properties, body)


def set_scalar(properties: dict[str, Property], key: str, value: str) -> dict[str, Property]:
    """Set a scalar property in place. `created` is immutable -- it is never
    rewritten.

    Use when a verb needs to overwrite a single-value property -- e.g.
    stamping `updated` to today's date.
    Do NOT use when the property is a list you want to add to, not replace
    -- use `append_unique`, which preserves existing entries.

    Example output:
        {'updated': '2026-07-17', 'topics': ['gardening']}

    Example invocation:
        from llmos_vault.frontmatter import set_scalar
        set_scalar({"topics": ["gardening"]}, "updated", "2026-07-17")

    Args:
        properties: Frontmatter properties to mutate.
        key: Property name to set.
        value: New scalar value.

    Raises:
        ValueError: `key` is "created" -- that property is never rewritten.
    """
    if key == "created":
        raise ValueError("created is immutable and must never be rewritten")
    properties[key] = value
    return properties


def append_unique(properties: dict[str, Property], key: str, value: str) -> dict[str, Property]:
    """Append `value` to the list property `key` in place, unless already present.

    Use when a verb needs to add to a list property without duplicating an
    existing entry -- e.g. appending the current provider to `authors`.
    Do NOT use when the property holds a single scalar value you want to
    replace -- use `set_scalar` instead.

    Example output:
        {'authors': ['claude', 'codex']}

    Example invocation:
        from llmos_vault.frontmatter import append_unique
        append_unique({"authors": ["claude"]}, "authors", "codex")

    Args:
        properties: Frontmatter properties to mutate.
        key: List property name to append to.
        value: Value to append if not already present.
    """
    existing = properties.get(key, [])
    if not isinstance(existing, list):
        existing = [existing]
    if value not in existing:
        existing.append(value)
    properties[key] = existing
    return properties
