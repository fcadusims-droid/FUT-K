"""Plugin system (Inference layer): extend FUT-K without touching the core.

A **match-metric plugin** is a pure function of ``(events, params)`` returning
a small dict with at least ``value`` (bounded number) and ``summary`` (one
human-readable sentence). Plugins register through the decorator and are
discovered from plain ``.py`` files in a plugins directory — so third parties
add capability by *dropping a file in*, never by editing the engine.

    from fie.plugins import match_metric

    @match_metric("expected_chaos", "How wild this match was, 0..1")
    def expected_chaos(events, params):
        ...
        return {"value": 0.83, "summary": "A wild one: ..."}

Rules (enforced by tests/test_architecture.py): plugins import only the
engine's Core/Inference layers, do no I/O, and are deterministic.
"""

from __future__ import annotations

import importlib.util
import pathlib
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MetricPlugin:
    name: str
    description: str
    compute: Callable  # (events, params) -> dict with "value" and "summary"


_REGISTRY: dict = {}


def match_metric(name: str, description: str = ""):
    """Decorator: register a match-metric plugin under ``name``."""

    def wrap(fn: Callable) -> Callable:
        _REGISTRY[name] = MetricPlugin(name=name, description=description, compute=fn)
        return fn

    return wrap


def registered() -> dict:
    """The current registry (name -> MetricPlugin)."""
    return dict(_REGISTRY)


def clear() -> None:
    """Reset the registry (tests)."""
    _REGISTRY.clear()


def load_plugins(directory) -> list:
    """Import every ``*.py`` file in ``directory``; return loaded plugin names.

    Files register themselves via the decorator at import time. A broken file
    is skipped with its error recorded, never crashing the host application.
    """
    loaded, before = [], set(_REGISTRY)
    path = pathlib.Path(directory)
    if not path.is_dir():
        return loaded
    for file in sorted(path.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"futk_plugin_{file.stem}", file)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - a bad plugin must not kill the app
            loaded.append(f"{file.name}: FAILED ({exc})")
    loaded.extend(sorted(set(_REGISTRY) - before))
    return loaded


def run_all(events, params) -> dict:
    """Run every registered plugin; errors are reported, never raised."""
    out = {}
    for name, plugin in sorted(_REGISTRY.items()):
        try:
            result = plugin.compute(events, params)
            out[name] = {"description": plugin.description, **result}
        except Exception as exc:  # noqa: BLE001
            out[name] = {"description": plugin.description, "error": str(exc)}
    return out
