import math

import pytest

from audio2score.fretting import FretConfig, assign, enumerate_shapes, group_chords, positions
from audio2score.models import NoteEvent


def note(onset, pitch, dur=0.2):
    return NoteEvent(onset=onset, offset=onset + dur, pitch=pitch)


def frets(notes):
    return [(n.string, n.fret) for n in notes]


def test_positions_e4():
    assert positions(64, FretConfig()) == [(1, 19), (2, 14), (3, 9), (4, 5), (5, 0)]


def test_positions_out_of_range():
    cfg = FretConfig()
    assert positions(39, cfg) == []  # below low E
    assert positions(64 + 20, cfg) == []  # above 19th fret on high E


def test_group_chords_by_onset_window():
    notes = [note(0.0, 40), note(0.02, 64), note(0.5, 45), note(0.53, 57), note(0.6, 60)]
    assert group_chords(notes, 0.04) == [[0, 1], [2, 3], [4]]


def test_single_open_note_prefers_open_string():
    out = assign([note(0.0, 64)])
    assert frets(out) == [(5, 0)]


def test_open_e_minor_chord():
    # E2 B2 E3 G3 B3 E4 strummed together -> open Em: 0 2 2 0 0 0
    pitches = [40, 47, 52, 55, 59, 64]
    out = assign([note(0.0, p) for p in pitches])
    assert sorted(frets(out)) == [(0, 0), (1, 2), (2, 2), (3, 0), (4, 0), (5, 0)]


def test_shapes_use_distinct_strings_and_limited_span():
    cfg = FretConfig()
    for shape in enumerate_shapes([48, 52, 55, 60], cfg):  # C major voicing
        strings = [s for s, _ in shape]
        assert len(set(strings)) == len(strings)
        fretted = [f for _, f in shape if f > 0]
        if fretted:
            assert max(fretted) - min(fretted) <= cfg.max_span


def test_alternation_stays_in_position():
    # C5 / G4 alternating. Lowest-fret greedy gives e8, e3, e8, ... (5-fret jumps); staying in
    # 8th position (G4 on B string fret 8) is what a player would do.
    pitches = [72, 67] * 4
    out = assign([note(i * 0.15, p) for i, p in enumerate(pitches)])
    assert {(n.pitch, n.string, n.fret) for n in out} == {(72, 5, 8), (67, 4, 8)}


def test_ringing_bass_not_cut_by_melody():
    # Sustained open A bass (A2) with a melody note above that could sit on the A string.
    # B2 (47) is A-string fret 2 or low-E fret 7; with A ringing it should go to low E.
    bass = NoteEvent(onset=0.0, offset=2.0, pitch=45)
    mel = note(0.5, 47)
    out = assign([bass, mel])
    by_pitch = {n.pitch: (n.string, n.fret) for n in out}
    assert by_pitch[45] == (1, 0)
    assert by_pitch[47] == (0, 7)


def test_unplayable_chord_drops_inner_note_keeps_outer_voices():
    # 7 notes at once cannot fit on 6 strings.
    pitches = [40, 45, 50, 55, 59, 64, 67]
    out = assign([note(0.0, p) for p in pitches])
    placed = [n.pitch for n in out if n.string is not None]
    assert len(placed) == 6
    assert 40 in placed and 67 in placed


def test_out_of_range_note_left_unplaced():
    out = assign([note(0.0, 30), note(0.5, 64)])
    assert out[0].string is None and out[0].fret is None
    assert frets(out[1:]) == [(5, 0)]


def test_drop_d_tuning():
    cfg = FretConfig(tuning=(38, 45, 50, 55, 59, 64))
    out = assign([note(0.0, 38)], cfg)
    assert frets(out) == [(0, 0)]


def test_input_not_mutated():
    notes = [note(0.0, 64)]
    assign(notes)
    assert notes[0].string is None


@pytest.mark.parametrize("p", [1.0, 2.0, math.inf])
def test_playability_norms_all_produce_valid_assignment(p):
    pitches = [40, 52, 55, 59, 45, 57, 60, 64]
    out = assign([note(i * 0.3, x) for i, x in enumerate(pitches)], p=p)
    cfg = FretConfig()
    for n in out:
        assert cfg.tuning[n.string] + n.fret == n.pitch


def test_invalid_p():
    with pytest.raises(ValueError):
        assign([note(0.0, 64)], p=0.5)
