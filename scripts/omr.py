"""Convert PDF scores in data/reference/ to MusicXML with Audiveris, locally.

    python scripts/omr.py                 # every PDF in data/reference/ without an OMR result
    python scripts/omr.py "data/reference/my piece.pdf" --force

For data/reference/<name>.pdf this writes data/reference/<name>.omr.mxl (raw OMR result) and keeps
the Audiveris book in data/reference/omr/<name>.omr for correcting in the Audiveris editor.
OMR output always needs checking: open the .omr.mxl in MuseScore, fix it against the PDF, and
save it as data/reference/<name>.musicxml; the evaluation prefers that corrected file.

Never use MuseScore's "Import PDF" for these scores: it uploads them to musescore.com.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "data" / "reference"
DEFAULT_AUDIVERIS = Path(r"C:\Program Files\Audiveris\Audiveris.exe")


def find_audiveris() -> Path:
    env = os.environ.get("AUDIVERIS_EXE")
    for candidate in (env, shutil.which("audiveris"), DEFAULT_AUDIVERIS):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    sys.exit("Audiveris not found: winget install audiveris.org.Audiveris (or set AUDIVERIS_EXE)")


def convert(pdf: Path, audiveris: Path) -> list[Path]:
    work = REFERENCE / "omr"
    work.mkdir(parents=True, exist_ok=True)
    cmd = [str(audiveris), "-batch", "-transcribe", "-export", "-save", "-output", str(work)]
    proc = subprocess.run(
        [*cmd, "--", str(pdf)], check=False, capture_output=True, text=True, errors="replace"
    )
    # A book with several movements is exported as <name>.mvt1.mxl, <name>.mvt2.mxl, ...
    exported = sorted(work.glob(f"{pdf.stem}.mxl")) + sorted(work.glob(f"{pdf.stem}.mvt*.mxl"))
    if proc.returncode != 0 or not exported:
        tail = "\n".join(proc.stdout.splitlines()[-15:] + proc.stderr.splitlines()[-15:])
        raise RuntimeError(f"Audiveris failed on {pdf.name} (exit {proc.returncode}):\n{tail}")
    results = []
    for src in exported:
        suffix = src.name[len(pdf.stem) :].removesuffix(".mxl")  # "" or ".mvt1"
        dest = REFERENCE / f"{pdf.stem}{suffix}.omr.mxl"
        shutil.move(str(src), dest)
        results.append(dest)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pdfs", nargs="*", type=Path, help="default: all PDFs in data/reference/")
    parser.add_argument("--force", action="store_true", help="redo PDFs that already have a result")
    args = parser.parse_args(argv)

    pdfs = args.pdfs or sorted(REFERENCE.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {REFERENCE}")
        return 1
    audiveris = find_audiveris()
    failed = 0
    for pdf in pdfs:
        if not args.force and list(REFERENCE.glob(f"{pdf.stem}*.omr.mxl")):
            print(f"skip {pdf.name} (already converted; --force to redo)")
            continue
        print(f"OMR  {pdf.name} ...", flush=True)
        try:
            for out in convert(pdf.resolve(), audiveris):
                print(f"  -> {out.relative_to(ROOT)}")
        except RuntimeError as e:
            print(e)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
