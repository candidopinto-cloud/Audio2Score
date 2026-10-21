"""Assign (string, fret) to every note with a polyphonic Viterbi over chord shapes.

Notes whose onsets fall within `chord_window` of each other form one chord. For each chord we
enumerate candidates: a subset of its notes plus a playable shape for them (one note per string,
limited fret span). Leaving a note out costs something proportional to its loudness, and much
less if it looks like an overtone of a louder note (octave, 12th or double octave above). This
lets transcription artefacts be dropped instead of dragging a whole chord up the neck. Dropped
notes keep string=None: they stay in the MIDI but not in the tab.

The Viterbi then picks the sequence of candidates minimising drop cost + shape difficulty
(stretch, height on the neck) + hand shifts + collisions with still-ringing strings. A shift
beyond the hand's reach has a fixed cost plus a small per-fret cost (so there is no incentive to
stop at a halfway position). The hand position is carried through open-string chords (they don't
teleport the hand), and shift cost shrinks with the time since the hand last fretted something.

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
OVERTONE_INTERVALS = (12, 19, 24)  # octave, octave + fifth, two octaves


@dataclass(frozen=True)
class FretConfig:
    tuning: tuple[int, ...] = STANDARD_TUNING
    max_fret: int = 19  # classical guitar
    max_span: int = 4  # max distance between lowest and highest fretted note in one shape
    chord_window: float = 0.04  # seconds; onsets closer than this form one chord
    max_candidates: int = 32  # beam: keep the K cheapest candidates per chord
    w_span: float = 1.0  # per fret of stretch within a shape
    w_height: float = 0.15  # per fret of hand position
    high_fret: int = 7  # above this fret, each extra fret of hand position costs w_high more
    w_high: float = 0.3
    w_fretted: float = 0.2  # per fretted (non-open) note
    reach: int = 2  # hand-position changes up to this many frets need no real shift
    w_shift: float = 1.5  # fixed cost of a shift beyond `reach`
    w_move: float = 0.15  # per fret of position change
    move_relax: float = 0.5  # seconds; movement cost is divided by (1 + elapsed / move_relax)
    w_ring: float = 3.0  # per note that cuts off a different note still ringing on that string
    w_drop: float = 6.0  # cost of leaving out a note: w_drop * (0.5 + 0.5 * velocity / 127)
    outer_drop_factor: float = 1.5  # bass and top notes are more costly to drop
    overtone_drop_factor: float = 0.3  # likely overtones are cheap to drop
    overtone_window: float = 0.05  # seconds; onset tolerance for overtone detection
    max_extra_drops: int = 2  # per chord, beyond what is needed to make it playable at all


@dataclass(frozen=True)
class Candidate:
    keep: tuple[int, ...]  # indices into the sorted note list, ascending pitch
    shape: Shape
    cost: float  # shape cost + drop cost


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
    pos = min(fretted)
    return (
        cfg.w_span * (max(fretted) - pos)
        + cfg.w_height * pos
        + cfg.w_high * max(0, pos - cfg.high_fret)
        + cfg.w_fretted * len(fretted)
    )


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


def overtone_flags(notes: list[NoteEvent], cfg: FretConfig) -> list[bool]:
    """True for notes that start with a louder note an octave/12th/2 octaves below."""
    flags = [False] * len(notes)
    order = sorted(range(len(notes)), key=lambda i: notes[i].onset)
    lo = 0
    for i in order:
        n = notes[i]
        while notes[order[lo]].onset < n.onset - cfg.overtone_window:
            lo += 1
        for j in order[lo:]:
            m = notes[j]
            if m.onset > n.onset + cfg.overtone_window:
                break
            if n.pitch - m.pitch in OVERTONE_INTERVALS and m.velocity > n.velocity:
                flags[i] = True
                break
    return flags


def _chord_candidates(
    chord: list[int], notes: list[NoteEvent], overtone: list[bool], cfg: FretConfig
) -> list[Candidate]:
    """Candidates for one chord (indices sorted by pitch), cheapest first."""
    playable = [i for i in chord if positions(notes[i].pitch, cfg)]  # in instrument range
    if not playable:
        return []

    def drop_cost(i: int) -> float:
        c = cfg.w_drop * (0.5 + 0.5 * notes[i].velocity / 127)
        if i in (playable[0], playable[-1]):
            c *= cfg.outer_drop_factor
        if overtone[i]:
            c *= cfg.overtone_drop_factor
        return c

    cands: list[Candidate] = []
    first_feasible: int | None = None
    for k in range(len(playable) + 1):
        if first_feasible is not None and k > first_feasible + cfg.max_extra_drops:
            break
        for removed in itertools.combinations(playable, k):
            keep = tuple(i for i in playable if i not in removed)
            if keep:
                shapes = enumerate_shapes([notes[i].pitch for i in keep], cfg)
            elif all(overtone[i] for i in removed):
                shapes = [()]  # a chord made only of overtones may vanish entirely
            else:
                continue
            if not shapes:
                continue
            if first_feasible is None:
                first_feasible = k
            dc = sum(drop_cost(i) for i in removed)
            cands.extend(Candidate(keep, sh, shape_cost(sh, cfg) + dc) for sh in shapes)
    cands.sort(key=lambda c: c.cost)
    return cands[: cfg.max_candidates]


def _move_cost(a: int, b: int, elapsed: float, cfg: FretConfig) -> float:
    d = abs(a - b)
    cost = cfg.w_move * d + (cfg.w_shift if d > cfg.reach else 0.0)
    return cost / (1 + elapsed / cfg.move_relax)


def _ring_cost(prev: Candidate, cur: Candidate, notes: list[NoteEvent], cfg: FretConfig) -> float:
    if not cur.keep:
        return 0.0
    onset = notes[cur.keep[0]].onset
    ringing = {
        s: notes[i].pitch
        for (s, _), i in zip(prev.shape, prev.keep, strict=True)
        if notes[i].offset > onset + cfg.chord_window
    }
    return cfg.w_ring * sum(
        1
        for (s, _), i in zip(cur.shape, cur.keep, strict=True)
        if s in ringing and ringing[s] != notes[i].pitch
    )


def assign(
    notes: list[NoteEvent], cfg: FretConfig | None = None, p: float = 1.0
) -> list[NoteEvent]:
    """Return copies of `notes` (sorted by onset) with `string`/`fret` set.

    Notes left out of the tab (out of range, unplayable, or dropped as likely overtones) keep
    string=None.
    """
    cfg = cfg or FretConfig()
    if p < 1:
        raise ValueError("playability p must be >= 1")
    notes = sorted(notes, key=lambda n: (n.onset, n.pitch))
    overtone = overtone_flags(notes, cfg)

    steps: list[tuple[float, list[Candidate]]] = []  # (onset, candidates) per chord
    for chord in group_chords(notes, cfg.chord_window):
        chord.sort(key=lambda i: notes[i].pitch)
        cands = _chord_candidates(chord, notes, overtone, cfg)
        if cands:
            steps.append((notes[chord[0]].onset, cands))

    if not steps:
        return [replace(n) for n in notes]

    def combine(acc: float, step: float) -> float:
        return max(acc, step) if math.isinf(p) else acc + step**p

    # Viterbi. Besides the score, each state remembers the hand position and the time it was
    # last fretting along its best path, so open-string chords don't reset the hand.
    first = steps[0][1]
    score = [combine(0.0, c.cost) for c in first]
    hand = [hand_position(c.shape) for c in first]
    hand_time = [steps[0][0]] * len(first)
    back: list[list[int]] = [[-1] * len(first)]
    for t in range(1, len(steps)):
        onset, cur = steps[t]
        prev = steps[t - 1][1]
        new_score, new_hand, new_time, ptr = [], [], [], []
        for c in cur:
            pos = hand_position(c.shape)
            best, best_j = math.inf, -1
            for j, pc in enumerate(prev):
                step = c.cost + _ring_cost(pc, c, notes, cfg)
                if pos is not None and hand[j] is not None:
                    step += _move_cost(hand[j], pos, onset - hand_time[j], cfg)
                total = combine(score[j], step)
                if total < best:
                    best, best_j = total, j
            new_score.append(best)
            ptr.append(best_j)
            if pos is None:
                new_hand.append(hand[best_j])
                new_time.append(hand_time[best_j])
            else:
                new_hand.append(pos)
                new_time.append(onset)
        score, hand, hand_time = new_score, new_hand, new_time
        back.append(ptr)

    # Backtrack
    j = min(range(len(score)), key=score.__getitem__)
    chosen: list[Candidate] = [first[0]] * len(steps)
    for t in range(len(steps) - 1, -1, -1):
        chosen[t] = steps[t][1][j]
        j = back[t][j]

    out = [replace(n) for n in notes]
    for c in chosen:
        for i, (s, f) in zip(c.keep, c.shape, strict=True):
            out[i].string, out[i].fret = s, f
    return out
