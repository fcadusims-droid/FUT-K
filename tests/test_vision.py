"""Vision Engine — deterministic state estimation, prediction, self-evaluation."""

from __future__ import annotations

from fie.vision import (
    EntityState,
    correct,
    estimate_positions,
    evaluate_prediction,
    predict,
)


def _stream(*items):
    return [{"t": t, "x": x, "y": y, "player_id": pid, "player": nm}
            for (t, x, y, pid, nm) in items]


def test_predict_holds_position_by_default_moves_with_velocity_when_asked():
    s = EntityState(x=50.0, y=50.0, vx=4.0, vy=0.0, confidence=1.0,
                    last_obs_t=0.0, t=0.0)
    # Default (event-data best): hold position, decay confidence.
    held = predict(s, 2.0)
    assert held.x == 50.0 and held.confidence < 1.0
    # Kinematic model (for dense tracking data): moves right, drag-limited.
    moved = predict(s, 2.0, use_velocity=True)
    assert 50.0 < moved.x < 58.0 and moved.confidence < 1.0
    # No time passed -> unchanged position, full confidence.
    assert predict(s, 0.0).x == 50.0


def test_correct_measures_prediction_error_and_resets_confidence():
    # First observation: no prediction, no error.
    s0, e0 = correct(None, 0.0, 50.0, 50.0)
    assert e0 is None and s0.confidence == 1.0
    # Second at t=1 establishes velocity (moved +5 in x).
    s1, e1 = correct(s0, 1.0, 55.0, 50.0)
    assert s1.vx > 0 and s1.confidence == 1.0
    # Third: the engine predicts ~60 (continuing +5/s); observe exactly 60 ->
    # small error. Observe 50 instead -> large error.
    _, small = correct(s1, 2.0, 60.0, 50.0)
    _, large = correct(s1, 2.0, 50.0, 50.0)
    assert small < large


def test_estimate_positions_predicts_gaps_and_drops_stale():
    stream = _stream(
        (10.0, 40.0, 50.0, "p1", "Ana"),
        (11.0, 45.0, 50.0, "p1", "Ana"),      # moving +5/s in x
        (12.0, 20.0, 20.0, "p2", "Bia"),       # last seen long ago
    )
    # At t=12, p1 unobserved for 1s. Default holds its last position (45) with
    # lowered confidence; the kinematic model would push it ahead.
    est = estimate_positions(stream, 12.0)
    assert "p1" in est
    assert est["p1"]["x"] == 45.0 and est["p1"]["confidence"] < 1.0
    assert est["p1"]["name"] == "Ana"
    kin = estimate_positions(stream, 12.0, use_velocity=True)
    assert kin["p1"]["x"] > 45.0
    # p2 was just observed at 12 -> confidence 1, observed flag.
    assert est["p2"]["observed"] and est["p2"]["confidence"] == 1.0
    # Far in the future, everyone is stale and honestly dropped.
    assert estimate_positions(stream, 200.0) == {}


def test_estimate_positions_is_deterministic():
    stream = _stream(
        (10.0, 40.0, 50.0, "p1", "Ana"), (11.0, 45.0, 52.0, "p1", "Ana"),
        (12.5, 60.0, 40.0, "p1", "Ana"),
    )
    assert estimate_positions(stream, 13.0) == estimate_positions(stream, 13.0)


def test_self_evaluation_beats_static_on_moving_entity():
    # A player moving steadily: the motion model should predict the next touch
    # better than "assume they stayed put".
    stream = _stream(*[
        (float(t), 10.0 + 4.0 * t, 50.0, "p1", "Ana") for t in range(8)
    ])
    ev = evaluate_prediction(stream)
    assert ev["n"] > 0
    assert ev["beats_static_by"] > 0        # motion model < static error
    assert ev["mean_error"] < ev["static_baseline_mean"]
