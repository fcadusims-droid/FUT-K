"""Layer 1 — Knowledge Acquisition (Section 4.1).

Each connector turns a public source into the one normalized ``Event`` format, so
the rest of the system never needs to know where a piece of information came from.
"""

from .base import Source
from .statsbomb import StatsBombSource

__all__ = ["Source", "StatsBombSource"]
