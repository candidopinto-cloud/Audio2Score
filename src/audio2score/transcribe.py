"""Audio -> note events. Backends are imported lazily so the package works without ML deps."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np

from audio2score.models import NoteEvent

# Classical guitar: low E2 (82 Hz) up to ~B5 (988 Hz, 19th fret); leave headroom for tuning drift.
GUITAR_FMIN_HZ = 75.0
GUITAR_FMAX_HZ = 1400.0

BACKENDS = ("auto", "gaps", "basic_pitch")


def default_backend() -> str:
    """GAPS (classical-guitar model) when installed, else Basic Pitch."""
    import importlib.util

    return "gaps" if importlib.util.find_spec("hf_midi_transcription") else "basic_pitch"


def run(audio: np.ndarray, sr: int, backend: str = "auto", **kwargs) -> list[NoteEvent]:
    """Transcribe mono audio into notes sorted by (onset, pitch)."""
    if backend == "auto":
        backend = default_backend()
    if backend == "basic_pitch":
        notes = _basic_pitch(audio, sr, **kwargs)
    elif backend == "gaps":
        notes = _gaps(audio, sr, **kwargs)
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
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")  # hide TensorFlow's start-up chatter
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


# GAPS: Kong et al. high-resolution CRNN fine-tuned on classical guitar (Riley et al., ISMIR 2024).
# Code and weights are MIT; the training data (GAPS dataset) is non-commercial. See docs/RESEARCH.md.
GAPS_SR = 16000
GAPS_PAD_S = 0.5
_gaps_model = None


def _gaps(audio: np.ndarray, sr: int, device: str | None = None) -> list[NoteEvent]:
    global _gaps_model
    try:
        from hf_midi_transcription import MidiTranscriptionModel
    except ImportError as e:
        raise ImportError(
            "GAPS backend not installed; see README (torch cu128 + hf_midi_transcription)"
        ) from e
    import librosa

    if _gaps_model is None:
        from huggingface_hub import hf_hub_download

        # ~100 MB, downloaded on first use and cached. Fetched here rather than by the library,
        # whose download message crashes on Windows consoles that can't print a check mark.
        weights = hf_hub_download("xavriley/midi-transcription-models", "guitar-gaps.pth")
        _gaps_model = MidiTranscriptionModel(
            instrument="guitar", checkpoint_path=weights, device=device
        )
    if sr != GAPS_SR:
        audio = librosa.resample(audio, orig_sr=sr, target_sr=GAPS_SR)
    duration = len(audio) / GAPS_SR
    # The model misses a note right at t=0, so give it some lead-in silence.
    pad = np.zeros(int(GAPS_PAD_S * GAPS_SR), dtype=np.float32)
    result = _gaps_model.transcriptor.transcribe(
        np.concatenate([pad, audio.astype(np.float32)]), None
    )
    notes = []
    for e in result["est_note_events"]:
        onset = max(0.0, float(e["onset_time"]) - GAPS_PAD_S)
        offset = min(duration, float(e["offset_time"]) - GAPS_PAD_S)  # can run past the end
        notes.append(
            NoteEvent(
                onset=onset,
                offset=max(offset, onset + 0.01),
                pitch=int(e["midi_note"]),
                velocity=int(np.clip(e["velocity"], 1, 127)),
            )
        )
    return notes
