"""Command-line entry point: audio2score <input> -o <outdir>."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from audio2score import audio_io, export, fretting, transcribe
from audio2score.models import STANDARD_TUNING

TUNINGS: dict[str, tuple[int, ...]] = {
    "standard": STANDARD_TUNING,
    "drop-d": (38, 45, 50, 55, 59, 64),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audio2score", description=__doc__)
    parser.add_argument("input", type=Path, help="audio or video file")
    parser.add_argument("-o", "--outdir", type=Path, default=Path("output"))
    parser.add_argument("--formats", default="midi,tab", help="midi,musicxml,tab,gp5")
    parser.add_argument("--backend", default="basic_pitch", choices=transcribe.BACKENDS)
    parser.add_argument("--tuning", default="standard", choices=sorted(TUNINGS))
    parser.add_argument("--max-fret", type=int, default=19)
    parser.add_argument("--playability", type=float, default=2.0, help="Lp-Viterbi p (1..inf)")
    args = parser.parse_args(argv)

    formats = [f.strip() for f in args.formats.split(",") if f.strip()]
    for fmt in formats:
        if fmt not in export.FORMATS:
            parser.error(f"unknown format {fmt!r}; choose from {', '.join(export.FORMATS)}")
        if fmt not in export.IMPLEMENTED:
            parser.error(f"{fmt} export is not implemented yet (see docs/PLAN.md)")
    tuning = TUNINGS[args.tuning]

    print(f"Loading {args.input} ...", file=sys.stderr)
    audio, sr = audio_io.load(args.input)
    print(f"  {len(audio) / sr:.1f} s of audio", file=sys.stderr)

    print(f"Transcribing with {args.backend} ...", file=sys.stderr)
    notes = transcribe.run(audio, sr, backend=args.backend)
    print(f"  {len(notes)} notes", file=sys.stderr)

    cfg = fretting.FretConfig(tuning=tuning, max_fret=args.max_fret)
    notes = fretting.assign(notes, cfg, p=args.playability)
    unplaced = sum(n.string is None for n in notes)
    if unplaced:
        print(f"  {unplaced} notes could not be placed on the fretboard", file=sys.stderr)

    written = export.write_all(notes, args.outdir, args.input.stem, formats, tuning=tuning)
    for path in written:
        print(f"Wrote {path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
