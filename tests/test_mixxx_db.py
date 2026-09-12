"""MixxxDB adapter tests against the v39 schema fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_djing.mixxx import CueType, MixxxDB
from open_djing.mixxx.db import SchemaVersionError


def test_schema_version(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    assert db.schema_version() == 39
    assert db.check_schema() == 39


def test_missing_db_raises() -> None:
    db = MixxxDB(Path("/nonexistent/mixxxdb.sqlite"))
    with pytest.raises(FileNotFoundError):
        db.tracks()


def test_tracks_join_and_filtering(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    tracks = db.tracks()
    # fs_deleted row must be excluded
    assert len(tracks) == 3
    names = {t.display_name for t in tracks}
    assert "Jorge Ben - Taj Mahal (Edit)" in names
    jorge = next(t for t in tracks if t.artist == "Jorge Ben")
    assert jorge.bpm == 104.0
    assert jorge.key == "8A"
    assert jorge.location.endswith("Taj Mahal (Edit).mp3")


def test_track_by_id(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    track = db.track_by_id(2)
    assert track is not None
    assert track.artist == "MC Bin Laden"
    assert db.track_by_id(999) is None


def test_cues_and_position_conversion(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    cues = db.cues_for_track(1)
    assert len(cues) == 2
    hotcue = next(c for c in cues if c.type == CueType.HOTCUE)
    assert hotcue.label == "drop"
    assert hotcue.hotcue_index == 0
    # 2646000 interleaved samples / (44100 Hz * 2 ch) = 30.0 s
    assert hotcue.position_seconds(44100, 2) == pytest.approx(30.0)


def test_crates(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    crates = db.crates()
    assert len(crates) == 1
    assert crates[0].name == "02_subindo"
    assert crates[0].track_count == 2
    assert crates[0].locked is False


def test_stats(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    stats = db.stats()
    assert stats["tracks"] == 3
    assert stats["with_bpm"] == 3  # ghost track has bpm=0 and is excluded anyway
    assert ("funk", 2) in stats["genres"] or ("funk", 1) in stats["genres"]


def test_schema_out_of_range(fixture_db: Path) -> None:
    import sqlite3

    con = sqlite3.connect(fixture_db)
    con.execute("UPDATE settings SET value = '99' WHERE name = 'mixxx.schema.version'")
    con.commit()
    con.close()

    db = MixxxDB(fixture_db)
    with pytest.raises(SchemaVersionError):
        db.check_schema()


def test_music_directories(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    assert db.music_directories() == [Path("/music/dj")]
