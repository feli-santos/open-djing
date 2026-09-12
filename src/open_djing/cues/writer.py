"""Write planned hot cues into mixxxdb.sqlite — carefully.

Safety rails, in order:
1. Refuse to run while Mixxx is running.
2. Refuse unknown schema versions (MixxxDB.check_schema).
3. Snapshot the database (SQLite backup API) before the first change.
4. Only touch `cues` rows with our hotcue indices; never rewrite the table.

Position math: Mixxx cue positions are interleaved samples —
seconds * samplerate * channels.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from open_djing.cues.planner import CuePlan
from open_djing.mixxx.db import MixxxDB
from open_djing.mixxx.models import CueType, Track


class MixxxRunningError(RuntimeError):
    """Raised when a write is attempted while Mixxx is open."""


@dataclass(frozen=True, slots=True)
class WriteReport:
    track_id: int
    written: int
    replaced: int
    skipped_pads: tuple[int, ...]  # pads left alone (user already set them)


def _track_by_location(db: MixxxDB, location: str) -> Track | None:
    for track in db.tracks():
        if track.location == location:
            return track
    return None


def write_cue_plan(
    db: MixxxDB,
    plan: CuePlan,
    *,
    overwrite: bool = False,
    mixxx_running_check=None,
) -> WriteReport:
    """Apply one CuePlan to the Mixxx database.

    `mixxx_running_check` is injectable for tests; defaults to the real check.
    """
    if mixxx_running_check is None:
        from open_djing.cli import _mixxx_is_running

        mixxx_running_check = _mixxx_is_running
    if mixxx_running_check():
        raise MixxxRunningError("Mixxx is running — close it before writing cues.")

    db.check_schema()

    track = _track_by_location(db, plan.file_path)
    if track is None:
        raise LookupError(
            f"Track not in Mixxx library: {plan.file_path}. Rescan the library in Mixxx first."
        )
    if not track.samplerate or not track.channels:
        raise ValueError(f"Track {track.id} missing samplerate/channels; reanalyze in Mixxx.")

    con = sqlite3.connect(db.db_path)
    con.row_factory = sqlite3.Row
    try:
        existing = {
            row["hotcue"]: row["id"]
            for row in con.execute(
                "SELECT id, hotcue FROM cues WHERE track_id = ? AND type = ? AND hotcue >= 0",
                (track.id, int(CueType.HOTCUE)),
            )
        }

        written = replaced = 0
        skipped: list[int] = []
        for cue in plan.cues:
            position = round(cue.seconds * track.samplerate * track.channels)
            if cue.hotcue_index in existing:
                if not overwrite:
                    skipped.append(cue.hotcue_index)
                    continue
                con.execute(
                    "UPDATE cues SET position = ?, label = ?, color = ? WHERE id = ?",
                    (position, cue.label, cue.color, existing[cue.hotcue_index]),
                )
                replaced += 1
            else:
                con.execute(
                    "INSERT INTO cues (track_id, type, position, length, hotcue, label, color)"
                    " VALUES (?, ?, ?, 0, ?, ?, ?)",
                    (
                        track.id,
                        int(CueType.HOTCUE),
                        position,
                        cue.hotcue_index,
                        cue.label,
                        cue.color,
                    ),
                )
                written += 1
        con.commit()
    finally:
        con.close()

    return WriteReport(
        track_id=track.id,
        written=written,
        replaced=replaced,
        skipped_pads=tuple(skipped),
    )


def backup_before_write(db_path: Path, backups_dir: Path) -> Path:
    """Snapshot the DB via the SQLite backup API. Returns the backup path."""
    from datetime import UTC, datetime

    backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = backups_dir / f"mixxxdb-precue-{stamp}.sqlite"
    src = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    return dest
