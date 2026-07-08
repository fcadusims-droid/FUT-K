"""Knowledge Graph over HTTP: relations from the canonical store (item 2)."""

from __future__ import annotations

from fie.fusiondata import Context, Layer, Provenance, make_record

from app.knowledgestore import store_records


def _seed(db_session):
    recs = [
        make_record("apps", 1, Layer.OBSERVED,
                    Context(player_id="p1", team="bayern", match_id="m1",
                            competition="BL1"), Provenance(source="statsbomb")),
        make_record("apps", 1, Layer.OBSERVED,
                    Context(player_id="p2", team="bayern", match_id="m1",
                            competition="BL1"), Provenance(source="statsbomb")),
        make_record("fixture", 1, Layer.OBSERVED,
                    Context(match_id="m1", home="bayern", away="dortmund",
                            competition="BL1"), Provenance(source="football_data")),
    ]
    store_records(db_session, recs)


def test_graph_whole_view(client, db_session):
    _seed(db_session)
    g = client.get("/knowledge/graph").json()
    edges = {(e["source"], e["relation"], e["target"]) for e in g["edges"]}
    assert ("player:p1", "played_for", "team:bayern") in edges
    assert ("match:m1", "part_of", "competition:BL1") in edges
    assert ("team:bayern", "faced", "team:dortmund") in edges
    assert g["n_nodes"] >= 5


def test_graph_entity_neighbourhood(client, db_session):
    _seed(db_session)
    body = client.get("/knowledge/graph?entity=team:bayern").json()
    neigh = {n["node"]["key"] for n in body["neighbors"]}
    assert {"player:p1", "player:p2", "match:m1"} <= neigh
    # Filter by relation.
    players = client.get(
        "/knowledge/graph?entity=team:bayern&relation=played_for").json()
    assert {n["node"]["key"] for n in players["neighbors"]} == {"player:p1", "player:p2"}


def test_graph_nodes_of_type(client, db_session):
    _seed(db_session)
    body = client.get("/knowledge/graph?node_type=player").json()
    assert {n["id"] for n in body["nodes"]} == {"p1", "p2"}
