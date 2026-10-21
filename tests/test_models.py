from audio2score.models import STANDARD_TUNING, NoteEvent, Transcription


def test_defaults():
    t = Transcription(notes=[NoteEvent(onset=0.0, offset=0.5, pitch=64)])
    assert t.tuning == STANDARD_TUNING
    assert t.notes[0].string is None
