# Audio2Score

Convert audio or video recordings into sheet music and guitar tablature.
First target: solo nylon-string (classical) guitar.

## Quick start (Windows)
```powershell
cd C:\Audio2Score
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -e .[dev,eval,basic_pitch]
pytest
audio2score "data\my song.mp3" -o output   # writes my song.mid, .tab.txt and .musicxml
# Without activating the venv, run from C:\Audio2Score:
#   .\.venv\Scripts\audio2score "data\my song.mp3" -o output
```
Also install ffmpeg (`winget install Gyan.FFmpeg`) and MuseScore 4 to view scores.

### GAPS transcription model (recommended; used automatically when installed)
Classical-guitar model by Riley et al. (code and weights MIT; trained on non-commercial data, see
`docs/RESEARCH.md`). Runs on the GPU if available; weights (~100 MB) download on first use.
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu128   # RTX 50-series needs cu128+
pip install "huggingface-hub>=0.16" "safetensors>=0.3" "torchlibrosa>=0.1"
pip install --no-deps git+https://github.com/xavriley/piano_transcription_inference.git git+https://github.com/xavriley/hf_midi_transcription
```
`--no-deps` keeps resampy at 0.4.2 for Basic Pitch; `pip check` will mention this, harmlessly.
Choose a backend explicitly with `--backend gaps` or `--backend basic_pitch`.

### Reference scores from PDF
Put PDFs in `data/reference/` and run `python scripts/omr.py` (needs Audiveris:
`winget install audiveris.org.Audiveris`). It runs locally and writes `<name>.omr.mxl`; correct
that in MuseScore and save it as `<name>.musicxml`. Do not use MuseScore's "Import PDF" for
private scores — it uploads them to musescore.com.

## Layout
```
src/audio2score/   pipeline modules (audio_io, transcribe, rhythm, voices, fretting, export, cli)
tests/             unit tests (no audio or models needed)
scripts/           evaluation and one-off tools
data/              your test recordings (not in git); data/reference/ = true scores
docs/              PLAN.md (milestones), EVAL.md (accuracy results)
output/            generated files (not in git)
```

See `CLAUDE.md` for architecture and decisions, `docs/PLAN.md` for the roadmap.
