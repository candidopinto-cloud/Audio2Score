# Audio2Score — project context for Claude Code

## What this is
Audio2Score converts audio or video recordings into readable music notation
(standard score) and guitar tablature. **Initial focus: solo nylon-string
(classical) guitar.** Other instruments and electric guitar come later.

Owner: Candido. Platform: Windows (project lives at `C:\Audio2Score`).

## Pipeline (target architecture)
```
input (audio/video)
  -> audio_io      : ffmpeg extract/convert -> mono 22.05/44.1 kHz WAV
  -> [separation]  : OPTIONAL, later (Demucs / BS-Roformer) — skip for solo guitar
  -> transcribe    : audio -> note events (onset, offset, pitch, velocity)
                     primary: GAPS model (classical-guitar trained)
                     fallback: Basic Pitch
  -> rhythm        : tempo, beats, meter, quantization (librosa / Beat This!)
  -> voices        : split into bass / melody / inner voices (classical notation)
  -> fretting      : polyphonic Viterbi over chord shapes -> (string, fret)
  -> export        : MIDI, MusicXML (music21), ASCII tab, GP5 (PyGuitarPro)
  -> UI            : later (PySide6 desktop or simple web UI)
```

## Key decisions (keep unless the owner changes them)
- Python 3.11, src layout, package name `audio2score`.
- Each stage is a separate module with a plain-data interface
  (`NoteEvent` dataclasses in `audio2score/models.py`) so backends can be swapped.
- Fretting is **polyphonic from day one** (fingerstyle is rarely monophonic).
  Start with sum-cost Viterbi; add Lp-Viterbi with `p` as a "playability" knob
  (default p=2). Use beam search (top-K ≈ 10) if chord-shape space explodes.
- Standard notation is a first-class output, not an afterthought: MusicXML
  with separate voices, opened in MuseScore for review.
- Tuning is configurable (standard EADGBE default; support drop-D etc.).
  Classical guitar: 19 usable frets by default.
- Licensing: prefer MIT/Apache/BSD components. **MuScriptor weights are
  CC BY-NC (non-commercial)** — do not make it a hard dependency.

## Things to verify before relying on them
The initial research (AudioTranscriptionOpenSource.docx, in the owner's
OneDrive Documents) was AI-generated. Before depending on any of these,
confirm the repo exists, its license, install method and recent activity:
GAPS model code/weights, rayBastard/tabforge, SumitGA/Riffscribe,
scottvr/gtrsnipe, ThanhMinh12/Fretwork, TART (arXiv 2510.02597).
Treat quoted accuracy figures as unverified.

## Conventions
- Format with `ruff format`, lint with `ruff check`, test with `pytest`.
- Pure-logic modules (fretting, rhythm quantization, exporters) must have
  unit tests that run without ML models or audio files.
- Large files (audio, model weights, outputs) never go in git — see `.gitignore`.
  Test audio lives in `data/` (ignored); ground-truth scores in `data/reference/`.
- CLI entry point: `audio2score <input> -o <outdir> [--formats midi,musicxml,tab,gp5]`.

## Evaluation
Milestone quality is judged on 5–10 solo classical guitar recordings for which
the owner has the real score. Metrics: note-level F1 (mir_eval, onset ±50 ms),
plus manual review in MuseScore. Keep results in `docs/EVAL.md`.

## Current status
See `docs/PLAN.md` for milestones. Start with Milestone 1.
