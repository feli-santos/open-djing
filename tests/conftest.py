"""Shared fixtures: build a disposable mixxxdb from the real v39 schema dump."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent / "fixtures" / "mixxx_schema_v39.sql"


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    """A mixxxdb.sqlite with the real Mixxx 2.5 schema and a few seeded rows."""
    db_path = tmp_path / "mixxxdb.sqlite"
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA_PATH.read_text())

    con.execute("INSERT INTO settings (name, value) VALUES ('mixxx.schema.version', '39')")
    con.execute("INSERT INTO directories (directory) VALUES ('/music/dj')")

    locations = [
        # (id, location, filename, directory, filesize, fs_deleted, needs_verification)
        (
            1,
            "/music/dj/brasilidades/Jorge Ben - Taj Mahal (Edit).mp3",
            "Jorge Ben - Taj Mahal (Edit).mp3",
            "/music/dj/brasilidades",
            9_000_000,
            0,
            0,
        ),
        (
            2,
            "/music/dj/funk/MC Bin Laden - Bololo Haha (VIP).mp3",
            "MC Bin Laden - Bololo Haha (VIP).mp3",
            "/music/dj/funk",
            7_000_000,
            0,
            0,
        ),
        (
            3,
            "/music/dj/hiphop/Racionais - Vida Loka (Instrumental).mp3",
            "Racionais - Vida Loka (Instrumental).mp3",
            "/music/dj/hiphop",
            8_000_000,
            0,
            0,
        ),
        # deleted-on-disk file: must be filtered out everywhere
        (4, "/music/dj/_inbox/ghost.mp3", "ghost.mp3", "/music/dj/_inbox", 1, 1, 0),
    ]
    con.executemany(
        "INSERT INTO track_locations (id, location, filename, directory, filesize,"
        " fs_deleted, needs_verification) VALUES (?, ?, ?, ?, ?, ?, ?)",
        locations,
    )

    tracks = [
        # (id, artist, title, genre, location_fk, duration, bpm, key, samplerate,
        #  channels, mixxx_deleted, rating, color, datetime_added)
        (
            1,
            "Jorge Ben",
            "Taj Mahal (Edit)",
            "brasilidades",
            1,
            245.0,
            104.0,
            "8A",
            44100,
            2,
            0,
            4,
            None,
            "2026-09-11 20:00:00",
        ),
        (
            2,
            "MC Bin Laden",
            "Bololo Haha (VIP)",
            "funk",
            2,
            150.0,
            130.0,
            "5A",
            44100,
            2,
            0,
            0,
            None,
            "2026-09-11 20:01:00",
        ),
        (
            3,
            "Racionais MC's",
            "Vida Loka (Instrumental)",
            "hiphop",
            3,
            210.0,
            90.0,
            "4B",
            44100,
            2,
            0,
            5,
            None,
            "2026-09-11 20:02:00",
        ),
        (
            4,
            "Ghost",
            "Deleted",
            "funk",
            4,
            100.0,
            0.0,
            None,
            44100,
            2,
            0,
            0,
            None,
            "2026-09-11 20:03:00",
        ),
    ]
    con.executemany(
        "INSERT INTO library (id, artist, title, genre, location, duration, bpm, key,"
        " samplerate, channels, mixxx_deleted, rating, color, datetime_added)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        tracks,
    )

    # One hotcue + a main cue on track 1. Position: 30s * 44100 Hz * 2 ch.
    con.execute(
        "INSERT INTO cues (track_id, type, position, length, hotcue, label, color)"
        " VALUES (1, 1, 2646000, 0, 0, 'drop', 4294901760)"
    )
    con.execute(
        "INSERT INTO cues (track_id, type, position, length, hotcue, label, color)"
        " VALUES (1, 2, 0, 0, -1, '', 4294901760)"
    )

    # Crates
    con.execute("INSERT INTO crates (id, name, locked) VALUES (1, '02_subindo', 0)")
    con.executemany(
        "INSERT INTO crate_tracks (crate_id, track_id) VALUES (?, ?)",
        [(1, 1), (1, 2)],
    )

    con.commit()
    con.close()
    return db_path
