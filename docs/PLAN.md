# Audio2Score — milestone plan

## Milestone 0 — Environment (½ day)
- [x] Install Python 3.11, ffmpeg (`winget install Gyan.FFmpeg`), git.
- [ ] Install MuseScore 4 (needed from Milestone 2): `winget install MuseScore.MuseScore`.
- [x] `git init`; create venv: `py -3.11 -m venv .venv` then `.venv\Scripts\activate`.
- [x] `pip install -e .[dev,eval,basic_pitch]` (Basic Pitch 0.4.0 verified on Windows; pulls TensorFlow 2.15, numpy 1.26).
- [ ] Check GPU: `python -c "import torch; print(torch.cuda.is_available())"`. RTX 5080 present; torch not
      installed yet (not needed until GAPS; RTX 50-series needs a cu128+ build).
- [ ] Put 5–10 test recordings in `data/` and their scores in `data/reference/`.

## Milestone 1 — Command-line MVP: audio → MIDI + tab
- [x] `audio_io`: load any audio/video via ffmpeg → mono float32 array + sample rate.
- [x] `transcribe`: Basic Pitch backend first (easiest install) → `list[NoteEvent]`.
- [x] `fretting`: polyphonic Viterbi (group notes into chords by onset window ≈ 30–50 ms).
- [x] `export`: MIDI + ASCII tab.
- [x] `cli`: `audio2score song.mp4 -o out/`.
- [x] Unit tests for fretting and exporters.
- [ ] Run on the real recordings in `data/`; review the tabs and log a first F1 in `docs/EVAL.md`.
- [ ] Handle spurious octave/harmonic notes from the transcriber (on synthetic audio one ghost note
      forced a whole chord up the neck). Idea: let fretting drop low-velocity notes at a cost.

## Milestone 2 — Classical-guitar transcription + score
- [ ] Verify and integrate the GAPS model as the primary backend; compare with Basic Pitch.
- [ ] `rhythm`: tempo/beat tracking, meter, quantize onsets/durations to a grid.
- [ ] `voices`: split into bass / melody (+ inner) voices.
- [ ] MusicXML export via music21 (voices, time/key signatures); open in MuseScore.
- [ ] `scripts/evaluate.py`: note F1 vs. reference MIDI/MusicXML (mir_eval). Log in `docs/EVAL.md`.

## Milestone 3 — Better tabs
- [ ] Tune fretting cost weights against real classical fingerings.
- [ ] Lp-Viterbi with `--playability p` option; open-string / barre bonuses; time-scaled movement cost.
- [ ] GP5 export (PyGuitarPro) for TuxGuitar / Guitar Pro.
- [ ] Optional: right-hand fingering (p-i-m-a) and string numbers in the score.

## Milestone 4 — Robustness
- [ ] Optional source separation (Demucs) for non-solo recordings.
- [ ] Capo / alternate tunings; tuning-offset detection (A≠440).
- [ ] Long-file chunking; progress reporting.

## Milestone 5 — UI
- [ ] Desktop UI (PySide6) or local web UI: load file, view score/tab, play back, edit, export.

## Later
- Techniques (slides, slurs/hammer-ons, harmonics, rasgueado).
- Steel-string acoustic, electric guitar, other instruments.
