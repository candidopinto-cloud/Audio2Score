import numpy as np

from audio2score.evaluate import RefNote, score_notes
from audio2score.models import NoteEvent


def synthetic_piece(n_beats=120, seed=0):
    rng = np.random.default_rng(seed)
    ref = []
    for b in range(n_beats):
        ref.append(RefNote(b, 1.0, int(rng.choice([40, 45, 47, 52]))))  # bass on every beat
        for k in range(2):  # melody in eighths
            ref.append(RefNote(b + k / 2, 0.5, int(rng.integers(60, 77))))
    return ref


def perform(ref, written_octave_up=True, seed=1):
    """Rubato: tempo drifts between 80 and 120 BPM; onsets jittered by ±10 ms."""
    rng = np.random.default_rng(seed)
    beats = np.arange(0, 200)
    sec_per_beat = 60 / (100 + 20 * np.sin(beats / 9))
    beat_times = np.concatenate([[0.0], np.cumsum(sec_per_beat)])
    out = []
    for n in ref:
        t = np.interp(n.onset, np.arange(len(beat_times)), beat_times) + rng.normal(0, 0.01)
        pitch = n.pitch - 12 if written_octave_up else n.pitch
        out.append(NoteEvent(onset=float(t), offset=float(t) + 0.3, pitch=pitch))
    return out


def test_alignment_recovers_rubato_performance():
    ref = synthetic_piece()
    res = score_notes(ref, perform(ref))
    assert res.f1 > 0.9
    assert res.octave_shift == -12  # written an octave above sounding pitch


def test_missing_notes_lower_recall_not_precision():
    ref = synthetic_piece()
    est = perform(ref, written_octave_up=False)
    est = [n for i, n in enumerate(est) if i % 5 != 0]  # drop 20%
    res = score_notes(ref, est, tolerance=0.1)
    assert res.octave_shift == 0
    assert 0.7 < res.recall < 0.85
    assert res.precision > 0.9
