"""Cue planner and writer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_djing.analysis.models import BeatgridResult, StructureSegment, TrackAnalysis
from open_djing.cues.planner import plan_cues
from open_djing.cues.writer import MixxxRunningError, write_cue_plan
from open_djing.mixxx import CueType, MixxxDB


def _analysis(
    *,
    file_path: str = "/music/dj/brasilidades/Jorge Ben - Taj Mahal (Edit).mp3",
    bpm: float = 104.0,
    confidence: float = 0.95,
    n_beats: int = 400,
) -> TrackAnalysis:
    beat = 60.0 / bpm
    beat_times = tuple(round(i * beat, 4) for i in range(n_beats))
    duration = n_beats * beat
    segments = (
        StructureSegment("intro", 0.0, 30.0),
        StructureSegment("verse", 30.0, 90.0),
        StructureSegment("drop", 90.0, 150.0),
        StructureSegment("breakdown", 150.0, 180.0),
        StructureSegment("outro", 180.0, duration),
    )
    return TrackAnalysis(
        file_path=file_path,
        file_hash="abc123",
        duration_seconds=duration,
        beatgrid=BeatgridResult(bpm, confidence, 0.0, beat_times),
        camelot="8A",
        energy=7,
        vocal_presence=0.4,
        segments=segments,
    )


def test_plan_layout_and_grid_snapping() -> None:
    plan = plan_cues(_analysis())
    by_label = {c.label: c for c in plan.cues}

    assert set(by_label) == {"MIX-IN", "32-IN", "DROP", "BREAK", "OUT-32", "MIX-OUT"}
    assert by_label["MIX-IN"].seconds == 0.0
    assert by_label["MIX-IN"].hotcue_index == 0
    # 32 beats at 104 BPM = 18.46s
    assert by_label["32-IN"].seconds == pytest.approx(32 * 60 / 104, abs=0.01)
    # Segment starts snap to the beatgrid
    beat = 60 / 104
    for label in ("DROP", "BREAK", "MIX-OUT"):
        assert by_label[label].seconds % beat == pytest.approx(0.0, abs=0.01)
    # OUT-32 is exactly 32 beats before MIX-OUT
    assert by_label["MIX-OUT"].seconds - by_label["OUT-32"].seconds == pytest.approx(
        32 * beat, abs=0.01
    )
    # pads: managed set only, 5-6 free
    assert {c.hotcue_index for c in plan.cues} == {0, 1, 2, 3, 6, 7}


def test_plan_variable_tempo_warns() -> None:
    plan = plan_cues(_analysis(confidence=0.5))
    assert any("variable tempo" in w for w in plan.warnings)


def test_plan_no_beats() -> None:
    analysis = _analysis()
    analysis = TrackAnalysis(
        **{
            **{
                f: getattr(analysis, f)
                for f in (
                    "file_path",
                    "file_hash",
                    "duration_seconds",
                    "camelot",
                    "energy",
                    "vocal_presence",
                    "segments",
                )
            },
            "beatgrid": BeatgridResult(0.0, 0.0, 0.0, ()),
        }
    )
    plan = plan_cues(analysis)
    assert plan.cues == ()
    assert plan.warnings


def test_writer_refuses_while_mixxx_running(fixture_db: Path) -> None:
    plan = plan_cues(_analysis())
    db = MixxxDB(fixture_db)
    with pytest.raises(MixxxRunningError):
        write_cue_plan(db, plan, mixxx_running_check=lambda: True)


def test_writer_inserts_and_respects_existing(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    plan = plan_cues(_analysis())
    report = write_cue_plan(db, plan, mixxx_running_check=lambda: False)

    # Track 1 already has a user hotcue on pad 1 (index 0): must be kept.
    assert report.track_id == 1
    assert 0 in report.skipped_pads
    assert report.written == len(plan.cues) - 1
    assert report.replaced == 0

    cues = db.cues_for_track(1)
    hotcues = [c for c in cues if c.type == CueType.HOTCUE]
    labels = {c.label for c in hotcues}
    assert "drop" in labels  # the user's original pad-1 cue survived
    assert "MIX-OUT" in labels

    # Second run without --overwrite: everything already set, nothing written.
    report2 = write_cue_plan(db, plan, mixxx_running_check=lambda: False)
    assert report2.written == 0
    assert len(report2.skipped_pads) == len(plan.cues)

    # With overwrite: replaces our pads (including the user's pad 1 — explicit choice).
    report3 = write_cue_plan(db, plan, overwrite=True, mixxx_running_check=lambda: False)
    assert report3.replaced == len(plan.cues)
    hotcues_after = [c for c in db.cues_for_track(1) if c.type == CueType.HOTCUE]
    assert {c.label for c in hotcues_after} >= {"MIX-IN", "MIX-OUT"}


def test_writer_unknown_track(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    plan = plan_cues(_analysis(file_path="/nowhere/unknown.mp3"))
    with pytest.raises(LookupError):
        write_cue_plan(db, plan, mixxx_running_check=lambda: False)


def test_position_sample_math(fixture_db: Path) -> None:
    db = MixxxDB(fixture_db)
    plan = plan_cues(_analysis())
    write_cue_plan(db, plan, mixxx_running_check=lambda: False)

    mix_out = next(
        c for c in db.cues_for_track(1) if c.type == CueType.HOTCUE and c.label == "MIX-OUT"
    )
    expected_seconds = next(c for c in plan.cues if c.label == "MIX-OUT").seconds
    assert mix_out.position_seconds(44100, 2) == pytest.approx(expected_seconds, abs=0.001)
