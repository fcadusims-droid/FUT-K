"""Data sovereignty over HTTP: deny by default, offline mode (item 4)."""

from __future__ import annotations

import json

from fie.fusiondata import Context, Layer, Provenance, make_record

from app.knowledgestore import store_records


def _seed(db_session):
    store_records(db_session, [
        make_record("apps", 1, Layer.OBSERVED, Context(match_id="m1", player_id="p1"),
                    Provenance(source="statsbomb")),
        make_record("competition_strength", {"goals_per_match": 2.5}, Layer.DERIVED,
                    Context(competition="BL1"),
                    Provenance(source="engine", pipeline_version="ctx/v1")),
    ])


def test_sovereignty_default_denies(client):
    body = client.get("/sovereignty").json()
    assert body["default"] == "local_only"


def test_sync_view_is_empty_by_default(client, db_session):
    _seed(db_session)
    body = client.get("/knowledge/sync-view").json()
    assert body["count"] == 0 and body["records"] == []   # deny by default


def test_sync_view_respects_a_configured_policy(client, db_session, monkeypatch):
    _seed(db_session)
    monkeypatch.setenv("FUTK_SOVEREIGNTY",
                       json.dumps({"by_layer": {"derived": "syncable"}}))
    body = client.get("/knowledge/sync-view").json()
    # Only the derived aggregate leaves; the observed personal datum stays local.
    assert body["count"] == 1
    assert body["records"][0]["layer"] == "derived"
    assert body["records"][0]["kind"] == "competition_strength"


def test_offline_mode_disables_the_external_feed(client, monkeypatch):
    monkeypatch.setenv("FUTK_OFFLINE", "1")
    r = client.post("/live/anygame/footballdata?fd_id=1")
    assert r.status_code == 503 and "offline" in r.json()["detail"].lower()
