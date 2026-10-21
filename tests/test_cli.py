import numpy as np
import pytest

from audio2score import audio_io, cli, transcribe
from audio2score.models import NoteEvent


def test_cli_end_to_end_with_fake_backend(tmp_path, monkeypatch):
    wav = tmp_path / "song.wav"
    audio_io.save_wav(wav, np.zeros(22050, dtype=np.float32), 22050)

    def fake_run(audio, sr, backend):
        return [NoteEvent(0.0, 0.5, 40), NoteEvent(0.0, 0.5, 64), NoteEvent(0.5, 1.0, 69)]

    monkeypatch.setattr(transcribe, "run", fake_run)
    out = tmp_path / "out"
    assert cli.main([str(wav), "-o", str(out)]) == 0
    assert (out / "song.mid").is_file()
    tab = (out / "song.tab.txt").read_text()
    assert tab.splitlines()[0].startswith("e|-0")


def test_cli_rejects_unimplemented_format(tmp_path):
    with pytest.raises(SystemExit):
        cli.main([str(tmp_path / "x.wav"), "--formats", "gp5"])


def test_audio_io_resamples_and_downmixes(tmp_path):
    import soundfile as sf

    t = np.arange(44100) / 44100
    stereo = np.stack([np.sin(2 * np.pi * 440 * t)] * 2, axis=1).astype(np.float32)
    path = tmp_path / "stereo.wav"
    sf.write(str(path), stereo, 44100)
    audio, sr = audio_io.load(path, sr=22050)
    assert sr == 22050
    assert audio.ndim == 1
    assert abs(len(audio) - 22050) < 100
