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
