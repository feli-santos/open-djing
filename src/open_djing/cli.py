"""odj: the open-djing command-line interface."""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from open_djing import __version__, paths

app = typer.Typer(
    name="odj",
    help="open-djing: turn Mixxx into an AI-augmented DJ learning platform.",
    no_args_is_help=True,
)
console = Console()


def _mixxx_is_running() -> bool:
    """Return True if the Mixxx app is currently running (macOS/Linux)."""
    result = subprocess.run(
        ["pgrep", "-x", "mixxx"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    # macOS app binary is capitalized
    result = subprocess.run(
        ["pgrep", "-x", "Mixxx"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


@app.command()
def version() -> None:
    """Print the open-djing version."""
    console.print(f"open-djing {__version__}")


@app.command()
def doctor() -> None:
    """Check that the environment is ready: Mixxx, database, music dir, audio tooling."""
    table = Table(title="odj doctor", show_lines=False)
    table.add_column("check", style="bold")
    table.add_column("status")
    table.add_column("detail", overflow="fold")

    ok = "[green]ok[/green]"
    warn = "[yellow]warn[/yellow]"
    fail = "[red]fail[/red]"
    problems = 0

    # Mixxx app installed
    mixxx_app = shutil.which("mixxx") or (
        "/Applications/Mixxx.app" if Path("/Applications/Mixxx.app").exists() else None
    )
    if mixxx_app:
        table.add_row("mixxx installed", ok, str(mixxx_app))
    else:
        table.add_row("mixxx installed", fail, "brew install --cask mixxx")
        problems += 1

    # Mixxx running (informational; writes must happen while closed)
    running = _mixxx_is_running()
    table.add_row(
        "mixxx running",
        warn if running else ok,
        "running now — DB writes are blocked" if running else "not running",
    )

    # Settings dir + database
    db = paths.mixxx_db_path()
    if db.exists():
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            n_tracks = con.execute(
                "SELECT count(*) FROM library WHERE mixxx_deleted = 0"
            ).fetchone()[0]
            schema_version = con.execute(
                "SELECT value FROM settings WHERE name = 'mixxx.schema.version'"
            ).fetchone()
            con.close()
            table.add_row(
                "mixxxdb.sqlite",
                ok,
                f"{db} — {n_tracks} tracks, schema v{schema_version[0] if schema_version else '?'}",
            )
        except sqlite3.Error as e:
            table.add_row("mixxxdb.sqlite", warn, f"{db} exists but query failed: {e}")
    else:
        table.add_row("mixxxdb.sqlite", warn, f"{db} not found — launch Mixxx once to create it")

    # Music dir
    mdir = paths.music_dir()
    if mdir.exists():
        n_audio = sum(
            1
            for p in mdir.rglob("*")
            if p.suffix.lower() in {".mp3", ".flac", ".wav", ".aiff", ".m4a", ".ogg"}
        )
        table.add_row("music dir", ok, f"{mdir} — {n_audio} audio files")
    else:
        table.add_row("music dir", warn, f"{mdir} does not exist — mkdir and point Mixxx at it")

    # ffmpeg
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        table.add_row("ffmpeg", ok, ffmpeg)
    else:
        table.add_row("ffmpeg", fail, "brew install ffmpeg")
        problems += 1

    # analysis extras
    try:
        import librosa  # noqa: F401

        table.add_row("librosa", ok, "analysis extras installed")
    except ImportError:
        table.add_row("librosa", warn, "not installed — uv sync --extra analysis")

    # odj data dir
    ddir = paths.odj_data_dir()
    table.add_row("odj data dir", ok if ddir.exists() else warn, str(ddir))

    console.print(table)
    if problems:
        raise typer.Exit(code=1)


@app.command()
def analyze(
    target: str = typer.Argument(None, help="File or directory (default: your music dir)"),
    force: bool = typer.Option(False, "--force", help="Re-analyze even if cached"),
) -> None:
    """Analyze audio: beatgrid+confidence, Camelot key, structure, energy (cached)."""
    try:
        from open_djing.analysis.cache import AnalysisCache
        from open_djing.analysis.engine import analyze_file, file_sha1, iter_audio_files
    except ImportError:
        console.print("[red]Analysis extras missing.[/red] Run: uv sync --extra analysis")
        raise typer.Exit(code=1) from None

    root = Path(target).expanduser() if target else paths.music_dir()
    if not root.exists():
        console.print(f"[red]{root} does not exist.[/red]")
        raise typer.Exit(code=1)

    files = iter_audio_files(root)
    if not files:
        console.print(f"[yellow]No audio files under {root}.[/yellow]")
        raise typer.Exit()

    cache = AnalysisCache()
    console.print(f"Analyzing [bold]{len(files)}[/bold] file(s) from {root}\n")

    done = skipped = failed = 0
    for f in files:
        digest = file_sha1(f)
        if not force and cache.get(digest):
            skipped += 1
            continue
        try:
            with console.status(f"[cyan]{f.name}[/cyan]"):
                result = analyze_file(f)
            cache.put(result)
            done += 1
            grid = (
                "[green]stable[/green]"
                if result.beatgrid.is_stable
                else "[yellow]variable[/yellow]"
            )
            console.print(
                f"[green]+[/green] {f.name} — {result.bpm} BPM ({grid},"
                f" conf {result.beatgrid.confidence}), key {result.camelot or '?'},"
                f" energy {result.energy}/10, vocals {result.vocal_presence:.0%}"
            )
        except Exception as e:  # noqa: BLE001 — keep batch going, report at end
            failed += 1
            console.print(f"[red]x[/red] {f.name}: {e}")

    console.print(
        f"\nanalyzed: {done}  cached: {skipped}  failed: {failed}"
        f"  (cache: {cache.count()} tracks total)"
    )
    if failed:
        raise typer.Exit(code=1)


@app.command()
def cues(
    target: str = typer.Argument(None, help="File or directory (default: your music dir)"),
    write: bool = typer.Option(False, "--write", help="Actually write to Mixxx (default: dry-run)"),
    overwrite: bool = typer.Option(
        False, "--overwrite", help="Replace hotcues on pads we manage (1-4, 7-8)"
    ),
) -> None:
    """Plan phrase-aligned hot cues from analysis; write into Mixxx with --write."""
    try:
        from open_djing.analysis.cache import AnalysisCache
        from open_djing.analysis.engine import file_sha1, iter_audio_files
    except ImportError:
        console.print("[red]Analysis extras missing.[/red] Run: uv sync --extra analysis")
        raise typer.Exit(code=1) from None

    from open_djing.cues.planner import plan_cues
    from open_djing.cues.writer import (
        MixxxRunningError,
        backup_before_write,
        write_cue_plan,
    )
    from open_djing.mixxx import MixxxDB

    root = Path(target).expanduser() if target else paths.music_dir()
    files = iter_audio_files(root)
    if not files:
        console.print(f"[yellow]No audio files under {root}.[/yellow]")
        raise typer.Exit()

    cache = AnalysisCache()
    plans = []
    for f in files:
        analysis = cache.get(file_sha1(f))
        if analysis is None:
            console.print(
                f"[yellow]-[/yellow] {f.name}: not analyzed yet (run `odj analyze` first)"
            )
            continue
        plan = plan_cues(analysis)
        plans.append(plan)
        console.print(f"\n[bold]{f.name}[/bold]")
        for w in plan.warnings:
            console.print(f"  [yellow]warning:[/yellow] {w}")
        for c in plan.cues:
            mins, secs = divmod(c.seconds, 60)
            console.print(f"  pad {c.hotcue_index + 1}: {c.label:<8} @ {int(mins)}:{secs:05.2f}")

    if not plans:
        raise typer.Exit()

    if not write:
        console.print(
            f"\n[cyan]Dry-run:[/cyan] {len(plans)} plan(s) shown. Re-run with --write to apply."
        )
        raise typer.Exit()

    db = MixxxDB()
    backup_path = backup_before_write(db.db_path, paths.backups_dir())
    console.print(f"\n[green]Backup:[/green] {backup_path}")

    applied = failed = 0
    for plan in plans:
        try:
            report = write_cue_plan(db, plan, overwrite=overwrite)
            applied += 1
            skipped = (
                f", kept pads {[p + 1 for p in report.skipped_pads]}" if report.skipped_pads else ""
            )
            console.print(
                f"[green]+[/green] track {report.track_id}: {report.written} new,"
                f" {report.replaced} replaced{skipped}"
            )
        except MixxxRunningError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from None
        except (LookupError, ValueError) as e:
            failed += 1
            console.print(f"[red]x[/red] {Path(plan.file_path).name}: {e}")

    console.print(f"\napplied: {applied}  failed: {failed}")
    if failed:
        raise typer.Exit(code=1)


@app.command()
def crates(
    write: bool = typer.Option(False, "--write", help="Write crates to Mixxx (default: dry-run)"),
) -> None:
    """Build party-moment crates (odj_*) from cached analysis."""
    from open_djing.analysis.cache import AnalysisCache
    from open_djing.crates.builder import build_crate_specs
    from open_djing.crates.writer import write_crates
    from open_djing.cues.writer import MixxxRunningError
    from open_djing.mixxx import MixxxDB

    cache = AnalysisCache()
    analyses = cache.all()
    if not analyses:
        console.print("[yellow]Analysis cache is empty — run `odj analyze` first.[/yellow]")
        raise typer.Exit()

    specs = build_crate_specs(analyses)
    for spec in specs:
        console.print(f"\n[bold]{spec.name}[/bold] — {spec.description}")
        for path in spec.file_paths:
            console.print(f"  {Path(path).name}")

    if not write:
        console.print(
            f"\n[cyan]Dry-run:[/cyan] {len(specs)} crate(s). Re-run with --write to apply."
        )
        raise typer.Exit()

    db = MixxxDB()
    try:
        reports = write_crates(db, specs)
    except MixxxRunningError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None

    console.print()
    for report in reports:
        console.print(f"[green]+[/green] {report.crate_name}: {report.track_count} tracks")
        for missing in report.missing_files:
            console.print(
                f"  [yellow]not in Mixxx library:[/yellow] {Path(missing).name} (rescan in Mixxx)"
            )


@app.command(name="next")
def next_track(
    track: str = typer.Argument(..., help="Path to the currently playing file"),
) -> None:
    """Suggest what to mix next, ranked by harmony and tempo compatibility."""
    from open_djing.analysis.cache import AnalysisCache
    from open_djing.analysis.engine import file_sha1
    from open_djing.crates.builder import mix_candidates

    cache = AnalysisCache()
    source_path = Path(track).expanduser()
    if not source_path.exists():
        console.print(f"[red]{source_path} not found.[/red]")
        raise typer.Exit(code=1)

    source = cache.get(file_sha1(source_path))
    if source is None:
        console.print("[yellow]Track not analyzed — run `odj analyze` first.[/yellow]")
        raise typer.Exit(code=1)

    candidates = mix_candidates(source, cache.all())
    if not candidates:
        console.print("[yellow]No compatible tracks in the analysis cache yet.[/yellow]")
        raise typer.Exit()

    console.print(
        f"[bold]{source_path.name}[/bold] — {source.bpm} BPM, key {source.camelot or '?'}\n"
    )
    table = Table(title="mix next")
    table.add_column("track")
    table.add_column("bpm", justify="right")
    table.add_column("key")
    table.add_column("tempo lock")
    table.add_column("harmonic")
    for c in candidates[:10]:
        ratio = {1.0: "straight", 2.0: "double", 0.5: "half", 0.75: "3:4", 4 / 3: "4:3"}.get(
            c.ratio, f"{c.ratio:.2f}"
        )
        table.add_row(
            Path(c.file_path).name,
            f"{c.bpm:.1f}",
            c.camelot or "?",
            ratio,
            "[green]yes[/green]" if c.harmonic else "no",
        )
    console.print(table)


@app.command()
def library() -> None:
    """Show Mixxx library overview: tracks, analysis coverage, genres, crates."""
    from open_djing.mixxx import MixxxDB

    db = MixxxDB()
    try:
        version = db.schema_version()
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None

    stats = db.stats()
    console.print(f"[bold]Mixxx library[/bold] (schema v{version}) — {db.db_path}\n")
    console.print(f"tracks: [bold]{stats['tracks']}[/bold]  analyzed (bpm): {stats['with_bpm']}")

    dirs = db.music_directories()
    console.print(f"music dirs: {', '.join(str(d) for d in dirs) or '[yellow]none set[/yellow]'}")

    genres = stats["genres"]
    if genres:
        gtable = Table(title="genres")
        gtable.add_column("genre")
        gtable.add_column("tracks", justify="right")
        for name, n in genres:
            gtable.add_row(name, str(n))
        console.print(gtable)

    crates = db.crates()
    if crates:
        ctable = Table(title="crates")
        ctable.add_column("crate")
        ctable.add_column("tracks", justify="right")
        ctable.add_column("locked")
        for crate in crates:
            ctable.add_row(crate.name, str(crate.track_count), "yes" if crate.locked else "")
        console.print(ctable)

    if stats["tracks"] == 0:
        console.print(
            "\n[yellow]Library is empty.[/yellow] Drop files into ~/Music/DJ"
            " and use Library → Rescan in Mixxx (docs/library/sourcing-guide.md has sources)."
        )


@app.command()
def backup() -> None:
    """Snapshot mixxxdb.sqlite into ~/.open-djing/backups (refuses while Mixxx is running)."""
    db = paths.mixxx_db_path()
    if not db.exists():
        console.print(f"[red]No database at {db}. Launch Mixxx once first.[/red]")
        raise typer.Exit(code=1)
    if _mixxx_is_running():
        console.print(
            "[red]Mixxx is running. Close it before backing up (avoids a mid-write copy).[/red]"
        )
        raise typer.Exit(code=1)

    paths.backups_dir().mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dest = paths.backups_dir() / f"mixxxdb-{stamp}.sqlite"

    # Use SQLite backup API rather than file copy: consistent even with WAL sidecars.
    src = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    dst = sqlite3.connect(dest)
    with dst:
        src.backup(dst)
    src.close()
    dst.close()

    size_mb = dest.stat().st_size / 1_048_576
    console.print(f"[green]Backed up[/green] {db.name} -> {dest} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    sys.exit(app())
