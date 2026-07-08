"""Executable architecture: dependencies point down, never up.

Parses every engine module's imports with ``ast`` and fails if any module
imports a layer above its own (docs/ARCHITECTURE.md). Changing the layer map
here is allowed — but it must happen in the same commit as the code that
needs it, so the diff documents the decision.
"""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).parent.parent / "src" / "fie"
PLUGINS_DIR = pathlib.Path(__file__).parent.parent / "plugins"

LAYERS = {"core": 0, "inference": 1, "knowledge": 2, "application": 3}

MODULE_LAYER = {
    "events": "core",
    "eventbus": "core",
    "indices": "core",
    "prediction": "core",
    "regime": "core",
    "confidence": "core",
    "change": "core",
    "calibration": "core",
    "learning": "inference",
    "learned": "inference",
    "ratings": "inference",
    "plugins": "inference",
    "fusion": "inference",
    "fusiondata": "inference",  # Dataset Fusion: the unified knowledge substrate
    "dynamics": "inference",    # Dynamic Knowledge Management: temporal versions
    "worldstate": "inference",  # Knowledge Base for Simulation: pre-match state
    "knowledgemap": "inference",  # Phase C: lift engine outputs into the contract
    "simulation": "inference",
    "strategy": "inference",
    "vision": "inference",
    "scouting": "inference",  # Scout AI: similarity + transparent index
    "players": "knowledge",
    "coaches": "knowledge",
    "tactical": "knowledge",
    "narrative": "knowledge",
    "consensus": "knowledge",
    "memory": "knowledge",
    "causality": "knowledge",
    "explain": "knowledge",
    "profiling": "knowledge",
    "sources": "application",
    "db": "application",
}


def _fie_imports(path: pathlib.Path) -> set:
    """Names of fie submodules imported by the file (absolute or relative)."""
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:  # relative: from .x import / from ..x import
                if node.module:
                    found.add(node.module.split(".")[0])
                else:  # from . import x
                    found.update(alias.name.split(".")[0] for alias in node.names)
            elif node.module and node.module.startswith("fie"):
                parts = node.module.split(".")
                if len(parts) > 1:
                    found.add(parts[1])
                else:  # from fie import X — top-level re-exports (core surface)
                    found.add("events")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("fie."):
                    found.add(alias.name.split(".")[1])
    return found & set(MODULE_LAYER)


def _module_files():
    for path in sorted(SRC.glob("*.py")):
        if path.stem != "__init__":
            yield path.stem, path
    for path in sorted((SRC / "sources").glob("*.py")):
        yield "sources", path


def test_layer_map_is_complete():
    """Every engine module must be assigned to a layer (no unclassified code)."""
    names = {name for name, _ in _module_files()}
    unmapped = names - set(MODULE_LAYER)
    assert not unmapped, f"add these modules to the layer map: {sorted(unmapped)}"


def test_dependencies_point_down_never_up():
    violations = []
    for name, path in _module_files():
        layer = LAYERS[MODULE_LAYER[name]]
        for imported in _fie_imports(path):
            if imported == name:
                continue
            if LAYERS[MODULE_LAYER[imported]] > layer:
                violations.append(
                    f"{path.relative_to(SRC.parent.parent)}: {MODULE_LAYER[name]} "
                    f"module '{name}' imports {MODULE_LAYER[imported]} "
                    f"module '{imported}' (upward)"
                )
    assert not violations, "\n".join(violations)


def test_core_is_stdlib_only():
    """Core modules import nothing outside the standard library and Core."""
    import sys

    stdlib = set(sys.stdlib_module_names)
    for name, path in _module_files():
        if MODULE_LAYER[name] != "core":
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    assert root in stdlib or root == "fie", (
                        f"core module {name} imports third-party '{root}'"
                    )
            elif isinstance(node, ast.ImportFrom) and not node.level:
                root = (node.module or "").split(".")[0]
                assert root in stdlib or root in ("fie", ""), (
                    f"core module {name} imports third-party '{root}'"
                )


def test_plugins_respect_the_architecture():
    """Repo plugins may import only Core/Inference fie modules + stdlib."""
    if not PLUGINS_DIR.exists():
        return
    allowed_layers = {"core", "inference"}
    for path in sorted(PLUGINS_DIR.glob("*.py")):
        for imported in _fie_imports(path):
            assert MODULE_LAYER[imported] in allowed_layers, (
                f"plugin {path.name} imports {MODULE_LAYER[imported]} module "
                f"'{imported}' — plugins may only use Core/Inference"
            )
