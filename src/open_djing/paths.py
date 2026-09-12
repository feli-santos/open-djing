"""Well-known filesystem paths used across open-djing.

Everything is centralized here so tools, tests, and docs never hardcode paths.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def mixxx_settings_dir() -> Path:
    """Return the Mixxx settings directory for the current platform.

    On macOS, Mixxx >= 2.5 ships sandboxed: settings live inside the app
    container. We prefer the container path when it exists and fall back to
    the legacy location (pre-sandbox builds, or builds from source).
    """
    if sys.platform == "darwin":
        container = (
            Path.home()
            / "Library"
            / "Containers"
            / "org.mixxx.mixxx"
            / "Data"
            / "Library"
            / "Application Support"
            / "Mixxx"
        )
        legacy = Path.home() / "Library" / "Application Support" / "Mixxx"
        return container if container.exists() else legacy
    if sys.platform.startswith("linux"):
        return Path.home() / ".mixxx"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Mixxx"
    raise RuntimeError(f"Unsupported platform: {sys.platform}")


def mixxx_db_path() -> Path:
    """Return the path to mixxxdb.sqlite (may not exist yet)."""
    return mixxx_settings_dir() / "mixxxdb.sqlite"


def music_dir() -> Path:
    """Root music directory that Mixxx watches. Overridable via ODJ_MUSIC_DIR."""
    env = os.environ.get("ODJ_MUSIC_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Music" / "DJ"


def odj_data_dir() -> Path:
    """open-djing's own data directory (analysis cache, backups)."""
    env = os.environ.get("ODJ_DATA_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".open-djing"


def backups_dir() -> Path:
    return odj_data_dir() / "backups"
