import pretty_midi
import pytest

from audio2score.export import render_tab, string_labels, write_all, write_midi
from audio2score.models import NoteEvent


def fretted(onset, pitch, string, fret, dur=0.25):
    return NoteEvent(onset=onset, offset=onset + dur, pitch=pitch, string=string, fret=fret)


def test_string_labels_standard():
    assert string_labels((40, 45, 50, 55, 59, 64)) == ["E", "A", "D", "G", "B", "e"]


def test_string_labels_drop_d_pads_width():
    labels = string_labels((38, 45, 50, 55, 59, 64))
    assert [label.strip() for label in labels] == ["D", "A", "D", "G", "B", "E"]


def test_render_tab_chord_and_melody():
    notes = [
        fretted(0.0, 40, 0, 0),
        fretted(0.0, 64, 5, 0),
        fretted(0.25, 71, 4, 12),
    ]
    tab = render_tab(notes)
    lines = tab.strip().splitlines()
    assert len(lines) == 6
    # 0.25 s gap at 0.125 s/dash -> 2 spacer dashes; "12" widens its column on every string.
    assert lines[0] == "e|-0-----|"
    assert lines[1] == "B|----12-|"
    assert lines[5] == "E|-0-----|"
    assert len({len(line) for line in lines}) == 1


def test_render_tab_wraps_long_lines():
    notes = [fretted(i * 0.25, 64, 5, 0) for i in range(100)]
    tab = render_tab(notes, line_width=40)
    systems = tab.strip().split("\n\n")
    assert len(systems) > 1
    assert all(len(line) <= 40 for line in tab.splitlines())


def test_render_tab_skips_unplaced_notes():
    notes = [NoteEvent(onset=0.0, offset=0.5, pitch=30), fretted(0.5, 64, 5, 0)]
    tab = render_tab(notes)
    assert tab.splitlines()[0] == "e|-0-|"


def test_midi_roundtrip(tmp_path):
    notes = [fretted(0.0, 40, 0, 0, dur=0.5), fretted(0.5, 64, 5, 0, dur=0.5)]
    path = write_midi(notes, tmp_path / "x.mid")
    pm = pretty_midi.PrettyMIDI(str(path))
    got = [(n.pitch, round(n.start, 3), round(n.end, 3)) for n in pm.instruments[0].notes]
    assert got == [(40, 0.0, 0.5), (64, 0.5, 1.0)]
    assert pm.instruments[0].program == 24


def test_write_all(tmp_path):
    notes = [fretted(0.0, 64, 5, 0)]
    paths = write_all(notes, tmp_path / "out", "song", ["midi", "tab"])
    assert [p.name for p in paths] == ["song.mid", "song.tab.txt"]
    assert all(p.is_file() for p in paths)


def test_write_all_unimplemented_format(tmp_path):
    with pytest.raises(NotImplementedError):
        write_all([], tmp_path, "song", ["gp5"])
