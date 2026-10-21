"""MusicXML export (music21): one guitar staff, upper voice stems up, bass voice stems down.

Needs notes with q_onset/q_duration (rhythm stage) and voice (voices stage). Within a voice,
notes are held until the next note when the gap is short (guitar notes ring; transcribed offsets
are early), cut where the next note starts, and longer gaps become rests. Notes crossing a bar
line are split and tied. Optionally, string/fret are written as <technical> marks (MuseScore
shows them as circled string numbers).
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

from audio2score.models import NoteEvent, Transcription
from audio2score.voices import BASS, UPPER

XML_VOICE = {UPPER: "1", BASS: "2"}
STEM = {UPPER: "up", BASS: "down"}


@dataclass
class Event:
    onset: Fraction
    duration: Fraction
    notes: list[NoteEvent]  # empty = rest
    tie_start: bool = False
    tie_stop: bool = False


def voice_events(
    notes: list[NoteEvent], total: Fraction, legato: Fraction = Fraction(1)
) -> list[Event]:
    """Monophonic event list (chords + rests) covering [0, total) for one voice.

    A note is extended to the next onset in the voice if that leaves a gap of at most `legato`
    quarter notes.
    """
    groups: dict[Fraction, list[NoteEvent]] = {}
    for n in notes:
        groups.setdefault(n.q_onset, []).append(n)
    onsets = sorted(groups)
    events: list[Event] = []
    t = Fraction(0)
    for i, on in enumerate(onsets):
        if on > t:
            events.append(Event(t, on - t, []))
        nxt = onsets[i + 1] if i + 1 < len(onsets) else total
        dur = min(max(n.q_duration for n in groups[on]), nxt - on)
        if nxt - on - dur <= legato:
            dur = nxt - on
        events.append(Event(on, dur, sorted(groups[on], key=lambda n: n.pitch)))
        t = on + dur
    if t < total:
        events.append(Event(t, total - t, []))
    return events


def _next_cut(start: Fraction, end: Fraction, bar: Fraction) -> Fraction:
    """End of the next written segment: at the bar line, and at a beat line unless both edges
    of the segment are on beats. Off-beat pieces then stay within one beat's grid (16ths or
    triplets) and always have a plain written value; e.g. 1/3 + 1/4 would otherwise need a 12:7
    tuplet, which MuseScore cannot import."""
    cut = min(end, (math.floor(start / bar) + 1) * bar)
    if start.denominator != 1:
        cut = min(cut, Fraction(math.floor(start) + 1))
    elif cut.denominator != 1 and math.floor(cut) > start:
        cut = Fraction(math.floor(cut))
    return cut


def split_at_bars(events: list[Event], bar: Fraction) -> list[list[Event]]:
    """Per-measure events with onsets relative to the bar; notes crossing a bar line, or crossing
    a beat line off the beat, are split and tied."""
    measures: list[list[Event]] = []
    for ev in events:
        start, end = ev.onset, ev.onset + ev.duration
        first = True
        while start < end:
            m = math.floor(start / bar)
            seg_end = _next_cut(start, end, bar)
            while len(measures) <= m:
                measures.append([])
            last = seg_end == end
            measures[m].append(
                Event(
                    start - m * bar,
                    seg_end - start,
                    ev.notes,
                    tie_start=bool(ev.notes) and not last,
                    tie_stop=bool(ev.notes) and not first,
                )
            )
            start, first = seg_end, False
    return measures


def build_score(trans: Transcription, title: str = ""):
    import music21 as m21

    notes = [n for n in trans.notes if n.q_onset is not None]
    beats_per_bar, unit = trans.time_signature
    bar = Fraction(4 * beats_per_bar, unit)
    end = max((n.q_onset + n.q_duration for n in notes), default=bar)
    total = max(1, math.ceil(end / bar)) * bar

    by_voice = {
        v: voice_events([n for n in notes if (BASS if n.voice == BASS else UPPER) == v], total)
        for v in (UPPER, BASS)
    }
    measures = {v: split_at_bars(evs, bar) for v, evs in by_voice.items()}
    n_measures = int(total / bar)

    part = m21.stream.Part(id="guitar")
    part.partName = "Classical Guitar"
    part.insert(0, m21.instrument.AcousticGuitar())
    for i in range(n_measures):
        meas = m21.stream.Measure(number=i + 1)
        if i == 0:
            meas.insert(0, m21.clef.Treble8vbClef())
            meas.insert(0, _key(notes))
            meas.insert(0, m21.meter.TimeSignature(f"{beats_per_bar}/{unit}"))
            if trans.tempo_bpm:
                meas.insert(0, m21.tempo.MetronomeMark(number=round(trans.tempo_bpm)))
        for v in (UPPER, BASS):
            voice = m21.stream.Voice(id=XML_VOICE[v])
            evs = measures[v][i] if i < len(measures[v]) else [Event(Fraction(0), bar, [])]
            for ev in evs:
                voice.insert(ev.onset, _element(m21, ev, STEM[v]))
            meas.insert(0, voice)
        part.append(meas)

    score = m21.stream.Score([part])
    score.insert(0, m21.metadata.Metadata(title=title or "Transcription", composer=""))
    return score


def _element(m21, ev: Event, stem: str):
    if not ev.notes:
        el = m21.note.Rest()
    elif len(ev.notes) == 1:
        el = m21.note.Note(ev.notes[0].pitch)
    else:
        el = m21.chord.Chord([n.pitch for n in ev.notes])
    el.quarterLength = ev.duration
    if ev.notes:
        el.stemDirection = stem
        if ev.tie_start and ev.tie_stop:
            el.tie = m21.tie.Tie("continue")
        elif ev.tie_start:
            el.tie = m21.tie.Tie("start")
        elif ev.tie_stop:
            el.tie = m21.tie.Tie("stop")
    return el


def _key(notes: list[NoteEvent]):
    import music21 as m21

    if not notes:
        return m21.key.Key("C")
    s = m21.stream.Stream()
    for n in notes:
        el = m21.note.Note(n.pitch)
        el.quarterLength = n.q_duration
        s.insert(n.q_onset, el)
    return s.analyze("key")


def _fingering_index(trans: Transcription) -> dict[tuple[int, str], list[tuple]]:
    """(measure number, xml voice) -> [(start, end, midi, xml string, fret)] in quarter notes."""
    beats_per_bar, unit = trans.time_signature
    bar = Fraction(4 * beats_per_bar, unit)
    n_strings = len(trans.tuning)
    index: dict[tuple[int, str], list[tuple]] = {}
    for n in trans.notes:
        if n.q_onset is None or n.string is None:
            continue
        v = XML_VOICE[BASS if n.voice == BASS else UPPER]
        start, end = n.q_onset, n.q_onset + n.q_duration
        while start < end:
            m = math.floor(start / bar)
            seg_end = min(end, (m + 1) * bar)
            index.setdefault((m + 1, v), []).append(
                (start - m * bar, seg_end - m * bar, n.pitch, n_strings - n.string, n.fret)
            )
            start = seg_end
    return index


_STEPS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def add_fingerings(path: Path, trans: Transcription) -> None:
    """Insert <technical><string/><fret/></technical> into each pitched note of the written file."""
    index = _fingering_index(trans)
    tree = ET.parse(path)
    divisions = 1
    for measure in tree.getroot().iter("measure"):
        number = int(measure.get("number"))
        pos = Fraction(0)
        last_start = Fraction(0)
        for el in measure:
            if el.tag == "attributes" and el.find("divisions") is not None:
                divisions = int(el.find("divisions").text)
            elif el.tag in ("backup", "forward"):
                d = Fraction(int(el.find("duration").text), divisions)
                pos += -d if el.tag == "backup" else d
            elif el.tag == "note":
                dur_el = el.find("duration")
                d = Fraction(int(dur_el.text), divisions) if dur_el is not None else Fraction(0)
                start = last_start if el.find("chord") is not None else pos
                if el.find("chord") is None:
                    last_start = pos
                    pos += d
                pitch = el.find("pitch")
                voice = el.find("voice")
                if pitch is None or voice is None:
                    continue
                midi = (
                    12 * (int(pitch.find("octave").text) + 1)
                    + _STEPS[pitch.find("step").text]
                    + int(float(pitch.findtext("alter", "0")))
                )
                for s, e, p, string, fret in index.get((number, voice.text), []):
                    if p == midi and s <= start < e:
                        notations = el.find("notations")
                        if notations is None:
                            notations = ET.SubElement(el, "notations")
                        tech = ET.SubElement(notations, "technical")
                        ET.SubElement(tech, "string").text = str(string)
                        ET.SubElement(tech, "fret").text = str(fret)
                        break
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def write_musicxml(
    trans: Transcription, path: str | Path, title: str = "", string_numbers: bool = False
) -> Path:
    path = Path(path)
    build_score(trans, title).write("musicxml", fp=str(path))
    if string_numbers:
        add_fingerings(path, trans)
    return path
