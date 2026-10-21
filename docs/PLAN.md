# Audio2Score — milestone plan

## Milestone 0 — Environment (½ day)
- [x] Install Python 3.11, ffmpeg (`winget install Gyan.FFmpeg`), git.
- [x] Install MuseScore 4 (`winget install Musescore.Musescore`; 4.7.5 at `C:\Program Files\MuseScore 4\bin\MuseScore4.exe`).
- [x] `git init`; create venv: `py -3.11 -m venv .venv` then `.venv\Scripts\activate`.
- [x] `pip install -e .[dev,eval,basic_pitch]` (Basic Pitch 0.4.0 verified on Windows; pulls TensorFlow 2.15, numpy 1.26).
- [ ] Check GPU: `python -c "import torch; print(torch.cuda.is_available())"`. RTX 5080 present; torch not
      installed yet (not needed until GAPS; RTX 50-series needs a cu128+ build).
- [x] Test recordings in `data/` (3 so far: Rosas, Porto [drop-D], Xaxado).
- [ ] Reference scores: none — the three pieces are unpublished. Need another source (see EVAL.md).

## Milestone 1 — Command-line MVP: audio → MIDI + tab
- [x] `audio_io`: load any audio/video via ffmpeg → mono float32 array + sample rate.
- [x] `transcribe`: Basic Pitch backend first (easiest install) → `list[NoteEvent]`.
- [x] `fretting`: polyphonic Viterbi (group notes into chords by onset window ≈ 30–50 ms).
- [x] `export`: MIDI + ASCII tab.
- [x] `cli`: `audio2score song.mp4 -o out/`.
- [x] Unit tests for fretting and exporters.
- [x] Run on the real recordings in `data/`; review the tabs; log results in `docs/EVAL.md`
      (playability proxy, since there are no reference scores).
- [x] Handle spurious octave/harmonic notes: fretting may drop notes at a cost (cheap for likely
      overtones); high-fret cost; fixed+per-fret shift cost, time-scaled, hand carried through
      open strings.

## Milestone 2 — Classical-guitar transcription + score
- [x] Verify the GAPS model (see docs/RESEARCH.md): code + weights MIT, training data non-commercial.
- [ ] Integrate GAPS (`hf_midi_transcription`, needs torch cu128) as the primary backend; compare with Basic Pitch.
- [x] `rhythm`: librosa beat tracking, meter guess (2/3/4) from bass accents, per-beat 16th/triplet grid.
- [ ] Better beats for rubato playing (Beat This!, or `--bpm`/`--time-signature` hints); 6/8 and other compound meters.
- [x] `voices`: bass (stems down) / upper voice (melody + inner notes as chords).
- [x] MusicXML export via music21 (2 voices, time/key/tempo, legato fill, beat-safe tuplets); opens in MuseScore 4.
      `--string-numbers` adds circled string numbers. A linked TAB staff would be better (Milestone 3).
- [ ] Reference scores are PDFs: convert locally with Audiveris 5.11 (never MuseScore's online PDF import),
      correct in MuseScore, save as MusicXML in `data/reference/`.
- [ ] `scripts/evaluate.py`: align reference to recording (DTW), then note F1 (mir_eval). Log in `docs/EVAL.md`.

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
