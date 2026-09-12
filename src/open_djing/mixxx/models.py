"""Typed views over Mixxx database rows.

Schema reference: tests/fixtures/mixxx_schema_v39.sql (Mixxx 2.5, schema v39).
Note: some foreign keys in the live schema reference "library_old" — an
artifact of Mixxx's own migrations. SQLite stores FK clauses as text and does
not enforce them by default, so joins against `library` work as expected.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class CueType(IntEnum):
    """Cue types as defined in Mixxx (src/track/cue.h)."""

    INVALID = 0
    HOTCUE = 1
    MAIN_CUE = 2
    BEAT = 3
    LOOP = 4
    JUMP = 5
    INTRO = 6
    OUTRO = 7
    N60DB_SOUND = 8  # first/last audible sound markers


@dataclass(frozen=True, slots=True)
class Track:
    """A playable track: `library` row joined with its `track_locations` row."""

    id: int
    artist: str | None
    title: str | None
    album: str | None
    genre: str | None
    year: str | None
    duration_seconds: float | None
    bpm: float | None
    key: str | None  # textual key as Mixxx displays it (e.g. "8A", "Am", "C")
    rating: int | None
    color: int | None
    location: str  # absolute file path
    filename: str
    samplerate: int | None
    channels: int | None
    datetime_added: str | None

    @property
    def display_name(self) -> str:
        artist = (self.artist or "").strip()
        title = (self.title or "").strip()
        if artist and title:
            return f"{artist} - {title}"
        return title or artist or self.filename


@dataclass(frozen=True, slots=True)
class CueInfo:
    """A row from `cues`. Positions are raw interleaved samples."""

    id: int
    track_id: int
    type: CueType
    position_samples: int  # -1 means unset
    length_samples: int
    hotcue_index: int  # -1 for non-hotcue cues
    label: str
    color: int

    def position_seconds(self, samplerate: int, channels: int = 2) -> float | None:
        """Convert the raw sample position to seconds.

        Mixxx stores cue positions in interleaved samples, i.e. frames * channels.
        """
        if self.position_samples < 0 or not samplerate or not channels:
            return None
        return self.position_samples / (samplerate * channels)


@dataclass(frozen=True, slots=True)
class Crate:
    id: int
    name: str
    track_count: int
    locked: bool
