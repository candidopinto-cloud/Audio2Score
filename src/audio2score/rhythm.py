"""Tempo, beats, meter and quantization: seconds -> positions in quarter notes.

Beat tracking (librosa for now; Beat This! later) gives beat times that follow rubato. Note times
are mapped onto beats by piecewise-linear interpolation, then each beat picks the subdivision
grid (16ths or eighth-note triplets) that fits its onsets best. The meter is guessed from where
strong bass notes fall. Everything after `track_beats` is pure logic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from fractions import Fraction

import numpy as np

from audio2score.models import NoteEvent, Transcription


@dataclass(frozen=True)
class RhythmConfig:
    subdivisions: tuple[int, ...] = (4, 3)  # per beat: 16ths, eighth-note triplets
    triplet_penalty: float = 0.03  # in beats; triplets must fit clearly better to be chosen
    meters: tuple[int, ...] = (2, 3, 4)  # beats per bar to consider
    prefer_four: float = 0.8  # choose 4/4 over 2/4 unless 2/4 scores this much better
    bass_pitch: int = 52  # lowest note of an onset at/below E3 counts as a bass accent
    bass_weight: float = 2.0


def track_beats(audio: np.ndarray, sr: int, start_bpm: float | None = None) -> np.ndarray:
    """Beat times in seconds."""
    import librosa

    _, beats = librosa.beat.beat_track(
        y=audio, sr=sr, units="time", start_bpm=start_bpm or 120.0, trim=False
    )
    beats = np.asarray(beats, dtype=float)
    if len(beats) < 4:  # nothing usable (e.g. very free playing): constant grid
        period = 60.0 / (start_bpm or 120.0)
        beats = np.arange(0.0, len(audio) / sr + period, period)
    return beats


def tempo_bpm(beats: np.ndarray) -> float:
    return float(60.0 / np.median(np.diff(beats)))


def seconds_to_beats(times: np.ndarray, beats: np.ndarray) -> np.ndarray:
    """Fractional beat index for each time; linear extrapolation outside the tracked beats."""
    times = np.asarray(times, dtype=float)
    idx = np.arange(len(beats), dtype=float)
    pos = np.interp(times, beats, idx)
    first_period = beats[1] - beats[0]
    last_period = beats[-1] - beats[-2]
    before = times < beats[0]
    after = times > beats[-1]
    pos[before] = (times[before] - beats[0]) / first_period
    pos[after] = idx[-1] + (times[after] - beats[-1]) / last_period
    return pos


def _snap(x: float, sub: int) -> Fraction:
    return Fraction(round(x * sub), sub)


def quantize(
    notes: list[NoteEvent], beats: np.ndarray, cfg: RhythmConfig | None = None
) -> list[NoteEvent]:
    """Copies of `notes` with q_onset/q_duration in beats; beat 0 is the beat containing the first onset."""
    cfg = cfg or RhythmConfig()
    if not notes:
        return []
    on = seconds_to_beats(np.array([n.onset for n in notes]), beats)
    off = seconds_to_beats(np.array([n.offset for n in notes]), beats)
    origin = math.floor(on.min())
    on -= origin
    off -= origin

    # Pick a subdivision per beat from the onsets inside it.
    by_beat: dict[int, list[float]] = {}
    for x in on:
        by_beat.setdefault(math.floor(x), []).append(x - math.floor(x))

    def grid_cost(fracs: list[float], sub: int) -> float:
        err = float(np.mean([abs(f * sub - round(f * sub)) / sub for f in fracs]))
        return err + (cfg.triplet_penalty if sub % 3 == 0 else 0.0)

    sub_of = {k: min(cfg.subdivisions, key=lambda s: grid_cost(fr, s)) for k, fr in by_beat.items()}
    default_sub = cfg.subdivisions[0]

    out = []
    for n, a, b in zip(notes, on, off, strict=True):
        sub = sub_of[math.floor(a)]
        q_on = math.floor(a) + _snap(a - math.floor(a), sub)
        end_sub = sub_of.get(math.floor(b), default_sub)
        q_off = math.floor(b) + _snap(b - math.floor(b), end_sub)
        # An onset can snap forward into the next beat; the minimum length must then follow that
        # beat's grid, or one beat would mix 16ths and triplets.
        min_len = Fraction(1, sub_of.get(math.floor(q_on), default_sub))
        q_dur = max(q_off - q_on, min_len)
        out.append(replace(n, q_onset=q_on, q_duration=q_dur))
    return out


def beat_accents(notes: list[NoteEvent], cfg: RhythmConfig | None = None) -> np.ndarray:
    """Accent strength per integer beat, from notes starting exactly on the beat."""
    cfg = cfg or RhythmConfig()
    on_beat: dict[int, list[NoteEvent]] = {}
    for n in notes:
        if n.q_onset is not None and n.q_onset.denominator == 1:
            on_beat.setdefault(int(n.q_onset), []).append(n)
    if not on_beat:
        return np.zeros(0)
    acc = np.zeros(max(on_beat) + 1)
    for k, group in on_beat.items():
        low = min(group, key=lambda n: n.pitch)
        for n in group:
            w = cfg.bass_weight if n is low and n.pitch <= cfg.bass_pitch else 1.0
            acc[k] += w * n.velocity
    return acc


def estimate_meter(accents: np.ndarray, cfg: RhythmConfig | None = None) -> tuple[int, int]:
    """(beats_per_bar, phase): downbeats fall on beat indices k with k % beats_per_bar == phase."""
    cfg = cfg or RhythmConfig()
    if len(accents) < 8 or accents.mean() == 0:
        return 4, 0
    mean = accents.mean()

    def score(m: int, ph: int) -> float:
        return float(accents[ph::m].mean() / mean - 1.0)

    best = {m: max(range(m), key=lambda ph, m=m: score(m, ph)) for m in cfg.meters}
    m = max(cfg.meters, key=lambda m: score(m, best[m]))
    if m == 2 and 4 in cfg.meters:
        ph4 = max((best[2], best[2] + 2), key=lambda ph: score(4, ph))
        if score(4, ph4) >= cfg.prefer_four * score(2, best[2]):
            return 4, ph4
    return m, best[m]


def apply_meter(notes: list[NoteEvent], beats_per_bar: int, phase: int) -> list[NoteEvent]:
    """Shift positions so downbeats land on multiples of the bar length (pickup becomes rests)."""
    shift = (beats_per_bar - phase) % beats_per_bar
    return [replace(n, q_onset=n.q_onset + shift) for n in notes]


def run(
    audio: np.ndarray,
    sr: int,
    notes: list[NoteEvent],
    time_signature: tuple[int, int] | None = None,
    start_bpm: float | None = None,
    cfg: RhythmConfig | None = None,
) -> Transcription:
    """Track beats, quantize `notes` and place bar lines. Positions are in quarter notes."""
    cfg = cfg or RhythmConfig()
    beats = track_beats(audio, sr, start_bpm)
    q = quantize(notes, beats, cfg)
    if time_signature is None:
        m, phase = estimate_meter(beat_accents(q, cfg), cfg)
        time_signature = (m, 4)
    else:
        m = time_signature[0]
        _, phase = estimate_meter(beat_accents(q, cfg), replace(cfg, meters=(m,)))
    q = apply_meter(q, m, phase)
    return Transcription(
        notes=q, tempo_bpm=tempo_bpm(beats), beats=list(beats), time_signature=time_signature
    )
