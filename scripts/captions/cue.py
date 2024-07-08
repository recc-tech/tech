"""
Data definition.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional


@dataclass(frozen=True)
class Cue:
    id: str
    start: timedelta
    end: timedelta
    text: str
    confidence: Optional[float]

    def with_text(self, new_text: str) -> Cue:
        return Cue(
            id=self.id,
            start=self.start,
            end=self.end,
            text=new_text,
            confidence=self.confidence,
        )
