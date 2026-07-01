"""Section 12, Layer 5 — passing-network extraction (offline)."""

from __future__ import annotations

from fie import db as fie_db
from fie.players import critical_links, passing_network
from fie.sources.statsbomb import passing_records
from fie.tactical import team_robustness


def _pass(team, pid, name, rid, rname, *, incomplete=False, shot_assist=False):
    e = {
        "type": {"name": "Pass"},
        "team": {"name": team},
        "player": {"id": pid, "name": name},
        "pass": {},
    }
    if rid is not None:
        e["pass"]["recipient"] = {"id": rid, "name": rname}
    if incomplete:
        e["pass"]["outcome"] = {"name": "Incomplete"}
    if shot_assist:
        e["pass"]["shot_assist"] = True
    return e


EVENTS = [
    _pass("Alpha", 1, "A", 2, "B"),
    _pass("Alpha", 1, "A", 2, "B", shot_assist=True),
    _pass("Alpha", 2, "B", 1, "A"),
    _pass("Alpha", 1, "A", 3, "C", incomplete=True),  # failed -> not in graph
    _pass("Beta", 9, "X", 8, "Y"),                     # other team -> skipped
]


def test_passing_records_filter_and_flags():
    names = {}
    records = passing_records(EVENTS, "Alpha", names)
    assert len(records) == 4  # only Alpha passes
    # the incomplete pass is not a success
    failed = [r for r in records if r.to == "3"]
    assert failed and failed[0].success is False
    assert names["1"] == "A" and names["2"] == "B"


def test_network_weights_and_chances():
    graph = passing_network(passing_records(EVENTS, "Alpha"))
    assert graph[("1", "2")]["weight"] == 2
    assert graph[("1", "2")]["chances"] == 1
    assert graph[("2", "1")]["weight"] == 1
    assert ("1", "3") not in graph  # incomplete pass excluded
    # A and B are the central pair.
    assert set(critical_links(graph, top=2)) == {"1", "2"}
    assert 0.0 <= team_robustness(graph) <= 1.0


def test_interactions_roundtrip():
    graph = passing_network(passing_records(EVENTS, "Alpha"))
    names = {"1": "A", "2": "B"}
    conn = fie_db.connect(":memory:")
    fie_db.init_schema(conn)
    fie_db.insert_interactions(conn, "Alpha test", graph, names)
    rows = conn.execute(
        "SELECT from_player, to_player, passes, chances_created FROM interactions "
        "ORDER BY passes DESC"
    ).fetchall()
    assert rows[0] == ("A", "B", 2, 1)
