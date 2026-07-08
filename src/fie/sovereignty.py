"""Data sovereignty — what may leave the institution (Inference).

Local infrastructure & independence (docs/design/LONG_TERM_VISION.md §7): each
institution keeps control of its own data. Joining the Federation never forces it
to share anything confidential. This module is the enforcement primitive: a
declarative policy that classifies every knowledge record as **local-only** or
**syncable**, so a sync client can only ever export what the institution has
explicitly allowed.

The default is **deny** — nothing leaves unless a rule says it may — so
sovereignty holds even if a policy is misconfigured or absent. Pure and
deterministic: same records + policy, same partition. Standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Sharing(str, Enum):
    LOCAL_ONLY = "local_only"   # never leaves the institution
    SYNCABLE = "syncable"       # may be shared with the Federation


@dataclass(frozen=True)
class SovereigntyPolicy:
    """Declares which knowledge may be synced. Deny by default.

    Resolution order for a record, most specific first: a locked **source** →
    always local; an explicit **kind** rule; an explicit **layer** rule; else the
    ``default``. Keeping ``default = LOCAL_ONLY`` means a datum only ever leaves
    when a rule deliberately allows it.
    """

    default: Sharing = Sharing.LOCAL_ONLY
    by_layer: dict = field(default_factory=dict)   # layer value -> Sharing
    by_kind: dict = field(default_factory=dict)    # kind -> Sharing
    local_sources: frozenset = frozenset()          # sources that never leave

    def classify(self, record) -> Sharing:
        if record.provenance.source in self.local_sources:
            return Sharing.LOCAL_ONLY
        if record.kind in self.by_kind:
            return self.by_kind[record.kind]
        layer = record.layer.value
        if layer in self.by_layer:
            return self.by_layer[layer]
        return self.default

    def is_syncable(self, record) -> bool:
        return self.classify(record) is Sharing.SYNCABLE

    def to_dict(self) -> dict:
        return {
            "default": self.default.value,
            "by_layer": {k: v.value for k, v in sorted(self.by_layer.items())},
            "by_kind": {k: v.value for k, v in sorted(self.by_kind.items())},
            "local_sources": sorted(self.local_sources),
        }


# The shipped default: maximally private — nothing syncs until the institution
# declares otherwise. Sovereignty by default.
DEFAULT_POLICY = SovereigntyPolicy()


def _sharing(value) -> Sharing:
    return value if isinstance(value, Sharing) else Sharing(value)


def policy_from_dict(data: dict) -> SovereigntyPolicy:
    """Build a policy from a manifest dict (e.g. parsed sovereignty config)."""
    data = data or {}
    return SovereigntyPolicy(
        default=_sharing(data.get("default", Sharing.LOCAL_ONLY.value)),
        by_layer={k: _sharing(v) for k, v in (data.get("by_layer") or {}).items()},
        by_kind={k: _sharing(v) for k, v in (data.get("by_kind") or {}).items()},
        local_sources=frozenset(data.get("local_sources") or ()),
    )


def partition(records, policy: SovereigntyPolicy = DEFAULT_POLICY):
    """Split records into ``(local_only, syncable)`` per the policy. Deterministic."""
    local, syncable = [], []
    for r in records:
        (syncable if policy.is_syncable(r) else local).append(r)
    return local, syncable


def syncable(records, policy: SovereigntyPolicy = DEFAULT_POLICY) -> list:
    """The records the institution has allowed to leave — the sync export set."""
    return [r for r in records if policy.is_syncable(r)]
