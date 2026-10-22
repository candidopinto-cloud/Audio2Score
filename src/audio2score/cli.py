"""Command-line entry point: audio2score <input> -o <outdir>."""

from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from audio2score import audio_io, export, fretting, rhythm, transcribe, voices
from audio2score.models import STANDARD_TUNING

TUNINGS: dict[str, tuple[int, ...]] = {
    "standard": STANDARD_TUNING,
    "drop-d": (38, 45, 50, 55, 59, 64),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audio2score", description=__doc__)
    parser.add_argument("input", type=Path, help="audio or video file")
    parser.add_argument("-o", "--outdir", type=Path, default=Path("output"))
    parser.add_argument("--formats", default="midi,tab,musicxml", help="midi,musicxml,tab,gp5")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=transcribe.BACKENDS,
        help="auto = gaps if installed, else basic_pitch",
    )
    parser.add_argument("--tuning", default="standard", choices=sorted(TUNINGS))
    parser.add_argument("--max-fret", type=int, default=19)
    parser.add_argument("--playability", type=float, default=2.0, help="Lp-Viterbi p (1..inf)")
    parser.add_argument(
        "--time-signature", type=_time_signature, help="e.g. 3/4 (default: estimated)"
    )
    parser.add_argument("--bpm", type=float, help="tempo hint for the beat tracker")
    parser.add_argument(
        "--string-numbers", action="store_true", help="mark string numbers in the score"
    )
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

    backend = transcribe.default_backend() if args.backend == "auto" else args.backend
    print(f"Transcribing with {backend} ...", file=sys.stderr)
    notes = transcribe.run(audio, sr, backend=backend)
    print(f"  {len(notes)} notes", file=sys.stderr)

    cfg = fretting.FretConfig(tuning=tuning, max_fret=args.max_fret)
    notes = fretting.assign(notes, cfg, p=args.playability)
    unplaced = sum(n.string is None for n in notes)
    if unplaced:
        print(
            f"  {unplaced} notes left out of the tab (out of range, unplayable or likely"
            " overtones; still in the MIDI)",
            file=sys.stderr,
        )

    print("Tracking beats and quantizing ...", file=sys.stderr)
    trans = rhythm.run(audio, sr, notes, args.time_signature, args.bpm)
    num, den = trans.time_signature
    print(f"  ~{trans.tempo_bpm:.0f} BPM, {num}/{den}", file=sys.stderr)
    trans.notes = voices.assign(trans.notes)
    trans.tuning = tuning

    # MIDI and tab get every note. The score leaves out notes the fretting dropped (likely
    # overtones) but keeps notes that are just out of the guitar's range, so they can be reviewed.
    score = dataclasses.replace(
        trans,
        notes=[
            n for n in trans.notes if n.string is not None or not fretting.positions(n.pitch, cfg)
        ],
    )
    written = []
    for fmt in formats:
        src = score if fmt == "musicxml" else trans
        written += export.write_all(src, args.outdir, args.input.stem, [fmt], args.string_numbers)
    for path in written:
        print(f"Wrote {path}", file=sys.stderr)
    return 0


def _time_signature(text: str) -> tuple[int, int]:
    try:
        num, den = (int(x) for x in text.split("/"))
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"expected N/D, got {text!r}") from e
    return num, den


if __name__ == "__main__":
    sys.exit(main())
