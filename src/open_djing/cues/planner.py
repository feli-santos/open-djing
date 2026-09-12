"""Turn a TrackAnalysis into a set of phrase-aligned hot cues.

Cue layout (hotcue pads 1-8, indices 0-7):

  pad 1  MIX-IN    first beat of the track (aligned start for mixing in)
  pad 2  32-IN     32 beats after mix-in (end of a typical intro phrase)
  pad 3  DROP      start of the highest-energy segment, snapped to the grid
  pad 4  VOX/BREAK start of the lowest-energy mid segment (breakdown)
  pad 7  OUT-32    32 beats before mix-out (start your exit blend here)
  pad 8  MIX-OUT   start of the outro segment, snapped to the grid

Pads 5-6 stay free for the DJ's own markers. All positions snap to the
nearest detected beat so cue-jumping stays on grid even when the track was
recorded by a live drummer.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass

from open_djing.analysis.models import TrackAnalysis

# Mixxx stores cue colors as 32-bit ARGB integers.
_ARGB = {
    "green": 0xFF32BE44,
    "blue": 0xFF0044FF,
    "red": 0xFFFF2200,
    "purple": 0xFFAA00FF,
    "orange": 0xFFFF8800,
    "yellow": 0xFFF8D200,
}


@dataclass(frozen=True, slots=True)
class PlannedCue:
    hotcue_index: int  # 0-based pad index
    label: str
    seconds: float
    color: int


@dataclass(frozen=True, slots=True)
class CuePlan:
    file_path: str
    file_hash: str
    cues: tuple[PlannedCue, ...]
    warnings: tuple[str, ...] = ()


def _snap_to_beat(seconds: float, beat_times: tuple[float, ...]) -> float:
    """Snap a timestamp to the nearest detected beat (identity if no beats)."""
    if not beat_times:
        return seconds
    i = bisect.bisect_left(beat_times, seconds)
    candidates = beat_times[max(0, i - 1) : i + 1]
    return min(candidates, key=lambda b: abs(b - seconds))


def plan_cues(analysis: TrackAnalysis) -> CuePlan:
    beats = analysis.beatgrid.beat_times
    warnings: list[str] = []
    cues: list[PlannedCue] = []

    if not beats:
        return CuePlan(
            file_path=analysis.file_path,
            file_hash=analysis.file_hash,
            cues=(),
            warnings=("no beatgrid detected — skipped",),
        )

    if not analysis.beatgrid.is_stable:
        warnings.append(
            f"variable tempo (confidence {analysis.beatgrid.confidence}) — "
            "cues snapped to detected beats; verify the grid in Mixxx"
        )

    # Pad 1: MIX-IN on the first beat.
    mix_in = beats[0]
    cues.append(PlannedCue(0, "MIX-IN", round(mix_in, 3), _ARGB["green"]))

    # Pad 2: 32 beats in (a full phrase), if the track is long enough.
    if len(beats) > 32:
        cues.append(PlannedCue(1, "32-IN", round(beats[32], 3), _ARGB["blue"]))

    segments = analysis.segments
    drop = next((s for s in segments if s.label == "drop"), None)
    if drop:
        t = _snap_to_beat(drop.start_seconds, beats)
        cues.append(PlannedCue(2, "DROP", round(t, 3), _ARGB["red"]))

    breakdown = next((s for s in segments if s.label == "breakdown"), None)
    if breakdown:
        t = _snap_to_beat(breakdown.start_seconds, beats)
        cues.append(PlannedCue(3, "BREAK", round(t, 3), _ARGB["purple"]))

    outro = next((s for s in reversed(segments) if s.label == "outro"), None)
    if outro:
        out_t = _snap_to_beat(outro.start_seconds, beats)
        # Pad 7: 32 beats before mix-out.
        i = bisect.bisect_left(beats, out_t)
        if i >= 32:
            cues.append(PlannedCue(6, "OUT-32", round(beats[i - 32], 3), _ARGB["orange"]))
        cues.append(PlannedCue(7, "MIX-OUT", round(out_t, 3), _ARGB["yellow"]))

    return CuePlan(
        file_path=analysis.file_path,
        file_hash=analysis.file_hash,
        cues=tuple(sorted(cues, key=lambda c: c.hotcue_index)),
        warnings=tuple(warnings),
    )
