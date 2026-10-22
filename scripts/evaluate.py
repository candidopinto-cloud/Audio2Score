"""Note F1 for every recording in data/ that has a reference score in data/reference/.

    python scripts/evaluate.py                       # all pairs, default backend(s)
    python scripts/evaluate.py --backends gaps,basic_pitch --log

Reference lookup for data/<name>.<ext>, first match wins:
    reference/<name>.musicxml | .mxl | .mid      corrected score
    reference/<name>.mvt*.musicxml               corrected, one file per movement
    reference/<name>.omr.mxl                     raw OMR (results marked "raw OMR")
    reference/<name>.mvt*.omr.mxl
--log appends the results to docs/EVAL.md.
"""

from __future__ import annotations

import argparse
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REFERENCE = DATA / "reference"
EVAL_MD = ROOT / "docs" / "EVAL.md"
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".mp4", ".mkv", ".mov", ".webm"}


def find_reference(stem: str) -> tuple[list[Path], bool]:
    """(files, is_raw_omr); empty list if none."""
    for ext in (".musicxml", ".mxl", ".mid"):
        if (REFERENCE / f"{stem}{ext}").is_file():
            return [REFERENCE / f"{stem}{ext}"], False
    mvts = sorted(REFERENCE.glob(f"{stem}.mvt*.musicxml"), key=_mvt_number)
    if mvts:
        return mvts, False
    if (REFERENCE / f"{stem}.omr.mxl").is_file():
        return [REFERENCE / f"{stem}.omr.mxl"], True
    return sorted(REFERENCE.glob(f"{stem}.mvt*.omr.mxl"), key=_mvt_number), True


def _mvt_number(path: Path) -> int:
    part = path.name.split(".mvt")[1].split(".")[0]
    return int(part) if part.isdigit() else 0


def main(argv: list[str] | None = None) -> int:
    from audio2score import audio_io, transcribe
    from audio2score.evaluate import load_reference, score_notes

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--backends", default="auto", help="comma-separated, e.g. gaps,basic_pitch")
    parser.add_argument("--log", action="store_true", help="append results to docs/EVAL.md")
    args = parser.parse_args(argv)
    backends = [b.strip() for b in args.backends.split(",") if b.strip()]
    backends = [transcribe.default_backend() if b == "auto" else b for b in backends]

    pairs = []
    for audio in sorted(p for p in DATA.iterdir() if p.suffix.lower() in AUDIO_EXT):
        refs, raw = find_reference(audio.stem)
        if refs:
            pairs.append((audio, refs, raw))
    if not pairs:
        print(f"No recording in {DATA} has a reference in {REFERENCE}")
        return 1

    rows = []
    for audio, refs, raw in pairs:
        ref = load_reference(refs)
        y, sr = audio_io.load(audio)
        for backend in backends:
            est = transcribe.run(y, sr, backend=backend)
            r50 = score_notes(ref, est, 0.05)
            r100 = score_notes(ref, est, 0.10)
            rows.append((audio.stem, backend, raw, r50, r100))
            print(
                f"{audio.stem[:40]:40s} {backend:11s} ref {r50.n_ref:4d} est {r50.n_est:4d}"
                f"  F1@50ms {r50.f1:.2f} (P {r50.precision:.2f} R {r50.recall:.2f})"
                f"  F1@100ms {r100.f1:.2f}{'  [raw OMR]' if raw else ''}",
                flush=True,
            )

    if args.log:
        today = datetime.date.today().isoformat()
        lines = [
            "",
            f"## Note F1 vs. reference scores ({today})",
            "",
            (
                "Reference aligned to the transcription by DTW on pitch-class activity, then"
                " mir_eval (onset tolerance, offsets ignored). Raw OMR references contain"
                " recognition errors."
            ),
            "",
            "| Piece | Backend | Ref | Ref notes | Est notes | P@50 | R@50 | F1@50ms | F1@100ms |",
            "|-------|---------|-----|-----------|-----------|------|------|---------|----------|",
        ]
        for stem, backend, raw, r50, r100 in rows:
            lines.append(
                f"| {stem} | {backend} | {'raw OMR' if raw else 'corrected'} | {r50.n_ref} |"
                f" {r50.n_est} | {r50.precision:.2f} | {r50.recall:.2f} | {r50.f1:.2f} |"
                f" {r100.f1:.2f} |"
            )
        with EVAL_MD.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Logged to {EVAL_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
