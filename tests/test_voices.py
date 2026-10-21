from fractions import Fraction as F

from audio2score.models import NoteEvent
from audio2score.voices import BASS, UPPER, assign


def qn(beat, pitch, dur=F(1)):
    return NoteEvent(onset=0.0, offset=0.0, pitch=pitch, q_onset=F(beat), q_duration=dur)


def voices_by_pitch(out):
    return [(n.q_onset, n.pitch, n.voice) for n in out]


def test_chord_lowest_note_is_bass():
    out = assign([qn(0, 40), qn(0, 59), qn(0, 64)])
    assert [n.voice for n in out] == [BASS, UPPER, UPPER]


def test_arpeggio_bass_then_melody():
    # p-i-m-a arpeggio: bass on the beat, then upper notes
    notes = [qn(F(k, 2), p) for k, p in enumerate([45, 57, 60, 64, 45, 57, 60, 64])]
    out = assign(notes)
    assert [n.voice for n in out] == [BASS, UPPER, UPPER, UPPER] * 2


def test_close_chord_stays_together():
    out = assign([qn(0, 40), qn(0, 76), qn(1, 60), qn(1, 64), qn(1, 67)])
    upper_chord = [n.voice for n in out if n.q_onset == 1]
    assert len(set(upper_chord)) == 1


def test_empty():
    assert assign([]) == []
