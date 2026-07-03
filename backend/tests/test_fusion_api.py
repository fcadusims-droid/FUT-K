"""Fused records in the production DB: store, idempotence, API exposure."""

from __future__ import annotations

from fie.fusion import resolve_matches

from app.fusionstore import list_fused, store_fused

FIELDS = {"home_goals": 0, "away_goals": 0, "corners_home": 0}
PRIORS = {"alpha": 0.95, "beta": 0.9}

SOURCES = {
    "alpha": [
        {"date": "2024-04-14", "home": "Leverkusen", "away": "Werder Bremen",
         "home_goals": 5, "away_goals": 0, "corners_home": 7},
    ],
    "beta": [
        {"date": "2024-04-14", "home": "Bayer 04 Leverkusen", "away": "SV Werder Bremen",
         "home_goals": 5, "away_goals": 0, "corners_home": 8},
        {"date": "2024-04-20", "home": "Union Berlin", "away": "Bayern Munich",
         "home_goals": 1, "away_goals": 5, "corners_home": 2},  # single-source
    ],
}


def test_store_fused_is_idempotent_and_keeps_provenance(db_session):
    resolved = resolve_matches(SOURCES)
    first = store_fused(db_session, "Bundesliga 2023/24", resolved, FIELDS, PRIORS)
    # Only the fixture seen by 2+ sources is stored; corners conflict recorded.
    assert first == {"stored": 1, "updated": 0, "conflicts": 1}

    again = store_fused(db_session, "Bundesliga 2023/24", resolved, FIELDS, PRIORS)
    assert again == {"stored": 0, "updated": 1, "conflicts": 1}

    records = list_fused(db_session)
    assert len(records) == 1
    rec = records[0]
    assert rec["home_team"] == "bayer leverkusen"       # canonical entity keys
    assert rec["away_team"] == "werder bremen"
    assert rec["sources"] == ["alpha", "beta"]
    assert rec["fields"]["home_goals"]["value"] == 5
    assert rec["fields"]["home_goals"]["agreed"] is True
    assert rec["fields"]["corners_home"]["value"] == 7  # alpha wins by prior
    assert rec["fields"]["corners_home"]["dissent"] == {"beta": 8}
    assert rec["conflicts"] == ["corners_home"]


def test_fusion_records_endpoint_filters(client, db_session):
    resolved = resolve_matches(SOURCES)
    store_fused(db_session, "Bundesliga 2023/24", resolved, FIELDS, PRIORS)

    body = client.get("/fusion/records").json()
    assert len(body) == 1 and body[0]["league"] == "Bundesliga 2023/24"

    assert client.get("/fusion/records?team=leverkusen").json()
    assert client.get("/fusion/records?team=nonexistent").json() == []
    assert client.get("/fusion/records?conflicts_only=true").json()
    assert client.get("/fusion/records?league=Serie%20A").json() == []
