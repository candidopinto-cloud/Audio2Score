# Evaluation log

| Date | Backend | Piece | Note F1 (onset ±50 ms) | Notes |
|------|---------|-------|------------------------|-------|

## Playability proxy (no reference scores available)

The three test pieces are unpublished, so note F1 can't be computed for them. Until a reference
set exists, fretting changes are judged by tab statistics plus reading the tabs:
notes left out of the tab, share of notes at fret 12+, and "fast jumps" (consecutive fretted
notes < 0.35 s apart that differ by >= 7 frets). Transcription: Basic Pitch 0.4.0, p = 2.

| Date | Change | Piece (tuning) | Notes | Left out | Fret 12+ | Fast jumps |
|------|--------|----------------|-------|----------|----------|------------|
| 2026-10-21 | Baseline Viterbi | As Rosas Não Falam (std) | 847 | 2 | 1.8% | 3 |
| 2026-10-21 | Baseline Viterbi | Porto (std, wrong) | 882 | 15 | 1.4% | 1 |
| 2026-10-21 | Baseline Viterbi | São João Xaxado (std) | 2845 | 18 | 10.1% | 34 |
| 2026-10-21 | Overtone drops, high-fret cost, shift model | As Rosas Não Falam (std) | 847 | 44 | 0.7% | 2 |
| 2026-10-21 | Overtone drops, high-fret cost, shift model | Porto (drop-D) | 882 | 5 | 0.0% | 0 |
| 2026-10-21 | Overtone drops, high-fret cost, shift model | São João Xaxado (std) | 2845 | 210 | 0.4% | 12 |

Of the notes left out after the change: Rosas 42/44 and Xaxado 193/210 are flagged overtones
(a louder note an octave/12th/2 octaves below at the same onset), 6 are out of range, the rest
(2 and 11) are quiet notes in large chords.

## Backend comparison (2026-10-21, no reference)

Agreement between backends (mir_eval note matching, onset ±50 ms, offsets ignored). "Overtone-like"
= a louder note an octave/12th/2 octaves below at the same onset.

| Piece | Basic Pitch notes | GAPS notes | GAPS notes also in BP | BP notes also in GAPS | Overtone-like BP / GAPS |
|-------|-------------------|------------|-----------------------|-----------------------|-------------------------|
| As Rosas Não Falam | 847 | 554 | 91% | 60% | 13% / 0% |
| Porto | 882 | 986 | 70% | 78% | 2% / 0% |
| São João Xaxado | 2845 | 1891 | 86% | 57% | 19% / 2% |

GAPS runs in ~8 s per piece on the RTX 5080. For Rosas and Xaxado almost everything GAPS finds,
Basic Pitch also finds, and Basic Pitch's ~40% extra notes look like duplicates/overtones. Not
proof of accuracy — needs reference scores. GAPS is now the default backend.

Audiveris sanity check: OMR of our own MuseScore-rendered Porto page 1 (35 bars, rhythmically
messy) recovered 81% of pitches per bar and 57% at the exact position — expect manual correction.

## Note F1 vs. reference scores (2026-10-21)

Reference aligned to the transcription by DTW on pitch-class activity, then mir_eval (onset tolerance, offsets ignored). Raw OMR references contain recognition errors.

| Piece | Backend | Ref | Ref notes | Est notes | P@50 | R@50 | F1@50ms | F1@100ms |
|-------|---------|-----|-----------|-----------|------|------|---------|----------|
| Abel Carlevaro - Preludios Americanos (Evocación) | gaps | raw OMR | 205 | 848 | 0.03 | 0.14 | 0.05 | 0.06 |
| Abel Carlevaro - Preludios Americanos (Evocación) | basic_pitch | raw OMR | 205 | 1719 | 0.01 | 0.11 | 0.02 | 0.03 |
| Hans_Werner_Henze_-_Drei_tentos | gaps | raw OMR | 1141 | 1191 | 0.44 | 0.46 | 0.45 | 0.55 |
| Hans_Werner_Henze_-_Drei_tentos | basic_pitch | raw OMR | 1141 | 1801 | 0.26 | 0.41 | 0.31 | 0.39 |
| Pensamiento_Espanol_by_Jose_Broca | gaps | raw OMR | 1147 | 1396 | 0.46 | 0.56 | 0.51 | 0.58 |
| Pensamiento_Espanol_by_Jose_Broca | basic_pitch | raw OMR | 1147 | 2130 | 0.27 | 0.51 | 0.35 | 0.43 |

Notes on this table:
- **Carlevaro: ignore.** Its OMR result is unusable (bass clef, wrong key, garbled notes — the
  scan is dense with fingerings, string numbers and barré marks). Needs manual entry/correction.
- **Broca** (clean modern engraving) is the most trustworthy reference; OMR still drops the small
  ornament notes and adds stray clef changes. Diagnostics for GAPS: F1 0.51 → 0.67 when the
  onset tolerance is widened from 50 to 400 ms, and only ~+4 points when octaves are ignored, so
  most misses are not timing or octave errors: ~1/3 of GAPS notes and ~1/4 of reference notes have
  no counterpart at all (OMR omissions, edition vs. performance differences, transcription errors —
  not separable until the reference is corrected).
- GAPS beats Basic Pitch on every piece (+0.14 to +0.16 F1@50ms). Absolute numbers are lower
  bounds until the references are corrected in MuseScore.
