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
audio2score data\song.mp3 -o output   # writes output\song.mid + song.tab.txt
```
Also install ffmpeg (`winget install Gyan.FFmpeg`) and MuseScore 4 to view scores.

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
