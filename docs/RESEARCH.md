# Verified components

Checked 2026-10-21 against the actual repositories/records (not the AI-generated research doc).
Accuracy figures are as reported by the authors, not reproduced here.

## Transcription
- **GAPS model** — code https://github.com/xavriley/hf_midi_transcription (MIT, alpha, last commit
  2026-01-27), weights https://huggingface.co/xavriley/midi-transcription-models (MIT),
  `guitar-gaps.pth`. Kong et al. high-resolution CRNN fine-tuned on classical guitar. PyTorch,
  16 kHz mono input, 10 s segments, outputs MIDI. CLI: `midi_transcription in.wav out.mid
  --instrument guitar --device cuda`. Reported onset F1: 94.3 (GAPS test), 88.1 (GuitarSet
  zero-shot). Depends on a fork of piano_transcription_inference (old torch-era code; untested
  here). RTX 5080 needs a CUDA 12.8+ torch build.
  **Caveat:** trained on the GAPS dataset, whose licence is non-commercial (see below).
- **Basic Pitch 0.4.0** — Apache-2.0; on Windows installs TensorFlow 2.15 and numpy 1.26. In use.

## Datasets
- **GAPS** (ISMIR 2024) — 300 classical guitar performances, ~14 h, aligned MIDI + MusicXML with
  string/fret. Zenodo 13962272: no audio, CC BY-NC-SA 4.0. Hugging Face xavriley/GAPS: with
  audio (16.4 GB), card says MIT. Licences conflict — treat as non-commercial research data.
- **GuitarSet** — Zenodo 3371780, CC BY 4.0, string/fret annotations (steel-string acoustic).

## Other repos from the original research
- TART (arXiv 2510.02597): paper exists, no code found.
- rayBastard/tabforge: MIT, active. SumitGA/Riffscribe: no licence. scottvr/gtrsnipe: MIDI→tab,
  licence "Other". ThanhMinh12/Fretwork: a Hugging Face Space using the GAPS models, no licence.

## PDF scores → MusicXML (local only; the owner's scores are unpublished)
- **Audiveris 5.11.0** (2026-07-11), AGPL-3.0, Windows .msi with bundled Java. Batch:
  `-batch -transcribe -export -output <dir> score.pdf`. Ignores tab staves; two-voice writing
  with opposing stems can lose noteheads, so expect manual correction. Use it as an external
  tool, not a dependency. Only use github.com/Audiveris (audiveris.com/.net are not official).
- **MuseScore 4 "Import PDF" uploads to musescore.com** — do not use for private scores.
- homr (AGPL-3.0, active) and oemer (MIT, inactive since 2025-04): possible second opinions.
