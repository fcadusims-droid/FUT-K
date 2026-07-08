"""Dynamic Knowledge Management — knowledge as a temporal state.

Versions append (never overwrite), permanent changes settle while temporary ones
revert, and any date resolves to the state valid then — deterministically
(docs/design/DATASET_FUSION.md §Dynamic Knowledge).
"""

from __future__ import annotations

import pytest

from fie.fusiondata import PERMANENT, TEMPORARY, Context, IntegrityError, Layer
from fie.dynamics import (
    append_version,
    attribute_key,
    build_timeline,
    current_state,
    history,
    state_as_of,
    state_version,
    value_as_of,
)

P1 = Context(player_id="p1")


def _pos(value, valid_from, permanence=PERMANENT, valid_to=None, confidence=None):
    return state_version("position", value, P1, source="scout",
                         valid_from=valid_from, valid_to=valid_to,
                         permanence=permanence, confidence=confidence)


# --------------------------------------------------------------------------- #
# Building versions
# --------------------------------------------------------------------------- #
def test_state_version_carries_temporal_metadata():
    v = _pos("striker", "2019-01-01", confidence=0.8)
    assert v.temporal.valid_from == "2019-01-01"
    assert v.temporal.permanence == PERMANENT
    assert v.temporal.confidence == 0.8
    assert attribute_key(v) == ("position", "p1")


def test_invalid_permanence_rejected():
    with pytest.raises(IntegrityError):
        state_version("position", "x", P1, source="s", permanence="forever")


# --------------------------------------------------------------------------- #
# Append-only history: a permanent change closes the previous version
# --------------------------------------------------------------------------- #
def test_permanent_change_closes_prior_and_keeps_history():
    striker = _pos("striker", "2019-01-01")
    timeline = [striker]
    midfielder = _pos("midfielder", "2022-07-01")
    timeline = append_version(timeline, midfielder)

    # Both versions survive — nothing overwritten.
    assert len(timeline) == 2
    closed = next(r for r in timeline if r.value == "striker")
    assert closed.temporal.valid_to == "2022-07-01"        # closed at the change
    assert closed.temporal.superseded_by == midfielder.id  # linked forward
    assert not closed.temporal.is_current()
    assert midfielder.temporal.is_current()


def test_current_state_is_latest_permanent_live():
    tl = build_timeline([
        _pos("striker", "2019-01-01"),
        _pos("winger", "2020-08-01"),
        _pos("midfielder", "2022-07-01"),
    ])
    assert current_state(tl, "position", "p1").value == "midfielder"


# --------------------------------------------------------------------------- #
# As-of resolution: answer questions about the past
# --------------------------------------------------------------------------- #
def test_state_as_of_answers_the_past():
    tl = build_timeline([
        _pos("striker", "2019-01-01"),
        _pos("midfielder", "2022-07-01"),
    ])
    # "How did he play three seasons ago?" -> striker.
    assert value_as_of(tl, "2020-05-01", "position", "p1") == "striker"
    # Exactly at the change, the new state applies.
    assert value_as_of(tl, "2022-07-01", "position", "p1") == "midfielder"
    # After it -> midfielder.
    assert value_as_of(tl, "2024-01-01", "position", "p1") == "midfielder"
    # Before anything was known -> None / default.
    assert value_as_of(tl, "2000-01-01", "position", "p1", default="unknown") == "unknown"


# --------------------------------------------------------------------------- #
# Temporary states override while active, then revert
# --------------------------------------------------------------------------- #
def test_temporary_state_overrides_then_reverts():
    baseline = _pos("striker", "2019-01-01")
    # Improvised as a false nine for one match window.
    temp = _pos("false_nine", "2023-03-10", permanence=TEMPORARY,
                valid_to="2023-03-11", confidence=0.9)
    tl = append_version([baseline], temp)

    # A temporary change closes nothing on the baseline.
    assert len(tl) == 2
    assert baseline.temporal.is_current()
    # Inside the window the temporary state wins.
    assert value_as_of(tl, "2023-03-10", "position", "p1") == "false_nine"
    # Outside it the permanent baseline is back.
    assert value_as_of(tl, "2023-03-09", "position", "p1") == "striker"
    assert value_as_of(tl, "2023-04-01", "position", "p1") == "striker"
    # current_state ignores temporary overrides.
    assert current_state(tl, "position", "p1").value == "striker"


def test_confidence_breaks_ties_among_active_versions():
    # Two permanents active on the same day (same start): higher confidence wins.
    low = state_version("club", "A", P1, source="s1", valid_from="2024-01-01",
                        confidence=0.4)
    high = state_version("club", "B", P1, source="s2", valid_from="2024-01-01",
                         confidence=0.9)
    assert state_as_of([low, high], "2024-06-01", "club", "p1").value == "B"


# --------------------------------------------------------------------------- #
# History & determinism
# --------------------------------------------------------------------------- #
def test_history_is_ordered_and_complete():
    versions = [
        _pos("midfielder", "2022-07-01"),
        _pos("striker", "2019-01-01"),
        _pos("winger", "2020-08-01"),
    ]
    tl = build_timeline(versions)
    values = [r.value for r in history(tl, "position", "p1")]
    assert values == ["striker", "winger", "midfielder"]   # oldest-first, none lost


def test_build_timeline_is_deterministic():
    versions = [
        _pos("striker", "2019-01-01"),
        _pos("midfielder", "2022-07-01"),
        _pos("forward", "2024-01-01"),
    ]
    a = [r.to_dict() for r in build_timeline(versions)]
    b = [r.to_dict() for r in build_timeline(list(versions))]
    assert a == b


def test_append_version_does_not_mutate_input():
    striker = _pos("striker", "2019-01-01")
    original = [striker]
    append_version(original, _pos("midfielder", "2022-07-01"))
    assert len(original) == 1 and original[0].temporal.is_current()


def test_isolation_holds_across_entities():
    # p1 and p2 timelines never bleed into each other.
    p2 = state_version("position", "keeper", Context(player_id="p2"),
                       source="s", valid_from="2019-01-01", layer=Layer.OBSERVED)
    tl = build_timeline([_pos("striker", "2019-01-01"), p2])
    assert value_as_of(tl, "2020-01-01", "position", "p1") == "striker"
    assert value_as_of(tl, "2020-01-01", "position", "p2") == "keeper"
