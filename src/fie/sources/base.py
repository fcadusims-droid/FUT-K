"""The abstract source interface (Section 4.1).

The whole point of this interface is that the real provider is a pluggable
detail: switching providers — or using a simulated feed for development — never
affects the rest of the system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Source(ABC):
    """A single public source of match information."""

    name: str
    base_trust: float  # prior reliability of this connector, 0..1

    @abstractmethod
    def stream(self, match_id):
        """Yield normalized ``Event`` objects for ``match_id``."""
        raise NotImplementedError
