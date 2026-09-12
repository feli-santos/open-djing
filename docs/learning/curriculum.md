# Practice Curriculum — Weeks 1-4 (keyboard + mouse, no controller)

Each session: 25-40 min. Quality over duration — stop while it's still fun.
Prereq: Mixxx installed, 10+ analyzed tracks, `odj cues --write` done so every
track has MIX-IN / 32-IN / DROP / OUT-32 / MIX-OUT pads.

Mixxx keyboard essentials (US layout, defaults):

| Action | Deck 1 | Deck 2 |
|---|---|---|
| Load selected track | Shift+Left | Shift+Right |
| Play/pause | D | L |
| Cue | F | ; |
| Sync | 1 | 6 |
| Headphone cue (pre-listen) | T | Y |
| Hotcues 1-4 | Z X C V | M , . / |
| Tempo nudge | F1/F2 | F5/F6 |

(Check View → Keyboard Shortcuts in your Mixxx version if a key does nothing.)

## Week 1 — Phrase counting and structure

Goal: hear 8/16/32-beat phrases without looking.

- Drill A (10 min): play any funk track. Count beats out loud in groups of 8.
  Raise a finger every 8, restart at 32. Verify against the 32-IN cue.
- Drill B (10 min): jump between hotcues (MIX-IN → DROP → MIX-OUT) and predict
  what happens 8 beats after each jump before it happens.
- Drill C (10 min): same with one brasilidades track (live drummer). Notice the
  drift — that's why `odj analyze` flagged it "variable".

Done when: you can predict every drop in 5 tracks within 1 beat.

## Week 2 — Your first transitions (SYNC allowed)

Goal: clean 16-beat blend between two tracks in the same crate.

- Load two tracks from `odj_02_subindo` (check `odj next <track>` for a
  harmonic pair).
- At OUT-32 of track A: play track B from MIX-IN (synced), B's LOW EQ fully cut.
- Over 16 beats: swap the bass — B's LOW up while A's LOW goes down — then
  crossfade and pause A at its MIX-OUT.
- 5 blends per session. Record with Mixxx (Options → Record Mix) and listen back:
  where did the energy dip? Where did basses stack?

Done when: 3 consecutive blends with no audible train-wreck.

## Week 3 — EQ discipline and cuts

Goal: transitions that respect frequency space; fast cuts for funk.

- Bass-swap drill: blend held for 32 beats with both tracks audible, bass
  swapped exactly on a phrase boundary.
- Cut drill (funk BR): funk tracks often end abruptly — practice cutting on
  beat 1 of a phrase: crossfader hard-cut, no blend. Then echo-out cuts
  (add an Echo FX on deck A, cut the fader, let the tail ring into B).
- Vocal clash check: never two vocal sections at once. Use the BREAK cue to
  time your entry into instrumental space.

Done when: a 4-track mini-set (aquecimento → subindo) with 2 blends + 1 cut.

## Week 4 — Beatmatching by ear (SYNC off)

Goal: match tempo manually. This is the skill that separates button-pushers.

- Turn SYNC off. Load a stable pair (both `analyze` confidence >= 0.85).
- Pre-listen deck B in headphones (T/Y toggles). Nudge tempo (F5/F6) until the
  beats stop flanging, then release into the mix.
- Brasilidades bonus round: try it with a variable-tempo track and ride the
  nudges through the whole blend. Frustrating and extremely instructive.

Done when: one manual 16-beat blend without checking BPM numbers.

## Scoring yourself

After each session, one line in a practice log (any note app):
date, drill, what broke, one thing to fix next time.
The Set Review Coach (roadmap M6) will automate this from your recordings —
until then, your ears are the coach.
