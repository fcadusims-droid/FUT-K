"""Football Intelligence Engine (FIE).

One module per section of ``docs/design/football_intelligence_engine.md``. Everything here is
standard-library only; test-time dependencies (pytest, hypothesis, numpy) live in
the ``[dev]`` extra and never leak into ``src/fie``.
"""

from .events import Event, State
from .prediction import Params

__all__ = ["Event", "State", "Params"]
