"""Assign tracks to party-moment crates and compute mix compatibility.

Party moments (crate names sort in set order):

  odj_01_aquecimento   warm-up: lower energy, 85-108 BPM
  odj_02_subindo       building: mid energy, 100-120 BPM
  odj_03_pico          peak: high energy, 118-140 BPM
  odj_04_respiro       breathers: high vocal presence, any BPM

BPM compatibility uses tempo-ratio logic, not absolute difference: two
tracks lock when bpm_a * ratio lands within pitch-fader range (default 8%)
of bpm_b, for ratios 1:1 (straight), 2:1 / 1:2 (half/double time), and the
3:4 / 4:3 bridges (e.g. 96 BPM boom bap against 128 BPM club tempo).
Cross-genre pairs found via non-straight ratios are best mixed by phrase
(cut/echo-out on a phrase boundary) rather than long beat-matched blends.
"""

from __future__ import annotations

from dataclasses import dataclass

from open_djing.analysis.camelot import compatible_keys
from open_djing.analysis.models import TrackAnalysis

# Ratios under which two tempos can lock: straight, half/double, and the
# 3:4 bridge (e.g. 96 BPM boom bap against 128 BPM club tempo).
_RATIOS = (1.0, 2.0, 0.5, 0.75, 4 / 3)


def bpm_compatible(bpm_a: float, bpm_b: float, tolerance: float = 0.08) -> float | None:
    """Return the ratio that locks the two tempos, or None.

    A ratio r locks when |bpm_a * r - bpm_b| / bpm_b <= tolerance.
    Straight (1.0) is preferred, then half/double, then bridge ratios.
    """
    if bpm_a <= 0 or bpm_b <= 0:
        return None
    for ratio in _RATIOS:
        if abs(bpm_a * ratio - bpm_b) / bpm_b <= tolerance:
            return ratio
    return None


@dataclass(frozen=True, slots=True)
class CrateSpec:
    name: str
    description: str
    file_paths: tuple[str, ...]


def _moment(analysis: TrackAnalysis) -> str:
    """Classify a track into a party moment."""
    bpm = analysis.bpm
    # Normalize very fast tempos heard half-time (150 BPM trap ~ 75 BPM feel).
    felt_bpm = bpm / 2 if bpm >= 140 else bpm

    if analysis.vocal_presence >= 0.55 and analysis.energy <= 5:
        return "odj_04_respiro"
    if analysis.energy >= 7 and felt_bpm >= 118:
        return "odj_03_pico"
    if analysis.energy >= 5 or felt_bpm >= 105:
        return "odj_02_subindo"
    return "odj_01_aquecimento"


def build_crate_specs(analyses: list[TrackAnalysis]) -> list[CrateSpec]:
    """Group analyses into party-moment crate specs (only non-empty crates)."""
    descriptions = {
        "odj_01_aquecimento": "warm-up: low energy, open the room",
        "odj_02_subindo": "building: mid energy, fill the floor",
        "odj_03_pico": "peak time: high energy",
        "odj_04_respiro": "breathers: vocal moments, sing-along resets",
    }
    buckets: dict[str, list[str]] = {name: [] for name in descriptions}
    for analysis in analyses:
        buckets[_moment(analysis)].append(analysis.file_path)

    return [
        CrateSpec(name=name, description=descriptions[name], file_paths=tuple(sorted(files)))
        for name, files in buckets.items()
        if files
    ]


@dataclass(frozen=True, slots=True)
class MixCandidate:
    file_path: str
    bpm: float
    camelot: str | None
    ratio: float  # tempo ratio that locks it to the source track
    harmonic: bool  # True when keys are Camelot-compatible


def mix_candidates(
    source: TrackAnalysis,
    pool: list[TrackAnalysis],
    tolerance: float = 0.08,
) -> list[MixCandidate]:
    """Tracks from `pool` that can follow `source`, best first.

    Sort order: harmonic straight-tempo first, then harmonic bridges,
    then non-harmonic straight, then the rest — always excluding `source`.
    """
    ok_keys = compatible_keys(source.camelot)
    out: list[MixCandidate] = []
    for cand in pool:
        if cand.file_hash == source.file_hash:
            continue
        ratio = bpm_compatible(source.bpm, cand.bpm, tolerance)
        if ratio is None:
            continue
        out.append(
            MixCandidate(
                file_path=cand.file_path,
                bpm=cand.bpm,
                camelot=cand.camelot,
                ratio=ratio,
                harmonic=bool(cand.camelot and cand.camelot in ok_keys),
            )
        )

    def rank(c: MixCandidate) -> tuple[int, int, float]:
        straight = 0 if c.ratio == 1.0 else 1
        return (0 if c.harmonic else 1, straight, abs(1 - c.ratio))

    return sorted(out, key=rank)
