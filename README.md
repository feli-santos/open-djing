# open-djing

Open-source toolkit that turns [Mixxx](https://mixxx.org) into an AI-augmented DJ learning platform.

Built for anyone starting a DJ career or pushing their hobby further: it organizes your library, marks your tracks, plans your transitions, and (eventually) reviews your sets like a coach — all on top of free, open-source software.

## Why

Commercial DJ software locks automation behind closed formats. Mixxx keeps everything in an open SQLite database and scriptable interfaces, which means your tools — and your AI agents — can genuinely help you learn:

- **Analyze**: beatgrid, key (Camelot), song structure, and energy for every track.
- **Auto-cue**: phrase-aligned hot cues (intro, drop, vocal start, outro) written straight into Mixxx.
- **Smart crates**: crates organized by party moment and harmonic/BPM compatibility — including half/double-time mixing (90 BPM hiphop ↔ 130 BPM funk).
- **Learn**: a practice curriculum with drills, and a roadmap toward AI set review and live agent B2B mixing.

First-class genres for the reference library: **brasilidades, Brazilian funk, and hiphop** — styles with live drummers, syncopation, and half-time relationships that most tools handle poorly.

## Status

Early alpha. Milestones:

- [x] M0 — Toolchain: Mixxx install, `odj doctor`, safe DB `odj backup`
- [ ] M1 — Seed library conventions + sourcing guide
- [ ] M2 — Mixxx SQLite adapter (read-only models, safety rails)
- [ ] M3 — Analysis pipeline (librosa): beatgrid, key, structure, energy
- [ ] M4 — Auto-cue writer (dry-run by default)
- [ ] M5 — Smart crates builder
- [ ] M6+ — Set Review Coach, practice drills, IAC MIDI live bridge, AI B2B mode, MCP server, crate digger agent

## Install

Requirements: macOS (Linux support planned), [Homebrew](https://brew.sh), [uv](https://docs.astral.sh/uv/).

```sh
brew install --cask mixxx
brew install ffmpeg

git clone https://github.com/feli-santos/open-djing.git
cd open-djing
uv sync --extra analysis

uv run odj doctor   # checks your whole setup
```

## Usage

```sh
odj doctor    # environment sanity check
odj backup    # snapshot mixxxdb.sqlite before any experiment
odj version
```

More commands land with each milestone (`odj analyze`, `odj cues`, `odj crates`).

## Safety model

Mixxx's database is the source of truth for your library. open-djing:

1. **Never writes while Mixxx is running** (process check).
2. **Backs up** via the SQLite backup API before any write.
3. **Dry-runs by default** — every mutating command prints its plan first.

## License

[MIT](LICENSE)
