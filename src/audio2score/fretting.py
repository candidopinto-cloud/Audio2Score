"""Assign (string, fret) to every note with a polyphonic Viterbi over chord shapes.

Notes whose onsets fall within `chord_window` of each other form one chord. For each chord we
enumerate playable shapes (one note per string, limited fret span), then pick the sequence of
shapes minimising shape difficulty + hand movement + collisions with still-ringing strings.

Step costs are combined with an Lp norm: p=1 is the plain sum, larger p penalises the single
hardest moment more (p=inf minimises the worst step). Minimising sum(c**p) is equivalent to
minimising the Lp norm, so the DP stays a standard Viterbi.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, replace

from audio2score.models import STANDARD_TUNING, NoteEvent

Shape = tuple[tuple[int, int], ...]  # (string, fret) per kept chord note, same order as pitches


@dataclass(frozen=True)
class FretConfig:
    tuning: tuple[int, ...] = STANDARD_TUNING
    max_fret: int = 19  # classical guitar
    max_span: int = 4  # max distance between lowest and highest fretted note in one shape
    chord_window: float = 0.04  # seconds; onsets closer than this form one chord
    max_candidates: int = 24  # beam: keep the K cheapest shapes per chord
    w_span: float = 1.0  # per fret of stretch within a shape
    w_height: float = 0.1  # per fret of hand position (mild preference for low positions)
    w_fretted: float = 0.2  # per fretted (non-open) note
    w_move: float = 0.5  # per fret of hand shift between consecutive chords
    w_ring: float = 3.0  # per note that cuts off a different note still ringing on that string


def group_chords(notes: list[NoteEvent], window: float) -> list[list[int]]:
    """Group indices of `notes` (any order) into chords by onset proximity to the chord's first note."""
    order = sorted(range(len(notes)), key=lambda i: (notes[i].onset, notes[i].pitch))
    chords: list[list[int]] = []
    for i in order:
        if chords and notes[i].onset - notes[chords[-1][0]].onset <= window:
            chords[-1].append(i)
        else:
            chords.append([i])
    return chords


def positions(pitch: int, cfg: FretConfig) -> list[tuple[int, int]]:
    """All (string, fret) pairs that produce `pitch`."""
    out = []
    for s, open_pitch in enumerate(cfg.tuning):
        fret = pitch - open_pitch
        if 0 <= fret <= cfg.max_fret:
            out.append((s, fret))
    return out


def hand_position(shape: Shape) -> int | None:
    """Lowest fretted fret, or None if the shape uses only open strings."""
    fretted = [f for _, f in shape if f > 0]
    return min(fretted) if fretted else None


def shape_cost(shape: Shape, cfg: FretConfig) -> float:
    fretted = [f for _, f in shape if f > 0]
    if not fretted:
        return 0.0
    span = max(fretted) - min(fretted)
    return cfg.w_span * span + cfg.w_height * min(fretted) + cfg.w_fretted * len(fretted)


def enumerate_shapes(pitches: list[int], cfg: FretConfig) -> list[Shape]:
    """Playable shapes for `pitches`, cheapest first, at most cfg.max_candidates."""
    options = [positions(p, cfg) for p in pitches]
    shapes: list[Shape] = []

    def rec(k: int, used: frozenset[int], chosen: list[tuple[int, int]], lo: int, hi: int):
        if k == len(pitches):
            shapes.append(tuple(chosen))
            return
        for s, f in options[k]:
            if s in used:
                continue
            nlo, nhi = (min(lo, f), max(hi, f)) if f > 0 else (lo, hi)
            if f > 0 and nhi - nlo > cfg.max_span:
                continue
            chosen.append((s, f))
            rec(k + 1, used | {s}, chosen, nlo, nhi)
            chosen.pop()

    rec(0, frozenset(), [], math.inf, -math.inf)
    shapes.sort(key=lambda sh: shape_cost(sh, cfg))
    return shapes[: cfg.max_candidates]


def _playable_subset(pitches: list[int], cfg: FretConfig) -> tuple[list[int], list[Shape]]:
    """Indices of the largest playable subset of `pitches` (dropping inner voices first)."""
    idx = [i for i, p in enumerate(pitches) if positions(p, cfg)]  # in instrument range
    n = len(idx)
    for drop in range(n):
        # Prefer keeping the outer voices: try removing inner notes before bass/melody.
        removal_order = idx[1:-1] + idx[:1] + idx[-1:] if n > 2 else idx
        for removed in itertools.combinations(removal_order, drop):
            keep = [i for i in idx if i not in removed]
            shapes = enumerate_shapes([pitches[i] for i in keep], cfg)
            if shapes:
                return keep, shapes
    return [], []


def _transition_cost(
    prev_shape: Shape,
    prev_notes: list[NoteEvent],
    shape: Shape,
    notes: list[NoteEvent],
    cfg: FretConfig,
) -> float:
    cost = 0.0
    a, b = hand_position(prev_shape), hand_position(shape)
    if a is not None and b is not None:
        cost += cfg.w_move * abs(a - b)
    onset = notes[0].onset
    ringing = {
        s: n.pitch
        for (s, _), n in zip(prev_shape, prev_notes, strict=True)
        if n.offset > onset + cfg.chord_window
    }
    for (s, _), n in zip(shape, notes, strict=True):
        if s in ringing and ringing[s] != n.pitch:
            cost += cfg.w_ring
    return cost


def assign(
    notes: list[NoteEvent], cfg: FretConfig | None = None, p: float = 1.0
) -> list[NoteEvent]:
    """Return copies of `notes` (sorted by onset) with `string`/`fret` set.

    Notes that cannot be placed (out of range, or too many in one chord) keep string=None.
    """
    cfg = cfg or FretConfig()
    if p < 1:
        raise ValueError("playability p must be >= 1")
    notes = sorted(notes, key=lambda n: (n.onset, n.pitch))
    chords = group_chords(notes, cfg.chord_window)

    # Per chord: kept note indices (into `notes`) and their candidate shapes.
    steps: list[tuple[list[int], list[Shape]]] = []
    for chord in chords:
        chord.sort(key=lambda i: notes[i].pitch)
        keep_local, shapes = _playable_subset([notes[i].pitch for i in chord], cfg)
        if shapes:
            steps.append(([chord[k] for k in keep_local], shapes))

    if not steps:
        return [replace(n) for n in notes]

    def combine(acc: float, step: float) -> float:
        return max(acc, step) if math.isinf(p) else acc + step**p

    # Viterbi
    first_shapes = steps[0][1]
    score = [combine(0.0, shape_cost(sh, cfg)) for sh in first_shapes]
    back: list[list[int]] = [[-1] * len(first_shapes)]
    for t in range(1, len(steps)):
        prev_idx, prev_shapes = steps[t - 1]
        cur_idx, cur_shapes = steps[t]
        prev_notes = [notes[i] for i in prev_idx]
        cur_notes = [notes[i] for i in cur_idx]
        new_score, ptr = [], []
        for sh in cur_shapes:
            base = shape_cost(sh, cfg)
            best, best_j = math.inf, -1
            for j, psh in enumerate(prev_shapes):
                step = base + _transition_cost(psh, prev_notes, sh, cur_notes, cfg)
                total = combine(score[j], step)
                if total < best:
                    best, best_j = total, j
            new_score.append(best)
            ptr.append(best_j)
        score = new_score
        back.append(ptr)

    # Backtrack
    j = min(range(len(score)), key=score.__getitem__)
    chosen: list[Shape] = [()] * len(steps)
    for t in range(len(steps) - 1, -1, -1):
        chosen[t] = steps[t][1][j]
        j = back[t][j]

    out = [replace(n) for n in notes]
    for (idx, _), shape in zip(steps, chosen, strict=True):
        for i, (s, f) in zip(idx, shape, strict=True):
            out[i].string, out[i].fret = s, f
    return out
