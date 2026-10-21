from fractions import Fraction as F

import numpy as np

from audio2score.models import NoteEvent
from audio2score.rhythm import (
    apply_meter,
    beat_accents,
    estimate_meter,
    quantize,
    seconds_to_beats,
    tempo_bpm,
)

BEATS = np.arange(0.0, 20.0, 0.5)  # 120 BPM


def note(onset, pitch=64, dur=0.2, vel=80):
    return NoteEvent(onset=onset, offset=onset + dur, pitch=pitch, velocity=vel)


def test_tempo():
    assert tempo_bpm(BEATS) == 120.0


def test_seconds_to_beats_interpolates_and_extrapolates():
    beats = np.array([1.0, 1.5, 2.5, 3.0])  # slows down in the middle
    pos = seconds_to_beats(np.array([0.5, 1.25, 2.0, 3.5]), beats)
    assert np.allclose(pos, [-1.0, 0.5, 1.5, 4.0])


def test_quantize_sixteenths_with_timing_jitter():
    onsets = [1.0 + 0.125 * k + j for k, j in enumerate([0.01, -0.012, 0.008, 0.0, -0.01])]
    q = quantize([note(t) for t in onsets], BEATS)
    assert [n.q_onset for n in q] == [F(0), F(1, 4), F(1, 2), F(3, 4), F(1)]


def test_quantize_triplets_when_they_fit():
    onsets = [1.0, 1.0 + 0.5 / 3, 1.0 + 1.0 / 3, 1.5]
    q = quantize([note(t) for t in onsets], BEATS)
    assert [n.q_onset for n in q] == [F(0), F(1, 3), F(2, 3), F(1)]


def test_quantize_durations_have_minimum_length():
    q = quantize([note(1.0, dur=0.01), note(1.0 + 0.5, dur=0.5)], BEATS)
    assert q[0].q_duration == F(1, 4)
    assert q[1].q_duration == F(1)


def test_meter_three_four_from_bass_on_every_third_beat():
    notes = []
    for b in range(24):
        if b % 3 == 1:  # downbeats on beats 1, 4, 7, ... (beat 0 is a pickup)
            notes.append(note(b * 0.5, pitch=40, vel=100))
        notes.append(note(b * 0.5, pitch=64, vel=60))
    q = quantize(notes, BEATS)
    m, phase = estimate_meter(beat_accents(q))
    assert (m, phase) == (3, 1)
    shifted = apply_meter(q, m, phase)
    bass_onsets = {n.q_onset for n in shifted if n.pitch == 40}
    assert all(o % 3 == 0 for o in bass_onsets)


def test_meter_prefers_four_over_two():
    notes = []
    for b in range(32):
        vel = 100 if b % 4 == 0 else 90 if b % 2 == 0 else 50
        notes.append(note(b * 0.5, pitch=40 if b % 2 == 0 else 64, vel=vel))
    m, phase = estimate_meter(beat_accents(quantize(notes, BEATS)))
    assert (m, phase) == (4, 0)


def test_meter_defaults_for_short_input():
    assert estimate_meter(np.zeros(3)) == (4, 0)


def test_each_beat_uses_one_grid():
    # A short note just before beat 1 snaps onto beat 1, which is a triplet beat: its length
    # must be a triplet eighth, not a 16th.
    onsets = [0.49, 0.5 + 0.5 / 3, 0.5 + 1.0 / 3]
    q = quantize([note(t, dur=0.01) for t in onsets], BEATS)
    for n in q:
        for x in (n.q_onset, n.q_onset + n.q_duration):
            assert (x - int(x)) * 3 == int((x - int(x)) * 3)  # on the triplet grid
