"""Smoke tests: package imports, paths resolve, CLI responds."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from open_djing import __version__, paths
from open_djing.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_paths_are_absolute() -> None:
    assert paths.mixxx_settings_dir().is_absolute()
    assert paths.mixxx_db_path().name == "mixxxdb.sqlite"
    assert paths.music_dir().is_absolute()


def test_music_dir_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ODJ_MUSIC_DIR", "/tmp/custom-music")
    assert paths.music_dir() == Path("/tmp/custom-music")


def test_data_dir_env_override(monkeypatch) -> None:
    monkeypatch.setenv("ODJ_DATA_DIR", "/tmp/custom-odj")
    assert paths.odj_data_dir() == Path("/tmp/custom-odj")
    assert paths.backups_dir() == Path("/tmp/custom-odj/backups")
