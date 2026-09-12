"""Crate builder + writer tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_djing.analysis.models import BeatgridResult, StructureSegment, TrackAnalysis
from open_djing.crates.builder import bpm_compatible, build_crate_specs, mix_candidates
from open_djing.crates.writer import write_crates
from open_djing.cues.writer import MixxxRunningError
from open_djing.mixxx import MixxxDB


def _analysis(
    path: str,
    bpm: float,
    energy: int,
    vocal: float = 0.3,
    camelot: str | None = "8A",
) -> TrackAnalysis:
    return TrackAnalysis(
        file_path=path,
        file_hash=f"hash-{path}",
        duration_seconds=200.0,
        beatgrid=BeatgridResult(bpm, 0.9, 0.0, (0.0, 60 / bpm)),
        camelot=camelot,
        energy=energy,
        vocal_presence=vocal,
        segments=(StructureSegment("body", 0.0, 200.0),),
    )


class TestBpmCompatible:
    def test_straight(self) -> None:
        assert bpm_compatible(120, 124) == 1.0
        assert bpm_compatible(120, 132) is None  # 10% off, out of 8% tolerance

    def test_half_double_time(self) -> None:
        # 90 hiphop -> 175 trap/DnB territory: 90*2=180, within 8% of 175
        assert bpm_compatible(90, 175) == 2.0
        assert bpm_compatible(175, 90) == 0.5

    def test_bridge_ratios(self) -> None:
        # 96 boom bap * 4/3 = 128 club tempo
        assert bpm_compatible(96, 128) == pytest.approx(4 / 3)
        assert bpm_compatible(128, 96) == 0.75

    def test_invalid(self) -> None:
        assert bpm_compatible(0, 120) is None
        assert bpm_compatible(120, -5) is None


class TestPartyMoments:
    def test_buckets(self) -> None:
        analyses = [
            _analysis("/m/warmup.mp3", bpm=95, energy=3),
            _analysis("/m/building.mp3", bpm=110, energy=6),
            _analysis("/m/peak.mp3", bpm=130, energy=9),
            _analysis("/m/singalong.mp3", bpm=100, energy=4, vocal=0.7),
            # 150 trap felt as 75: high energy but not "pico" felt-bpm
            _analysis("/m/trap.mp3", bpm=150, energy=8),
        ]
        specs = {s.name: s for s in build_crate_specs(analyses)}

        assert "/m/warmup.mp3" in specs["odj_01_aquecimento"].file_paths
        assert "/m/building.mp3" in specs["odj_02_subindo"].file_paths
        assert "/m/peak.mp3" in specs["odj_03_pico"].file_paths
        assert "/m/singalong.mp3" in specs["odj_04_respiro"].file_paths
        assert "/m/trap.mp3" in specs["odj_02_subindo"].file_paths

    def test_empty_crates_omitted(self) -> None:
        specs = build_crate_specs([_analysis("/m/a.mp3", bpm=95, energy=2)])
        assert [s.name for s in specs] == ["odj_01_aquecimento"]


class TestMixCandidates:
    def test_ranking_harmonic_straight_first(self) -> None:
        source = _analysis("/m/src.mp3", bpm=104, energy=6, camelot="8A")
        pool = [
            source,
            _analysis("/m/harmonic_straight.mp3", bpm=106, energy=6, camelot="9A"),
            _analysis("/m/clash_straight.mp3", bpm=104, energy=6, camelot="3B"),
            _analysis("/m/harmonic_bridge.mp3", bpm=138, energy=7, camelot="8B"),
            _analysis("/m/incompatible.mp3", bpm=999, energy=5),
        ]
        result = mix_candidates(source, pool)
        names = [Path(c.file_path).name for c in result]

        assert "incompatible.mp3" not in names
        assert "src.mp3" not in names  # source excluded
        assert names[0] == "harmonic_straight.mp3"
        # harmonic bridge beats non-harmonic straight? No: harmonic group first,
        # inside it straight beats bridge; then non-harmonic.
        assert names.index("harmonic_bridge.mp3") < names.index("clash_straight.mp3")


class TestCrateWriter:
    def test_write_and_rebuild_idempotent(self, fixture_db: Path) -> None:
        db = MixxxDB(fixture_db)
        specs = build_crate_specs(
            [
                _analysis(
                    "/music/dj/brasilidades/Jorge Ben - Taj Mahal (Edit).mp3",
                    bpm=104,
                    energy=6,
                ),
                _analysis("/music/dj/funk/MC Bin Laden - Bololo Haha (VIP).mp3", bpm=130, energy=9),
                _analysis("/music/dj/not-in-library.mp3", bpm=100, energy=6),
            ]
        )
        reports = write_crates(db, specs, mixxx_running_check=lambda: False)

        by_name = {r.crate_name: r for r in reports}
        assert by_name["odj_03_pico"].track_count == 1
        missing_all = [m for r in reports for m in r.missing_files]
        assert "/music/dj/not-in-library.mp3" in missing_all

        # Rebuild: same result, no duplicates.
        reports2 = write_crates(db, specs, mixxx_running_check=lambda: False)
        assert {r.crate_name: r.track_count for r in reports2} == {
            r.crate_name: r.track_count for r in reports
        }

        # User crate untouched.
        crate_names = {c.name for c in db.crates()}
        assert "02_subindo" in crate_names

    def test_refuses_while_running(self, fixture_db: Path) -> None:
        db = MixxxDB(fixture_db)
        specs = build_crate_specs([_analysis("/m/a.mp3", bpm=100, energy=5)])
        with pytest.raises(MixxxRunningError):
            write_crates(db, specs, mixxx_running_check=lambda: True)

    def test_refuses_unmanaged_prefix(self, fixture_db: Path) -> None:
        from open_djing.crates.builder import CrateSpec

        db = MixxxDB(fixture_db)
        with pytest.raises(ValueError, match="odj_"):
            write_crates(
                db,
                [CrateSpec("user_crate", "nope", ())],
                mixxx_running_check=lambda: False,
            )
