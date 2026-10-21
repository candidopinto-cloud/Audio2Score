"""Shared data types passed between pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field

# Standard tuning, low to high: E2 A2 D3 G3 B3 E4
STANDARD_TUNING: tuple[int, ...] = (40, 45, 50, 55, 59, 64)


@dataclass
class NoteEvent:
    """One transcribed note. Times in seconds; pitch as MIDI number."""

    onset: float
    offset: float
    pitch: int
    velocity: int = 80
    voice: int | None = None  # 0 = bass, 1 = melody, 2+ = inner (set by voices stage)
    string: int | None = None  # 0 = low E ... 5 = high E (set by fretting stage)
    fret: int | None = None


@dataclass
class Transcription:
    """Everything known about a piece after processing."""

    notes: list[NoteEvent] = field(default_factory=list)
    tempo_bpm: float | None = None
    beats: list[float] = field(default_factory=list)  # beat times in seconds
    time_signature: tuple[int, int] = (4, 4)
    key: str | None = None
    tuning: tuple[int, ...] = STANDARD_TUNING
    capo: int = 0
