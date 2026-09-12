"""Sidecar cache for analysis results (~/.open-djing/analysis.sqlite).

Keyed by content hash, so renames/moves don't trigger re-analysis and the
Mixxx database stays untouched until an explicit write command.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from open_djing import paths
from open_djing.analysis.models import BeatgridResult, StructureSegment, TrackAnalysis

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis (
    file_hash TEXT PRIMARY KEY,
    file_path TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE INDEX IF NOT EXISTS idx_analysis_path ON analysis (file_path);
"""


class AnalysisCache:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or (paths.odj_data_dir() / "analysis.sqlite")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def get(self, file_hash: str) -> TrackAnalysis | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT payload FROM analysis WHERE file_hash = ?", (file_hash,)
            ).fetchone()
        if row is None:
            return None
        return _from_json(row["payload"])

    def get_by_path(self, file_path: str) -> TrackAnalysis | None:
        """Latest analysis recorded for a path (hash may be stale if file changed)."""
        with self._connect() as con:
            row = con.execute(
                "SELECT payload FROM analysis WHERE file_path = ? ORDER BY created_at DESC LIMIT 1",
                (file_path,),
            ).fetchone()
        return _from_json(row["payload"]) if row else None

    def put(self, analysis: TrackAnalysis) -> None:
        payload = json.dumps(asdict(analysis))
        with self._connect() as con:
            con.execute(
                "INSERT INTO analysis (file_hash, file_path, payload) VALUES (?, ?, ?)"
                " ON CONFLICT(file_hash) DO UPDATE SET"
                " file_path = excluded.file_path, payload = excluded.payload",
                (analysis.file_hash, analysis.file_path, payload),
            )
            con.commit()

    def all(self) -> list[TrackAnalysis]:
        with self._connect() as con:
            rows = con.execute("SELECT payload FROM analysis ORDER BY file_path").fetchall()
        return [_from_json(r["payload"]) for r in rows]

    def count(self) -> int:
        with self._connect() as con:
            return con.execute("SELECT count(*) FROM analysis").fetchone()[0]


def _from_json(payload: str) -> TrackAnalysis:
    data = json.loads(payload)
    beatgrid = BeatgridResult(
        bpm=data["beatgrid"]["bpm"],
        confidence=data["beatgrid"]["confidence"],
        first_beat_seconds=data["beatgrid"]["first_beat_seconds"],
        beat_times=tuple(data["beatgrid"]["beat_times"]),
    )
    segments = tuple(
        StructureSegment(s["label"], s["start_seconds"], s["end_seconds"]) for s in data["segments"]
    )
    return TrackAnalysis(
        file_path=data["file_path"],
        file_hash=data["file_hash"],
        duration_seconds=data["duration_seconds"],
        beatgrid=beatgrid,
        camelot=data["camelot"],
        energy=data["energy"],
        vocal_presence=data["vocal_presence"],
        segments=segments,
    )
