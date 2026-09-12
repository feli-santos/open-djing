"""Audio analysis: beatgrid, key (Camelot), structure, and energy."""

from open_djing.analysis.camelot import CamelotKey, camelot_from_key_name, compatible_keys
from open_djing.analysis.models import BeatgridResult, StructureSegment, TrackAnalysis

__all__ = [
    "BeatgridResult",
    "CamelotKey",
    "StructureSegment",
    "TrackAnalysis",
    "camelot_from_key_name",
    "compatible_keys",
]
