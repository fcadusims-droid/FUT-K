"""Knowledge Graph — relations derived deterministically from record context."""

from __future__ import annotations

from fie.fusiondata import Context, Layer, Provenance, Temporal, make_record
from fie.graph import Node, build_graph


def _rec(kind="ev", **ctx):
    return make_record(kind, 1, Layer.OBSERVED, Context(**ctx),
                       Provenance(source="statsbomb"))


def test_node_key():
    assert Node("player", "p1").key == "player:p1"


def test_edges_are_derived_from_context():
    g = build_graph([
        _rec(player_id="p1", team="bayern", match_id="m1", competition="BL1"),
    ])
    keys = set(g.edges)
    assert ("player:p1", "appeared_in", "match:m1") in keys
    assert ("player:p1", "played_for", "team:bayern") in keys
    assert ("team:bayern", "competed_in", "match:m1") in keys
    assert ("match:m1", "part_of", "competition:BL1") in keys
    assert ("player:p1", "active_in", "competition:BL1") in keys


def test_faced_edge_from_home_away():
    g = build_graph([_rec(kind="match", match_id="m1", home="leverkusen",
                          away="leipzig", competition="BL1")])
    assert ("team:leverkusen", "faced", "team:leipzig") in g.edges


def test_edges_aggregate_count_and_provenance():
    # Two records (two providers) putting the same player in the same match.
    r1 = make_record("a", 1, Layer.OBSERVED,
                     Context(player_id="p1", match_id="m1"),
                     Provenance(source="statsbomb"))
    r2 = make_record("b", 1, Layer.OBSERVED,
                     Context(player_id="p1", match_id="m1"),
                     Provenance(source="opta"))
    g = build_graph([r1, r2])
    edge = g.edges[("player:p1", "appeared_in", "match:m1")]
    assert edge.count == 2
    assert edge.sources == {"statsbomb", "opta"}


def test_neighbors_and_relations():
    g = build_graph([
        _rec(player_id="p1", team="bayern", match_id="m1"),
        _rec(player_id="p2", team="bayern", match_id="m1"),
    ])
    # Bayern's neighbours include both players (in) and the match (out).
    neigh = {n["node"]["key"] for n in g.neighbors("team:bayern")}
    assert {"player:p1", "player:p2", "match:m1"} <= neigh
    # Filter by relation.
    players = g.neighbors("team:bayern", relation="played_for")
    assert {n["node"]["key"] for n in players} == {"player:p1", "player:p2"}


def test_nodes_of_type():
    g = build_graph([
        _rec(player_id="p1", team="bayern", match_id="m1"),
        _rec(player_id="p2", team="dortmund", match_id="m1"),
    ])
    assert {n.id for n in g.nodes_of_type("player")} == {"p1", "p2"}
    assert {n.id for n in g.nodes_of_type("team")} == {"bayern", "dortmund"}


def test_as_of_filters_edges_by_validity():
    old = make_record("a", 1, Layer.OBSERVED,
                      Context(player_id="p1", team="milan"),
                      Provenance(source="s"),
                      temporal=Temporal(valid_from="2003-01-01", valid_to="2009-01-01"))
    new = make_record("b", 1, Layer.OBSERVED,
                      Context(player_id="p1", team="real madrid"),
                      Provenance(source="s"),
                      temporal=Temporal(valid_from="2009-01-01"))
    g = build_graph([old, new])
    # In 2005 the player is at Milan; in 2012 at Real Madrid.
    at_2005 = {n["node"]["key"] for n in g.neighbors("player:p1", as_of="2005-06-01")}
    at_2012 = {n["node"]["key"] for n in g.neighbors("player:p1", as_of="2012-06-01")}
    assert "team:milan" in at_2005 and "team:real madrid" not in at_2005
    assert "team:real madrid" in at_2012 and "team:milan" not in at_2012


def test_to_dict_and_determinism():
    records = [
        _rec(player_id="p1", team="bayern", match_id="m1", competition="BL1"),
        _rec(player_id="p2", team="bayern", match_id="m1", competition="BL1"),
    ]
    a = build_graph(records).to_dict()
    b = build_graph(list(records)).to_dict()
    assert a == b
    assert a["n_nodes"] >= 4 and a["n_edges"] >= 4
