"""Audio analysis engine built on librosa.

Heavy imports (librosa/numpy) are deferred into functions so the CLI stays
fast when analysis extras are not installed.

Honesty notes:
- BPM confidence is derived from inter-beat-interval variance. Live drummers
  (classic brasilidades) legitimately produce low confidence — that is a
  feature, not noise: those tracks need manual-grid practice.
- Key detection uses chroma + Krumhansl-Schmuckler profiles. Good, not
  perfect; Mixxx's own analyzer may disagree on relative keys.
- Structure labels (intro/drop/...) are energy heuristics over agglomerative
  segmentation, not ground truth.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from open_djing.analysis.camelot import camelot_from_key_name
from open_djing.analysis.models import BeatgridResult, StructureSegment, TrackAnalysis

AUDIO_EXTENSIONS = {".mp3", ".flac", ".wav", ".aiff", ".aif", ".m4a", ".ogg"}

# Krumhansl-Schmuckler key profiles
_MAJOR_PROFILE = (6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88)
_MINOR_PROFILE = (6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17)
_PITCH_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def file_sha1(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def iter_audio_files(root: Path) -> list[Path]:
    """Audio files under `root`, skipping hidden files, sorted for stable runs."""
    if root.is_file():
        return [root] if root.suffix.lower() in AUDIO_EXTENSIONS else []
    return sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and not p.name.startswith(".")
    )


def estimate_key(chroma_mean) -> str | None:
    """Correlate a mean chroma vector against major/minor profiles.

    Returns a musical key name like "Am" or "C", or None on degenerate input.
    """
    import numpy as np

    chroma = np.asarray(chroma_mean, dtype=float)
    if chroma.shape != (12,) or not np.isfinite(chroma).all() or chroma.std() == 0:
        return None

    best_score, best_name = -2.0, None
    for shift in range(12):
        rolled = np.roll(chroma, -shift)
        for profile, suffix in ((_MAJOR_PROFILE, ""), (_MINOR_PROFILE, "m")):
            score = float(np.corrcoef(rolled, profile)[0, 1])
            if score > best_score:
                best_score, best_name = score, f"{_PITCH_NAMES[shift]}{suffix}"
    return best_name


def _beatgrid(y, sr) -> BeatgridResult:
    import librosa
    import numpy as np

    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, trim=False)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])

    if len(beat_times) >= 3:
        intervals = np.diff(beat_times)
        # Coefficient of variation of inter-beat intervals -> confidence.
        cv = float(np.std(intervals) / np.mean(intervals)) if np.mean(intervals) > 0 else 1.0
        confidence = max(0.0, min(1.0, 1.0 - cv * 4.0))
        first_beat = float(beat_times[0])
    else:
        confidence, first_beat = 0.0, 0.0

    return BeatgridResult(
        bpm=round(bpm, 2),
        confidence=round(confidence, 3),
        first_beat_seconds=round(first_beat, 4),
        beat_times=tuple(round(float(t), 4) for t in beat_times),
    )


def _energy_and_vocals(y, sr) -> tuple[int, float]:
    import librosa
    import numpy as np

    rms = librosa.feature.rms(y=y)[0]
    loudness = float(np.percentile(rms, 75))
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    density = float(np.mean(onset_env))

    # Map loudness (~0..0.35 typical) and onset density (~0..8 typical) to 1..10.
    raw = 6.0 * min(loudness / 0.30, 1.0) + 4.0 * min(density / 6.0, 1.0)
    energy = int(max(1, min(10, round(raw))))

    # Rough vocal presence: harmonic energy share inside the voice band.
    harmonic = librosa.effects.harmonic(y)
    spec = np.abs(librosa.stft(harmonic))
    freqs = librosa.fft_frequencies(sr=sr)
    voice_band = (freqs >= 200) & (freqs <= 4000)
    total = float(spec.sum()) or 1.0
    vocal = float(spec[voice_band].sum()) / total
    return energy, round(min(1.0, vocal), 3)


def _segments(y, sr, duration: float) -> tuple[StructureSegment, ...]:
    import librosa
    import numpy as np

    n_target = int(max(4, min(8, duration // 30)))
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    features = np.vstack([chroma, mfcc])
    if features.shape[1] < n_target:
        return (StructureSegment("body", 0.0, round(duration, 2)),)

    boundaries = librosa.segment.agglomerative(features, n_target)
    times = librosa.frames_to_time(boundaries, sr=sr)
    edges = [0.0, *[float(t) for t in times[1:]], duration]

    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.times_like(rms, sr=sr)

    def seg_rms(a: float, b: float) -> float:
        mask = (rms_times >= a) & (rms_times < b)
        return float(rms[mask].mean()) if mask.any() else 0.0

    spans = [
        (edges[i], edges[i + 1]) for i in range(len(edges) - 1) if edges[i + 1] - edges[i] > 1.0
    ]
    if not spans:
        return (StructureSegment("body", 0.0, round(duration, 2)),)

    energies = [seg_rms(a, b) for a, b in spans]
    hi, lo = max(energies), min(energies)

    segments: list[StructureSegment] = []
    for i, ((a, b), e) in enumerate(zip(spans, energies, strict=True)):
        if i == 0:
            label = "intro"
        elif i == len(spans) - 1:
            label = "outro"
        elif e == hi:
            label = "drop"
        elif e == lo:
            label = "breakdown"
        else:
            label = "verse"
        segments.append(StructureSegment(label, round(a, 2), round(b, 2)))
    return tuple(segments)


def analyze_file(path: Path) -> TrackAnalysis:
    """Full analysis of one audio file. Raises ImportError without analysis extras."""
    import librosa

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    duration = float(len(y)) / sr

    beatgrid = _beatgrid(y, sr)
    chroma_mean = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    key_name = estimate_key(chroma_mean)
    camelot = camelot_from_key_name(key_name)
    energy, vocal = _energy_and_vocals(y, sr)
    segments = _segments(y, sr, duration)

    return TrackAnalysis(
        file_path=str(path),
        file_hash=file_sha1(path),
        duration_seconds=round(duration, 2),
        beatgrid=beatgrid,
        camelot=str(camelot) if camelot else None,
        energy=energy,
        vocal_presence=vocal,
        segments=segments,
    )
