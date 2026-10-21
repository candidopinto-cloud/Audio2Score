"""Write note events to output formats."""

from __future__ import annotations

from pathlib import Path

from audio2score.fretting import group_chords
from audio2score.models import STANDARD_TUNING, NoteEvent

FORMATS = ("midi", "tab", "musicxml", "gp5")
IMPLEMENTED = ("midi", "tab")
NYLON_GUITAR_PROGRAM = 24  # General MIDI "Acoustic Guitar (nylon)"
_NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def write_midi(notes: list[NoteEvent], path: str | Path, tempo_bpm: float = 120.0) -> Path:
    import pretty_midi

    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo_bpm)
    inst = pretty_midi.Instrument(program=NYLON_GUITAR_PROGRAM, name="Classical Guitar")
    for n in notes:
        end = max(n.offset, n.onset + 0.01)
        inst.notes.append(pretty_midi.Note(n.velocity, n.pitch, n.onset, end))
    pm.instruments.append(inst)
    path = Path(path)
    pm.write(str(path))
    return path


def string_labels(tuning: tuple[int, ...]) -> list[str]:
    """Names per string, low to high; the top string is lowercased if its name repeats (e/E)."""
    names = [_NOTE_NAMES[p % 12] for p in tuning]
    if names[-1] in names[:-1]:
        names[-1] = names[-1].lower()
    width = max(len(n) for n in names)
    return [n.ljust(width) for n in names]


def render_tab(
    notes: list[NoteEvent],
    tuning: tuple[int, ...] = STANDARD_TUNING,
    chord_window: float = 0.04,
    seconds_per_dash: float = 0.125,
    max_dashes: int = 8,
    line_width: int = 80,
) -> str:
    """ASCII tab, high string on top. Spacing between columns roughly follows onset gaps.

    Unfretted notes (string=None) are skipped. Rhythm is not quantized yet (Milestone 2).
    """
    placed = [n for n in notes if n.string is not None and n.fret is not None]
    labels = string_labels(tuning)
    n_strings = len(tuning)
    chords = group_chords(placed, chord_window)

    # Build columns: each column is a list of per-string cells, low string first.
    columns: list[list[str]] = []
    prev_onset: float | None = None
    for chord in chords:
        onset = placed[chord[0]].onset
        if prev_onset is not None:
            gap = round((onset - prev_onset) / seconds_per_dash)
            columns.extend([["-"] * n_strings for _ in range(max(1, min(gap, max_dashes)))])
        cells = ["-"] * n_strings
        for i in chord:
            cells[placed[i].string] = str(placed[i].fret)
        width = max(len(c) for c in cells)
        columns.append([c.ljust(width, "-") for c in cells])
        prev_onset = onset

    # Wrap into systems of at most line_width characters.
    fixed = len(labels[0]) + 4  # "e|-" before the body, "-|" after
    systems: list[list[list[str]]] = [[]]
    used = 0
    for col in columns:
        w = len(col[0])
        if systems[-1] and fixed + used + w > line_width:
            systems.append([])
            used = 0
        systems[-1].append(col)
        used += w

    blocks = []
    for system in systems:
        lines = []
        for s in reversed(range(n_strings)):
            body = "".join(col[s] for col in system)
            lines.append(f"{labels[s]}|-{body}-|")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks) + "\n"


def write_tab(notes: list[NoteEvent], path: str | Path, **kwargs) -> Path:
    path = Path(path)
    path.write_text(render_tab(notes, **kwargs), encoding="utf-8")
    return path


def write_all(
    notes: list[NoteEvent],
    outdir: str | Path,
    stem: str,
    formats: list[str],
    tuning: tuple[int, ...] = STANDARD_TUNING,
) -> list[Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in formats:
        if fmt == "midi":
            written.append(write_midi(notes, outdir / f"{stem}.mid"))
        elif fmt == "tab":
            written.append(write_tab(notes, outdir / f"{stem}.tab.txt", tuning=tuning))
        elif fmt in ("musicxml", "gp5"):
            raise NotImplementedError(f"{fmt} export is not implemented yet (see docs/PLAN.md)")
        else:
            raise ValueError(f"unknown format {fmt!r}; choose from {FORMATS}")
    return written
