"""Confidence engine (Section 10).

Every diagnosis or probability is accompanied by how much the system trusts it.
Factors are combined with a geometric mean, so that one terrible factor collapses
the whole thing — which is exactly what we want.
"""

from __future__ import annotations


def confidence(
    n_events: float,
    source_quality: float,
    source_agreement: float,
    regime_instability: float,
    similar_cases: float,
    n_ref: float = 40,
    h_ref: float = 50,
) -> float:
    """A number in ``[0, 1]`` combining five factors via a geometric mean."""
    f_data = min(1.0, n_events / n_ref)
    f_source = max(0.0, min(1.0, source_quality))
    f_agree = max(0.0, min(1.0, source_agreement))
    f_regime = max(0.0, min(1.0, 1.0 - regime_instability))
    f_history = min(1.0, similar_cases / h_ref)
    # f_data / f_history are non-negative by construction (counts), so clamp to
    # [0,1] to stay robust to negative inputs before the geometric mean.
    f_data = max(0.0, f_data)
    f_history = max(0.0, f_history)
    return (f_data * f_source * f_agree * f_regime * f_history) ** 0.2
