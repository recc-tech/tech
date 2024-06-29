"""
Data definition.
"""

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Cue:
    id: str
    start: timedelta
    end: timedelta
    text: str
    confidence: float
