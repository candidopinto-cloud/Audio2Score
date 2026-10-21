"""Audio -> note events. Backends are imported lazily so the package works without ML deps."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np

from audio2score.models import NoteEvent

# Classical guitar: low E2 (82 Hz) up to ~B5 (988 Hz, 19th fret); leave headroom for tuning drift.
GUITAR_FMIN_HZ = 75.0
GUITAR_FMAX_HZ = 1400.0

BACKENDS = ("basic_pitch", "gaps")


def run(audio: np.ndarray, sr: int, backend: str = "basic_pitch", **kwargs) -> list[NoteEvent]:
    """Transcribe mono audio into notes sorted by (onset, pitch)."""
    if backend == "basic_pitch":
        notes = _basic_pitch(audio, sr, **kwargs)
    elif backend == "gaps":
        raise NotImplementedError("GAPS backend is Milestone 2 (not yet verified/integrated)")
    else:
        raise ValueError(f"unknown backend {backend!r}; choose from {BACKENDS}")
    notes.sort(key=lambda n: (n.onset, n.pitch))
    return notes


def _basic_pitch(
    audio: np.ndarray,
    sr: int,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_ms: float = 58.0,
) -> list[NoteEvent]:
    try:
        from basic_pitch.inference import predict
    except ImportError as e:
        raise ImportError("Basic Pitch not installed: pip install -e .[basic_pitch]") from e

    from audio2score.audio_io import save_wav

    # Basic Pitch only accepts a file path.
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "input.wav"
        save_wav(wav, audio, sr)
        _, _, events = predict(
            str(wav),
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=min_note_ms,
            minimum_frequency=GUITAR_FMIN_HZ,
            maximum_frequency=GUITAR_FMAX_HZ,
            melodia_trick=True,
        )

    # events: (start_s, end_s, pitch, amplitude 0..1, pitch_bends)
    return [
        NoteEvent(
            onset=float(start),
            offset=float(end),
            pitch=int(pitch),
            velocity=int(np.clip(round(amp * 127), 1, 127)),
        )
        for start, end, pitch, amp, *_ in events
    ]
