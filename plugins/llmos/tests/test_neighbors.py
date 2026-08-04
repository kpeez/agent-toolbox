"""Prove the headless link graph (spec behavior 5): `get_neighbors` and
`get_subgraph` return outgoing links, backlinks, and shared-topic siblings
straight from the fixture vault on disk, with Obsidian not running.
"""

from __future__ import annotations

from pathlib import Path

from llmos_vault.graph import get_neighbors, get_subgraph
from llmos_vault.notes import list_notes, read_note

VAULT = Path(__file__).parent / "fixtures" / "vault"


def test_get_neighbors_returns_outgoing_links():
    neighbors = get_neighbors(VAULT, "alpha")

    assert neighbors.outgoing == ["beta"]


def test_get_neighbors_reports_unresolved_outgoing_links():
    neighbors = get_neighbors(VAULT, "alpha")

    assert neighbors.unresolved_outgoing == ["ghost"]


def test_get_neighbors_returns_backlinks():
    neighbors = get_neighbors(VAULT, "alpha")

    assert neighbors.backlinks == ["delta"]


def test_get_neighbors_returns_shared_topic_siblings():
    neighbors = get_neighbors(VAULT, "alpha")

    assert neighbors.topic_siblings == ["beta", "gamma"]


def test_get_subgraph_depth_one_excludes_second_hop_note():
    subgraph = get_subgraph(VAULT, "alpha", depth=1)

    assert set(subgraph.nodes) == {"alpha", "beta", "delta", "gamma"}
    assert "epsilon" not in subgraph.nodes


def test_get_subgraph_depth_two_includes_second_hop_note():
    subgraph = get_subgraph(VAULT, "alpha", depth=2)

    assert set(subgraph.nodes) == {"alpha", "beta", "delta", "gamma", "epsilon"}


def test_get_subgraph_reports_unresolved_links_not_errors():
    subgraph = get_subgraph(VAULT, "alpha", depth=1)

    assert subgraph.unresolved == ["ghost"]


def test_get_subgraph_includes_link_and_topic_sibling_edges():
    subgraph = get_subgraph(VAULT, "alpha", depth=1)

    assert ("alpha", "beta", "link") in subgraph.edges
    assert ("delta", "alpha", "link") in subgraph.edges
    assert ("alpha", "gamma", "topic_sibling") in subgraph.edges


def test_read_note_returns_content_and_properties():
    note = read_note(VAULT, "alpha")

    assert note.properties["topics"] == ["gardening"]
    assert note.body.startswith("# Alpha")


def test_list_notes_enumerates_every_note_including_those_without_frontmatter():
    notes = list_notes(VAULT)

    names = {n.name for n in notes}
    assert {"alpha", "beta", "gamma", "delta", "epsilon"} <= names
    assert "AGENTS" in names
