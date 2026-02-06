"""
Output Level Enum

Defines the verbosity levels for tool observations.
This is orthogonal to the semantic content of the observation.

Design v2.0.1: Output Level vs Observation
- Observation (Semantic): WHAT information the tool returns
- Output Level (Engineering): HOW detailed the observation is formatted
- They are INDEPENDENT concerns
"""

from enum import Enum
from typing import Dict, Any


class OutputLevel(str, Enum):
    """
    Output verbosity level for tool observations.

    Controls the amount of detail returned to the LLM in the observation string.
    This is an ENGINEERING concern, not a semantic one.

    Levels:
        BRIEF: Minimal output (~10-50 tokens)
            - Just the key result or status
            - Examples: "Success", "Found 10 items", "Error: timeout"

        STANDARD: Balanced output (~100-500 tokens)
            - Summary + structured key-value pairs
            - Examples: "Success: Query completed. Rows: 100, Time: 23ms"

        FULL: Maximum detail (~1000+ tokens)
            - Complete data or artifact reference
            - Examples: Full JSON dataset, or "Stored as artifact_abc123"

    CRITICAL: OutputLevel is NOT Progressive Disclosure!
    - Progressive Disclosure applies to Skills loading (metadata → full → resources)
    - OutputLevel applies to Tool observations (BRIEF/STANDARD/FULL)
    """

    BRIEF = "brief"
    STANDARD = "standard"
    FULL = "full"

    @property
    def max_tokens(self) -> int:
        """Approximate maximum token count for this level."""
        return {
            self.BRIEF: 50,
            self.STANDARD: 500,
            self.FULL: 200000,  # Effectively unlimited, uses artifact storage
        }[self]

    @property
    def description(self) -> str:
        """Human-readable description."""
        return {
            self.BRIEF: "Minimal output - key result only",
            self.STANDARD: "Balanced output - summary with key details",
            self.FULL: "Complete output - full data or artifact reference",
        }[self]

    @classmethod
    def from_size(cls, data_size_bytes: int) -> "OutputLevel":
        """
        Determine appropriate output level based on data size.

        Args:
            data_size_bytes: Size of raw data in bytes

        Returns:
            Recommended OutputLevel
        """
        if data_size_bytes < 10_000:  # < 10KB
            return cls.FULL
        elif data_size_bytes < 1_000_000:  # < 1MB
            return cls.STANDARD
        else:
            # Large data always uses artifact storage
            return cls.FULL

    def should_use_artifact(self, data_size_bytes: int, threshold: int = 1_000_000) -> bool:
        """
        Check if data should be stored as artifact.

        Args:
            data_size_bytes: Size of raw data
            threshold: Threshold in bytes (default: 1MB)

        Returns:
            True if should use artifact storage
        """
        # FULL level with large data uses artifact
        return self == self.FULL and data_size_bytes >= threshold


__all__ = ["OutputLevel"]
