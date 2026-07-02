"""Passing-network payload (offline) + endpoint guards."""

from __future__ import annotations

from app.network import network_payload


def _pass(pid, name, rid, rname, chance=False):
    e = {"type": {"name": "Pass"}, "team": {"name": "Alpha"},
         "player": {"id": pid, "name": name},
         "pass": {"recipient": {"id": rid, "name": rname}}}
    if chance:
        e["pass"]["shot_assist"] = True
    return e


EVENTS = (
    [_pass(1, "Ana Pivot", 2, "Bea Wing") for _ in range(5)]
    + [_pass(2, "Bea Wing", 1, "Ana Pivot") for _ in range(3)]
    + [_pass(1, "Ana Pivot", 3, "Cal Nine", chance=True)]
    + [{"type": {"name": "Pass"}, "team": {"name": "Beta"},
        "player": {"id": 9, "name": "Rival"},
        "pass": {"recipient": {"id": 8, "name": "Other"}}}]
)


def test_network_payload_structure():
    p = network_payload(EVENTS, "Alpha")
    assert p["team"] == "Alpha"
    ids = [n["id"] for n in p["nodes"]]
    assert ids[0] == "1"  # Ana is the busiest node
    assert "9" not in ids  # other team excluded
    assert p["nodes"][0]["label"] == "Pivot"  # short label = last name
    top = p["edges"][0]
    assert (top["from"], top["to"], top["passes"]) == ("1", "2", 5)
    assert any(e["chances"] == 1 for e in p["edges"])
    assert 0.0 <= p["robustness"] <= 1.0
    assert 0.0 <= p["dependence"] <= 1.0


def test_network_payload_empty():
    p = network_payload([], "Alpha")
    assert p["nodes"] == [] and p["edges"] == []


def test_network_endpoint_404_unknown_match(client):
    assert client.get("/matches/nope/network").status_code == 404
