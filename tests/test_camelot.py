"""Camelot wheel arithmetic tests."""

from __future__ import annotations

import pytest

from open_djing.analysis import CamelotKey, camelot_from_key_name, compatible_keys


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8A", "8A"),
        ("8a", "8A"),
        ("12B", "12B"),
        ("Am", "8A"),
        ("A minor", "8A"),
        ("C", "8B"),
        ("C major", "8B"),
        ("F#m", "11A"),
        ("Gbm", "11A"),
        ("Eb", "5B"),
        ("D# minor", "2A"),
        ("Bb minor", "3A"),
    ],
)
def test_parse_variants(raw: str, expected: str) -> None:
    ck = camelot_from_key_name(raw)
    assert ck is not None
    assert str(ck) == expected


@pytest.mark.parametrize("raw", [None, "", "  ", "H#m", "13A", "0B", "not-a-key"])
def test_parse_invalid(raw: str | None) -> None:
    assert camelot_from_key_name(raw) is None


def test_neighbors_wrap_around() -> None:
    # 1A neighbors: itself, 2A (up), 12A (down), 1B (relative)
    assert CamelotKey.parse("1A").neighbors() == {"1A", "2A", "12A", "1B"}
    # 12B wraps up to 1B
    assert CamelotKey.parse("12B").neighbors() == {"12B", "1B", "11B", "12A"}


def test_compatible_keys_from_name() -> None:
    # Am == 8A -> {8A, 9A, 7A, 8B}
    assert compatible_keys("Am") == {"8A", "9A", "7A", "8B"}
    assert compatible_keys("unknown") == set()


def test_energy_boost() -> None:
    assert CamelotKey.parse("8A").energy_boost() == "10A"
    assert CamelotKey.parse("11B").energy_boost() == "1B"
    assert CamelotKey.parse("12A").energy_boost() == "2A"
