"""Write crate specs into mixxxdb.sqlite with the same rails as the cue writer.

Only crates whose names start with "odj_" are ever touched: ours are rebuilt
idempotently, user-created crates are never modified.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from open_djing.crates.builder import CrateSpec
from open_djing.cues.writer import MixxxRunningError
from open_djing.mixxx.db import MixxxDB

MANAGED_PREFIX = "odj_"


@dataclass(frozen=True, slots=True)
class CrateWriteReport:
    crate_name: str
    track_count: int
    missing_files: tuple[str, ...]  # analyzed files not found in Mixxx library


def write_crates(
    db: MixxxDB,
    specs: list[CrateSpec],
    *,
    mixxx_running_check=None,
) -> list[CrateWriteReport]:
    if mixxx_running_check is None:
        from open_djing.cli import _mixxx_is_running

        mixxx_running_check = _mixxx_is_running
    if mixxx_running_check():
        raise MixxxRunningError("Mixxx is running — close it before writing crates.")

    db.check_schema()

    location_to_id = {t.location: t.id for t in db.tracks()}

    reports: list[CrateWriteReport] = []
    con = sqlite3.connect(db.db_path)
    try:
        for spec in specs:
            if not spec.name.startswith(MANAGED_PREFIX):
                raise ValueError(
                    f"Refusing to manage crate without {MANAGED_PREFIX!r} prefix: {spec.name}"
                )

            row = con.execute("SELECT id FROM crates WHERE name = ?", (spec.name,)).fetchone()
            if row:
                crate_id = row[0]
                con.execute("DELETE FROM crate_tracks WHERE crate_id = ?", (crate_id,))
            else:
                cur = con.execute("INSERT INTO crates (name) VALUES (?)", (spec.name,))
                crate_id = cur.lastrowid

            track_ids, missing = [], []
            for path in spec.file_paths:
                tid = location_to_id.get(path)
                if tid is None:
                    missing.append(path)
                else:
                    track_ids.append(tid)

            con.executemany(
                "INSERT OR IGNORE INTO crate_tracks (crate_id, track_id) VALUES (?, ?)",
                [(crate_id, tid) for tid in track_ids],
            )
            con.execute("UPDATE crates SET count = ? WHERE id = ?", (len(track_ids), crate_id))
            reports.append(
                CrateWriteReport(
                    crate_name=spec.name,
                    track_count=len(track_ids),
                    missing_files=tuple(missing),
                )
            )
        con.commit()
    finally:
        con.close()
    return reports
