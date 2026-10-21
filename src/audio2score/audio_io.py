"""Load any audio/video file as a mono float32 array via ffmpeg."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import numpy as np

DEFAULT_SR = 22050


def find_ffmpeg() -> str | None:
    """Locate ffmpeg: $AUDIO2SCORE_FFMPEG, then PATH, then the winget links folder."""
    env = os.environ.get("AUDIO2SCORE_FFMPEG")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    # winget adds this folder to PATH, but already-open shells don't see it yet.
    local = os.environ.get("LOCALAPPDATA")
    if local:
        winget = Path(local) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
        if winget.is_file():
            return str(winget)
    return None


def load(path: str | Path, sr: int = DEFAULT_SR) -> tuple[np.ndarray, int]:
    """Decode `path` (any format ffmpeg understands, including video) to mono float32 at `sr`."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)

    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return _load_soundfile(path, sr)

    cmd = [
        ffmpeg,
        "-nostdin",
        "-v", "error",
        "-i", str(path),
        "-vn",  # drop any video stream
        "-ac", "1",
        "-ar", str(sr),
        "-f", "f32le",
        "-",
    ]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, check=False)
    if proc.returncode != 0:
        msg = proc.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed on {path}: {msg}")
    audio = np.frombuffer(proc.stdout, dtype=np.float32).copy()
    if audio.size == 0:
        raise RuntimeError(f"no audio stream found in {path}")
    return audio, sr


def _load_soundfile(path: Path, sr: int) -> tuple[np.ndarray, int]:
    """Fallback without ffmpeg: WAV/FLAC/OGG only."""
    import librosa
    import soundfile as sf

    try:
        audio, file_sr = sf.read(str(path), dtype="float32", always_2d=True)
    except RuntimeError as e:
        raise RuntimeError(
            f"cannot read {path} without ffmpeg (install with `winget install Gyan.FFmpeg`)"
        ) from e
    audio = audio.mean(axis=1)
    if file_sr != sr:
        audio = librosa.resample(audio, orig_sr=file_sr, target_sr=sr)
    return audio.astype(np.float32), sr


def save_wav(path: str | Path, audio: np.ndarray, sr: int) -> None:
    import soundfile as sf

    sf.write(str(path), audio, sr, subtype="FLOAT")
