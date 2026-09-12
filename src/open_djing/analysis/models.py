"""Result types for the analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class BeatgridResult:
    bpm: float
    confidence: float  # 0..1 — low values flag variable-tempo (live drummers)
    first_beat_seconds: float
    beat_times: tuple[float, ...] = field(repr=False, default=())

    @property
    def is_stable(self) -> bool:
        """True when the grid is steady enough for long blends and sync."""
        return self.confidence >= 0.85


@dataclass(frozen=True, slots=True)
class StructureSegment:
    label: str  # intro | verse | chorus | drop | breakdown | outro
    start_seconds: float
    end_seconds: float

    @property
    def duration(self) -> float:
        return self.end_seconds - self.start_seconds


@dataclass(frozen=True, slots=True)
class TrackAnalysis:
    """Everything open-djing knows about one audio file."""

    file_path: str
    file_hash: str  # sha1 of file contents — cache key
    duration_seconds: float
    beatgrid: BeatgridResult
    camelot: str | None  # e.g. "8A"
    energy: int  # 1..10 heuristic
    vocal_presence: float  # 0..1 rough estimate
    segments: tuple[StructureSegment, ...]

    @property
    def bpm(self) -> float:
        return self.beatgrid.bpm
