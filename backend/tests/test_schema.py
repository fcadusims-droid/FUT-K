"""Phase A1 — production schema: portable creation, FK/relationship round-trip."""

from __future__ import annotations

from app.models import Interaction, Match, MatchEvent, Outcome, Prediction, Snapshot


def test_tables_created(engine):
    """init_db() creates every declared table."""
    from sqlalchemy import inspect

    names = set(inspect(engine).get_table_names())
    assert {
        "matches", "events", "snapshots", "predictions", "outcomes",
        "player_profiles", "interactions", "influence",
    } <= names


def test_match_events_roundtrip(db_session):
    """A match's events persist and relate back through the FK."""
    m = Match(id="m1", competition="Test League", home_team="A", away_team="B")
    db_session.add(m)
    db_session.add(MatchEvent(match_id="m1", minute=10.0, team="HOME", type="shot"))
    db_session.add(MatchEvent(match_id="m1", minute=20.0, team="AWAY", type="goal"))
    db_session.commit()

    fetched = db_session.get(Match, "m1")
    assert len(fetched.events) == 2
    assert {e.type for e in fetched.events} == {"shot", "goal"}


def test_prediction_outcome_roundtrip(db_session):
    """A prediction's outcome is reachable through the one-to-one relationship."""
    db_session.add(Match(id="m2", home_team="A", away_team="B"))
    db_session.commit()
    pred = Prediction(match_id="m2", minute=30.0, target="goal_10min", probability=0.42)
    db_session.add(pred)
    db_session.commit()
    db_session.add(Outcome(prediction_id=pred.id, happened=1))
    db_session.commit()

    fetched = db_session.get(Prediction, pred.id)
    assert fetched.outcome.happened == 1


def test_snapshot_and_interaction_persist(db_session):
    """Snapshots and passing-network interactions persist independently of events."""
    db_session.add(Match(id="m3", home_team="A", away_team="B"))
    db_session.commit()
    db_session.add(
        Snapshot(match_id="m3", minute=45.0, momentum=0.6, regime="PRESSURE",
                 confidence=0.8, lambda_home=0.02, lambda_away=0.01)
    )
    db_session.add(
        Interaction(scope="A 2015/2016", from_player="1", to_player="2",
                    passes=10, chances_created=2)
    )
    db_session.commit()

    snap = db_session.query(Snapshot).filter_by(match_id="m3").one()
    assert snap.regime == "PRESSURE"
    edge = db_session.query(Interaction).filter_by(scope="A 2015/2016").one()
    assert edge.passes == 10
