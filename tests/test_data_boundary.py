"""Executable rule: no FUT-K module consumes external data directly.

The Dataset Fusion's platform rule (docs/design/DATASET_FUSION.md): every datum
from an outside provider must pass through the ingestion pipeline and become the
canonical FUT-K dataset before any consumer touches it. Concretely, only modules
at the **ingestion boundary** may import ``fie.sources`` (the provider connectors)
or open a network connection; simulation, scouting, tactics, the panel, the API's
serving path and the knowledge layers must depend on the canonical store, never
on a source.

Enforced with ``ast`` like the layer rule, so a regression fails the build. When
a module legitimately joins the ingestion boundary, add it to ``INGESTION`` in
the same commit — the diff then documents the decision.
"""

from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).parent.parent
ENGINE = ROOT / "src" / "fie"
BACKEND = ROOT / "backend" / "app"

# The ingestion boundary: the only place external providers are read. Everything
# else consumes the canonical dataset. Connectors live under fie/sources; the
# backend ingestion/refresh path is listed explicitly.
INGESTION_BACKEND = {
    "ingest.py",        # multi-competition ingestion pipeline
    "livefeed.py",      # live football-data.org polling glue
    "learningloop.py",  # recalibration reads raw for the held-out refit
    "twin.py",          # builds the replay stream from the raw feed at ingest
    "network.py",       # builds the passing network from the raw cache at ingest
}

FORBIDDEN_ROOTS = {"urllib", "requests", "httpx", "aiohttp", "socket"}


def _imports(path: pathlib.Path):
    """(module_roots, imports_fie_sources) for one file."""
    tree = ast.parse(path.read_text())
    roots, uses_sources = set(), False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
                if alias.name.startswith("fie.sources"):
                    uses_sources = True
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            roots.add(mod.split(".")[0])
            if mod == "fie.sources" or mod.startswith("fie.sources."):
                uses_sources = True
            # `from .sources import x` / `from ..sources import x`
            if node.level and mod.split(".")[0] == "sources":
                uses_sources = True
    return roots, uses_sources


def test_engine_serving_modules_never_import_sources():
    """No engine module outside fie/sources imports a provider connector."""
    violations = []
    for path in sorted(ENGINE.glob("*.py")):
        if path.stem == "__init__":
            continue
        _, uses_sources = _imports(path)
        if uses_sources:
            violations.append(f"src/fie/{path.name} imports fie.sources")
    assert not violations, (
        "engine consumers must read the canonical dataset, not a source:\n"
        + "\n".join(violations)
    )


def test_backend_serving_path_never_imports_sources():
    """Only the ingestion allowlist may read providers; serving code may not."""
    violations = []
    for path in sorted(BACKEND.glob("*.py")):
        if path.name in INGESTION_BACKEND or path.stem == "__init__":
            continue
        _, uses_sources = _imports(path)
        if uses_sources:
            violations.append(
                f"backend/app/{path.name} imports fie.sources (not in the "
                f"ingestion boundary)"
            )
    assert not violations, (
        "serving modules must consume the canonical store, not a provider:\n"
        + "\n".join(violations)
    )


def test_engine_core_and_consumers_open_no_network():
    """Only the source connectors open a network connection, nothing else."""
    violations = []
    for path in sorted(ENGINE.glob("*.py")):
        roots, _ = _imports(path)
        offending = roots & FORBIDDEN_ROOTS
        if offending:
            violations.append(f"src/fie/{path.name} imports {sorted(offending)}")
    # fie/sources/* are the connectors and are expected to use urllib; the
    # top-level engine modules must not.
    assert not violations, (
        "network access belongs only in the source connectors:\n"
        + "\n".join(violations)
    )
