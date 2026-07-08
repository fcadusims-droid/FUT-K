"""Data sovereignty — deny by default; only declared knowledge may sync."""

from __future__ import annotations

from fie.fusiondata import Context, Layer, Provenance, make_record
from fie.sovereignty import (
    DEFAULT_POLICY,
    Sharing,
    SovereigntyPolicy,
    partition,
    policy_from_dict,
    syncable,
)


def _rec(kind="k", layer=Layer.OBSERVED, source="statsbomb"):
    prov = Provenance(source=source, pipeline_version="v1")
    return make_record(kind, 1, layer, Context(match_id="m1"), prov)


def test_default_policy_denies_everything():
    recs = [_rec(layer=Layer.OBSERVED), _rec(layer=Layer.DERIVED)]
    local, sync = partition(recs)                 # DEFAULT_POLICY
    assert len(local) == 2 and sync == []
    assert DEFAULT_POLICY.default is Sharing.LOCAL_ONLY


def test_layer_rule_allows_only_declared_layers():
    policy = SovereigntyPolicy(by_layer={"derived": Sharing.SYNCABLE})
    observed = _rec(layer=Layer.OBSERVED)
    derived = _rec(layer=Layer.DERIVED)
    assert policy.is_syncable(derived) and not policy.is_syncable(observed)
    assert syncable([observed, derived], policy) == [derived]


def test_kind_rule_overrides_layer():
    policy = SovereigntyPolicy(
        by_layer={"derived": Sharing.SYNCABLE},
        by_kind={"player_embedding": Sharing.LOCAL_ONLY},   # keep personal DNA home
    )
    keep = _rec(kind="player_embedding", layer=Layer.DERIVED)
    share = _rec(kind="competition_strength", layer=Layer.DERIVED)
    assert not policy.is_syncable(keep) and policy.is_syncable(share)


def test_locked_source_never_leaves():
    policy = SovereigntyPolicy(default=Sharing.SYNCABLE,
                               local_sources=frozenset({"club-medical"}))
    medical = _rec(source="club-medical")
    public = _rec(source="statsbomb")
    assert not policy.is_syncable(medical) and policy.is_syncable(public)


def test_policy_round_trips_through_a_manifest():
    policy = SovereigntyPolicy(
        default=Sharing.LOCAL_ONLY,
        by_layer={"derived": Sharing.SYNCABLE},
        by_kind={"win_prob": Sharing.SYNCABLE},
        local_sources=frozenset({"club-medical"}))
    rebuilt = policy_from_dict(policy.to_dict())
    assert rebuilt == policy


def test_partition_is_deterministic():
    policy = policy_from_dict({"default": "local_only",
                               "by_layer": {"probabilistic": "syncable"}})
    recs = [_rec(layer=Layer.PROBABILISTIC), _rec(layer=Layer.OBSERVED)]
    a = partition(recs, policy)
    b = partition(list(recs), policy)
    assert [r.id for r in a[0]] == [r.id for r in b[0]]
    assert [r.id for r in a[1]] == [r.id for r in b[1]]
