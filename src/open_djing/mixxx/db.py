"""Read-only adapter for mixxxdb.sqlite.

Write support arrives in M4 (auto-cues) behind explicit safety rails:
backup-first, Mixxx-closed check, and dry-run defaults. Until then this
module only ever opens the database in read-only mode (SQLite URI mode=ro),
so it is always safe — even while Mixxx is running.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict

from open_djing import paths
from open_djing.mixxx.models import Crate, CueInfo, CueType, Track

SUPPORTED_SCHEMA_VERSIONS = range(37, 41)  # tested against v39 (Mixxx 2.5)

_TRACK_QUERY = """
SELECT
    l.id, l.artist, l.title, l.album, l.genre, l.year,
    l.duration, l.bpm, l.key, l.rating, l.color,
    tl.location, tl.filename,
    l.samplerate, l.channels, l.datetime_added
FROM library l
JOIN track_locations tl ON l.location = tl.id
WHERE l.mixxx_deleted = 0 AND tl.fs_deleted = 0
"""


class SchemaVersionError(RuntimeError):
    """Raised when the Mixxx database schema is outside the tested range."""


class LibraryStats(TypedDict):
    tracks: int
    with_bpm: int
    genres: list[tuple[str, int]]


def _row_to_track(row: sqlite3.Row) -> Track:
    return Track(
        id=row["id"],
        artist=row["artist"],
        title=row["title"],
        album=row["album"],
        genre=row["genre"],
        year=row["year"],
        duration_seconds=row["duration"],
        bpm=row["bpm"],
        key=row["key"],
        rating=row["rating"],
        color=row["color"],
        location=row["location"],
        filename=row["filename"],
        samplerate=row["samplerate"],
        channels=row["channels"],
        datetime_added=row["datetime_added"],
    )


class MixxxDB:
    """Read-only access to the Mixxx library database."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or paths.mixxx_db_path()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Mixxx database not found at {self.db_path}. Launch Mixxx once to create it."
            )
        con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            yield con
        finally:
            con.close()

    def schema_version(self) -> int:
        with self._connect() as con:
            row = con.execute(
                "SELECT value FROM settings WHERE name = 'mixxx.schema.version'"
            ).fetchone()
        if row is None:
            raise SchemaVersionError("No schema version found in settings table.")
        return int(row["value"])

    def check_schema(self) -> int:
        """Return the schema version, raising if it's outside the tested range."""
        version = self.schema_version()
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise SchemaVersionError(
                f"Mixxx schema v{version} is outside the tested range "
                f"[{SUPPORTED_SCHEMA_VERSIONS.start}, {SUPPORTED_SCHEMA_VERSIONS.stop - 1}]. "
                "Update open-djing (or open an issue) before writing anything."
            )
        return version

    def music_directories(self) -> list[Path]:
        with self._connect() as con:
            rows = con.execute("SELECT directory FROM directories").fetchall()
        return [Path(r["directory"]) for r in rows]

    def tracks(self) -> list[Track]:
        with self._connect() as con:
            rows = con.execute(_TRACK_QUERY).fetchall()
        return [_row_to_track(r) for r in rows]

    def track_by_id(self, track_id: int) -> Track | None:
        with self._connect() as con:
            row = con.execute(_TRACK_QUERY + " AND l.id = ?", (track_id,)).fetchone()
        return _row_to_track(row) if row else None

    def cues_for_track(self, track_id: int) -> list[CueInfo]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, track_id, type, position, length, hotcue, label, color"
                " FROM cues WHERE track_id = ?",
                (track_id,),
            ).fetchall()
        return [
            CueInfo(
                id=r["id"],
                track_id=r["track_id"],
                type=CueType(r["type"])
                if r["type"] in CueType._value2member_map_
                else CueType.INVALID,
                position_samples=r["position"],
                length_samples=r["length"],
                hotcue_index=r["hotcue"],
                label=r["label"],
                color=r["color"],
            )
            for r in rows
        ]

    def crates(self) -> list[Crate]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT c.id, c.name, c.locked, count(ct.track_id) AS n"
                " FROM crates c LEFT JOIN crate_tracks ct ON ct.crate_id = c.id"
                " GROUP BY c.id ORDER BY c.name"
            ).fetchall()
        return [
            Crate(id=r["id"], name=r["name"], track_count=r["n"], locked=bool(r["locked"]))
            for r in rows
        ]

    def stats(self) -> LibraryStats:
        """Library-wide numbers for `odj library`."""
        with self._connect() as con:
            n_tracks = con.execute(
                "SELECT count(*) FROM library l JOIN track_locations tl ON l.location = tl.id"
                " WHERE l.mixxx_deleted = 0 AND tl.fs_deleted = 0"
            ).fetchone()[0]
            n_analyzed = con.execute(
                "SELECT count(*) FROM library WHERE mixxx_deleted = 0 AND bpm > 0"
            ).fetchone()[0]
            genres = con.execute(
                "SELECT genre, count(*) AS n FROM library"
                " WHERE mixxx_deleted = 0 AND genre IS NOT NULL AND genre != ''"
                " GROUP BY genre ORDER BY n DESC LIMIT 10"
            ).fetchall()
        return {
            "tracks": n_tracks,
            "with_bpm": n_analyzed,
            "genres": [(r["genre"], r["n"]) for r in genres],
        }
