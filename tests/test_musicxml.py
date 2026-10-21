import xml.etree.ElementTree as ET
from fractions import Fraction as F

from audio2score.models import NoteEvent, Transcription
from audio2score.musicxml import Event, split_at_bars, voice_events, write_musicxml
from audio2score.voices import BASS, UPPER


def qn(beat, pitch, dur, voice, string=None, fret=None):
    return NoteEvent(
        onset=0.0, offset=0.0, pitch=pitch, q_onset=F(beat), q_duration=F(dur),
        voice=voice, string=string, fret=fret,
    )  # fmt: skip


def test_voice_events_truncate_and_fill_rests():
    notes = [qn(0, 64, 3, UPPER), qn(1, 67, 1, UPPER), qn(3, 69, 1, UPPER)]
    evs = voice_events(notes, F(4), legato=F(0))
    assert [(e.onset, e.duration, [n.pitch for n in e.notes]) for e in evs] == [
        (0, 1, [64]),
        (1, 1, [67]),
        (2, 1, []),
        (3, 1, [69]),
    ]


def test_split_at_bars_ties():
    measures = split_at_bars([Event(F(3), F(2), [qn(3, 45, 2, BASS)])], F(4))
    first, second = measures[3 // 4][0], measures[1][0]
    assert (first.onset, first.duration, first.tie_start, first.tie_stop) == (3, 1, True, False)
    assert (second.onset, second.duration, second.tie_start, second.tie_stop) == (0, 1, False, True)


def test_write_musicxml_two_voices_with_fingering(tmp_path):
    notes = [
        qn(0, 45, 4, BASS, string=1, fret=0),
        qn(0, 64, 1, UPPER, string=5, fret=0),
        qn(1, 67, 1, UPPER, string=5, fret=3),
        qn(2, 69, 2, UPPER, string=5, fret=5),
        qn(4, 52, 3, BASS, string=2, fret=2),
        qn(4, 59, 1, UPPER, string=4, fret=0),
        qn(4, 64, 1, UPPER, string=5, fret=0),
    ]
    trans = Transcription(notes=notes, tempo_bpm=90.0, time_signature=(4, 4))
    path = write_musicxml(trans, tmp_path / "x.musicxml", title="test", string_numbers=True)
    root = ET.parse(path).getroot()
    measures = root.findall(".//measure")
    assert len(measures) == 2
    assert root.find(".//time/beats").text == "4"
    pitched = [n for n in root.iter("note") if n.find("pitch") is not None]
    assert {n.findtext("voice") for n in pitched} == {"1", "2"}
    # every pitched note got a string/fret mark; MusicXML strings count from the high e = 1
    techs = [(n.findtext(".//string"), n.findtext(".//fret")) for n in pitched]
    assert all(s is not None for s, _ in techs)
    a2 = next(
        n for n in pitched if n.findtext("pitch/step") == "A" and n.findtext("pitch/octave") == "2"
    )
    assert (a2.findtext(".//string"), a2.findtext(".//fret")) == ("5", "0")


def test_write_musicxml_crossing_barline_is_tied(tmp_path):
    notes = [qn(3, 45, 2, BASS, 1, 0), qn(0, 64, 4, UPPER, 5, 0), qn(4, 64, 4, UPPER, 5, 0)]
    path = write_musicxml(Transcription(notes=notes), tmp_path / "t.musicxml")
    root = ET.parse(path).getroot()
    ties = [t.get("type") for n in root.iter("note") for t in n.findall("tie")
            if n.findtext("pitch/step") == "A"]  # fmt: skip
    assert ties == ["start", "stop"]


def test_offbeat_events_split_at_beats():
    # Rest from the last triplet of beat 0 to the first 16th of beat 1 (1/3 + 1/4 = 7/12) has no
    # plain written value; it must be split at the beat line.
    evs = [Event(F(0), F(2, 3), []), Event(F(2, 3), F(7, 12), []), Event(F(5, 4), F(11, 4), [])]
    (bar,) = split_at_bars(evs, F(4))
    assert [(e.onset, e.duration) for e in bar] == [
        (0, F(2, 3)),
        (F(2, 3), F(1, 3)),
        (1, F(1, 4)),
        (F(5, 4), F(3, 4)),
        (2, 2),
    ]


def test_on_beat_note_split_once():
    (bar,) = split_at_bars([Event(F(0), F(5, 2), [qn(0, 64, F(5, 2), UPPER)])], F(4))[:1]
    assert [(e.onset, e.duration, e.tie_start, e.tie_stop) for e in bar[:2]] == [
        (0, 2, True, False),
        (2, F(1, 2), False, True),
    ]


def test_voice_events_legato_fills_short_gaps():
    notes = [qn(0, 64, F(1, 4), UPPER), qn(1, 67, F(1, 4), UPPER), qn(F(7, 2), 69, 1, UPPER)]
    evs = voice_events(notes, F(8))
    assert [(e.onset, e.duration, bool(e.notes)) for e in evs] == [
        (0, 1, True),  # gap of 3/4 filled
        (1, F(1, 4), True),  # gap of 9/4 > 1 beat: stays a rest
        (F(5, 4), F(9, 4), False),
        (F(7, 2), 1, True),
        (F(9, 2), F(7, 2), False),
    ]


def test_string_numbers_off_by_default(tmp_path):
    notes = [qn(0, 64, 4, UPPER, string=5, fret=0)]
    path = write_musicxml(Transcription(notes=notes), tmp_path / "s.musicxml")
    assert ET.parse(path).getroot().find(".//technical") is None
