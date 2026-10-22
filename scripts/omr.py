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
import math
import os
import re
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


MAX_PIXELS = 16_000_000  # Audiveris rejects sheets above 20 Mpixels
MAX_DPI = 300
STEP_TIMEOUT_S = 600
FAILED_SHEET = re.compile(r"#(\d+)\][^\n]*Error processing stub")


def pdf_resolution(pdf: Path) -> tuple[int, int]:
    """(page count, DPI) such that every page stays under MAX_PIXELS when rasterized.

    Scanned PDFs often declare one point per scanned pixel, i.e. huge pages that the default
    300 DPI would blow up to 100+ Mpixels.
    """
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(str(pdf))
    sizes = [doc[i].get_size() for i in range(len(doc))]  # points, 1/72 inch
    largest = max(w * h for w, h in sizes)
    return len(sizes), min(MAX_DPI, int(72 * math.sqrt(MAX_PIXELS / largest)))


def run_audiveris(audiveris: Path, pdf: Path, work: Path, dpi: int, sheets: list[int] | None):
    cmd = [str(audiveris), "-batch", "-transcribe", "-export", "-save"]
    cmd += ["-constant", f"org.audiveris.omr.image.ImageLoading.pdfResolution={dpi}"]
    # Default is 120 s per step; pages with many meter changes need longer for RHYTHMS.
    cmd += ["-constant", f"org.audiveris.omr.Main.sheetStepTimeOut={STEP_TIMEOUT_S}"]
    cmd += ["-output", str(work)]
    if sheets:
        cmd += ["-sheets", *map(str, sheets)]
    return subprocess.run(
        [*cmd, "--", str(pdf)],
        check=False,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )


def convert(pdf: Path, audiveris: Path) -> list[Path]:
    work = REFERENCE / "omr"
    work.mkdir(parents=True, exist_ok=True)
    n_pages, dpi = pdf_resolution(pdf)
    # Start from a fresh book: re-processing a book left over from a failed run breaks Audiveris.
    (work / f"{pdf.stem}.omr").unlink(missing_ok=True)
    for old in [
        *REFERENCE.glob(f"{pdf.stem}.omr.mxl"),
        *REFERENCE.glob(f"{pdf.stem}.mvt*.omr.mxl"),
    ]:
        old.unlink()  # results of an earlier run, which may have had different movements
    proc = run_audiveris(audiveris, pdf, work, dpi, None)
    skipped: list[int] = []
    if proc.returncode != 0:
        # One sheet without music (cover, text page) makes the whole book fail: retry without it.
        skipped = sorted({int(m) for m in FAILED_SHEET.findall(proc.stdout)})
        keep = [i for i in range(1, n_pages + 1) if i not in skipped]
        if skipped and keep:
            print(f"  pages without recognizable music, skipped: {skipped}")
            (work / f"{pdf.stem}.omr").unlink(missing_ok=True)
            proc = run_audiveris(audiveris, pdf, work, dpi, keep)
    # A book with several movements is exported as <name>.mvt1.mxl, <name>.mvt2.mxl, ...
    exported = sorted(work.glob(f"{pdf.stem}.mxl")) + sorted(work.glob(f"{pdf.stem}.mvt*.mxl"))
    if proc.returncode != 0 or not exported:
        tail = "\n".join(proc.stdout.splitlines()[-15:] + proc.stderr.splitlines()[-15:])
        raise RuntimeError(f"Audiveris failed on {pdf.name} (exit {proc.returncode}):\n{tail}")
    results = []
    for src in exported:
        suffix = src.name[len(pdf.stem) :].removesuffix(".mxl")  # "" or ".mvt1"
        if suffix == ".mvtnull":  # Audiveris quirk when only some sheets are processed
            suffix = ""
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
