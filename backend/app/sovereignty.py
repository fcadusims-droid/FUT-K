"""Active data-sovereignty policy (Application).

Loads the institution's sovereignty manifest (``FUTK_SOVEREIGNTY``, a JSON policy
for ``fie.sovereignty``) and falls back to **deny-by-default** — nothing may be
synced to the Federation unless the institution explicitly allows it.
"""

from __future__ import annotations

import json

from fie.sovereignty import DEFAULT_POLICY, SovereigntyPolicy, policy_from_dict

from .config import get_settings


def active_policy() -> SovereigntyPolicy:
    raw = get_settings().sovereignty_json
    if not raw:
        return DEFAULT_POLICY
    try:
        return policy_from_dict(json.loads(raw))
    except (ValueError, TypeError, KeyError):
        # A malformed manifest must not accidentally open the gates.
        return DEFAULT_POLICY
