"""Note-level evaluation against a reference score that has no timing (MusicXML / OMR output).

A score gives positions in quarter notes, a recording in seconds, and performers bend tempo, so
the reference is first aligned to the transcription: both are rendered as pitch-class activity
over time and matched with dynamic time warping. The warping path maps every score position to a
time in the recording; then mir_eval counts matching notes (onset within tolerance, same pitch).

Caveat: the alignment uses the transcription itself, which flatters it somewhat (a fairly
consistent transcription error can pull the alignment along). Treat scores as relative, for
comparing backends and settings, not as absolute accuracy.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from audio2score.models import NoteEvent

FRAME = 0.05  # seconds per frame for alignment
DECAY = 0.5  # seconds; plucked notes fade, so weight each note by exp(-t / DECAY)


@dataclass
class RefNote:
    onset: float  # quarter notes from the start
    duration: float
    pitch: int


@dataclass
class Result:
    precision: float
    recall: float
    f1: float
    n_ref: int
    n_est: int
    octave_shift: int  # semitones applied to the reference (written guitar music is an 8ve up)
    tolerance: float


def load_reference(paths: list[Path]) -> list[RefNote]:
    """Notes from one or more MusicXML/MIDI files, concatenated in order (e.g. OMR movements)."""
    import music21 as m21

    notes: list[RefNote] = []
    start = 0.0
    for path in paths:
        score = m21.converter.parse(str(path))
        try:
            score = score.expandRepeats()
        except m21.repeat.ExpanderException as e:  # OMR output often has unmatched repeats
            warnings.warn(f"{path.name}: repeats not expanded ({e})", stacklevel=2)
        flat = score.stripTies().flatten()
        length = 0.0
        for el in flat.notes:
            if el.duration.isGrace:
                continue
            on = float(el.offset)
            dur = float(el.quarterLength)
            length = max(length, on + dur)
            for p in el.pitches:
                notes.append(RefNote(start + on, dur, p.midi))
        start += max(length, float(flat.highestTime))
    notes.sort(key=lambda n: (n.onset, n.pitch))
    return notes


def chroma_roll(onsets, durations, pitches, n_frames: int, frame: float) -> np.ndarray:
    """(n_frames, 12) pitch-class activity with plucked-string decay, L2-normalised per frame."""
    roll = np.zeros((n_frames, 12))
    t = np.arange(n_frames) * frame
    for on, dur, p in zip(onsets, durations, pitches, strict=True):
        a, b = int(on / frame), min(n_frames, int((on + max(dur, frame)) / frame) + 1)
        if a >= n_frames:
            continue
        roll[a:b, p % 12] += np.exp(-(t[a:b] - on) / DECAY)
    norm = np.linalg.norm(roll, axis=1, keepdims=True)
    return roll / np.maximum(norm, 1e-9)


def align(ref: list[RefNote], est: list[NoteEvent]) -> np.ndarray:
    """Map reference onsets (quarter notes) to seconds in the recording. Returns onset times."""
    import librosa

    est_len = max(n.offset for n in est)
    ref_len = max(n.onset + n.duration for n in ref)
    sec_per_q = est_len / ref_len  # nominal tempo so both sequences have similar length
    n_est = int(est_len / FRAME) + 1
    n_ref = int(ref_len * sec_per_q / FRAME) + 1
    e = chroma_roll(
        [n.onset for n in est],
        [n.offset - n.onset for n in est],
        [n.pitch for n in est],
        n_est,
        FRAME,
    )
    r = chroma_roll(
        [n.onset * sec_per_q for n in ref],
        [n.duration * sec_per_q for n in ref],
        [n.pitch for n in ref],
        n_ref,
        FRAME,
    )
    cost = 1.0 - r @ e.T  # cosine distance; silent frames get cost 1 everywhere
    _, path = librosa.sequence.dtw(C=cost, backtrack=True)
    path = path[::-1]  # ascending
    # For each reference frame take the mean matched recording frame, then interpolate.
    ref_frames, idx = np.unique(path[:, 0], return_index=True)
    counts = np.diff(np.append(idx, len(path)))
    sums = np.add.reduceat(path[:, 1], idx)
    est_frames = sums / counts
    ref_onsets = np.array([n.onset * sec_per_q / FRAME for n in ref])
    return np.interp(ref_onsets, ref_frames, est_frames) * FRAME


def score_notes(ref: list[RefNote], est: list[NoteEvent], tolerance: float = 0.05) -> Result:
    """Align, then note F1 (onset within `tolerance` s, pitch within 50 cents, offsets ignored).

    Tries reference octave shifts of -12/0/+12 (guitar is written an octave above sounding pitch;
    OMR and MusicXML exports differ in whether that is applied) and keeps the best.
    """
    import mir_eval

    times = align(ref, est)
    # Each reference note lasts until the next reference onset in the aligned timeline (only
    # needed because mir_eval wants intervals; offsets are not scored).
    ref_iv = np.stack([times, times + 0.1], axis=1)
    est_iv = np.array([[n.onset, max(n.offset, n.onset + 0.01)] for n in est])
    est_hz = mir_eval.util.midi_to_hz(np.array([n.pitch for n in est], dtype=float))
    best: Result | None = None
    for shift in (0, -12, 12):
        ref_hz = mir_eval.util.midi_to_hz(np.array([n.pitch + shift for n in ref], dtype=float))
        p, r, f, _ = mir_eval.transcription.precision_recall_f1_overlap(
            ref_iv, ref_hz, est_iv, est_hz, onset_tolerance=tolerance, offset_ratio=None
        )
        res = Result(p, r, f, len(ref), len(est), shift, tolerance)
        if best is None or res.f1 > best.f1:
            best = res
    return best
