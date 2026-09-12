"""Camelot wheel: harmonic-mixing arithmetic.

The wheel maps musical keys to positions 1-12, with suffix A (minor) or
B (major). Compatible transitions: same slot, +/-1 slot (same letter), or the
relative major/minor (same number, letter swap). Energy boost: +2 slots.
"""

from __future__ import annotations

from dataclasses import dataclass

# Canonical name -> Camelot code. Includes enharmonic spellings.
_KEY_TO_CAMELOT: dict[str, str] = {
    # Minor (A ring)
    "abm": "1A",
    "g#m": "1A",
    "ebm": "2A",
    "d#m": "2A",
    "bbm": "3A",
    "a#m": "3A",
    "fm": "4A",
    "cm": "5A",
    "gm": "6A",
    "dm": "7A",
    "am": "8A",
    "em": "9A",
    "bm": "10A",
    "f#m": "11A",
    "gbm": "11A",
    "dbm": "12A",
    "c#m": "12A",
    # Major (B ring)
    "b": "1B",
    "cb": "1B",
    "f#": "2B",
    "gb": "2B",
    "db": "3B",
    "c#": "3B",
    "ab": "4B",
    "g#": "4B",
    "eb": "5B",
    "d#": "5B",
    "bb": "6B",
    "a#": "6B",
    "f": "7B",
    "c": "8B",
    "g": "9B",
    "d": "10B",
    "a": "11B",
    "e": "12B",
}


@dataclass(frozen=True, slots=True)
class CamelotKey:
    number: int  # 1..12
    letter: str  # "A" minor | "B" major

    def __str__(self) -> str:
        return f"{self.number}{self.letter}"

    @classmethod
    def parse(cls, code: str) -> CamelotKey:
        code = code.strip().upper()
        number, letter = int(code[:-1]), code[-1]
        if not (1 <= number <= 12) or letter not in ("A", "B"):
            raise ValueError(f"Invalid Camelot code: {code!r}")
        return cls(number, letter)

    def neighbors(self) -> set[str]:
        """Keys that mix harmonically with this one (including itself)."""
        up = self.number % 12 + 1
        down = (self.number - 2) % 12 + 1
        swap = "B" if self.letter == "A" else "A"
        return {
            str(self),
            f"{up}{self.letter}",
            f"{down}{self.letter}",
            f"{self.number}{swap}",
        }

    def energy_boost(self) -> str:
        """+2 semitone-circle jump: classic energy lift."""
        return f"{(self.number + 1) % 12 + 1}{self.letter}"


def camelot_from_key_name(key: str | None) -> CamelotKey | None:
    """Best-effort conversion of a Mixxx/ID3 key string to a Camelot key.

    Accepts Camelot codes ("8A"), OpenKey-ish ("8m" ~ minor), and musical names
    ("Am", "F#m", "Eb", "B major", "c minor").
    """
    if not key:
        return None
    raw = key.strip()
    if not raw:
        return None

    # Already a Camelot code?
    upper = raw.upper()
    if len(upper) in (2, 3) and upper[-1] in ("A", "B") and upper[:-1].isdigit():
        try:
            return CamelotKey.parse(upper)
        except ValueError:
            return None

    # Musical name normalization: "F# minor" -> "f#m", "Eb Major" -> "eb"
    name = raw.lower().replace("♯", "#").replace("♭", "b")
    name = name.replace(" major", "").replace("maj", "").replace(" ", "")
    name = name.replace("minor", "m").replace("min", "m")
    code = _KEY_TO_CAMELOT.get(name)
    return CamelotKey.parse(code) if code else None


def compatible_keys(key: str | None) -> set[str]:
    """All Camelot codes that mix well with `key`. Empty set if unknown."""
    ck = camelot_from_key_name(key)
    return ck.neighbors() if ck else set()
