"""Split quantized notes into bass (voice 0) and upper (voice 1) voices.

Classical guitar notation usually has two voices on one staff: the bass with stems down and the
melody (plus inner notes, written as chords) with stems up. Notes starting together: the lowest
goes to the bass, the rest to the upper voice. A note on its own goes to whichever voice it is
closer to in pitch, tracked with a running average for each voice.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction

from audio2score.models import NoteEvent

BASS, UPPER = 0, 1


@dataclass(frozen=True)
class VoiceConfig:
    min_gap: int = 5  # a chord's lowest note joins the bass only if this far below the next note
    smoothing: float = 0.5  # weight of the newest note in each voice's running pitch


def assign(notes: list[NoteEvent], cfg: VoiceConfig | None = None) -> list[NoteEvent]:
    """Copies of `notes` (needs q_onset) with `voice` set, in (q_onset, pitch) order."""
    cfg = cfg or VoiceConfig()
    notes = sorted(notes, key=lambda n: (n.q_onset, n.pitch))
    groups: dict[Fraction, list[NoteEvent]] = {}
    for n in notes:
        groups.setdefault(n.q_onset, []).append(n)
    if not groups:
        return []

    first = groups[min(groups)]
    bass_ref = float(min(n.pitch for n in notes[: max(8, len(first))]))
    upper_ref = float(max(n.pitch for n in notes[: max(8, len(first))]))

    def update(ref: float, pitch: int) -> float:
        return (1 - cfg.smoothing) * ref + cfg.smoothing * pitch

    out = []
    for onset in sorted(groups):
        group = groups[onset]  # ascending pitch
        if len(group) >= 2 and group[1].pitch - group[0].pitch >= cfg.min_gap:
            low, rest = group[0], group[1:]
            out.append(replace(low, voice=BASS))
            out.extend(replace(n, voice=UPPER) for n in rest)
            bass_ref = update(bass_ref, low.pitch)
            upper_ref = update(upper_ref, rest[-1].pitch)
        elif len(group) >= 2:
            # Close-voiced chord: keep it together, in the voice its bottom note is closer to.
            v = BASS if abs(group[0].pitch - bass_ref) < abs(group[0].pitch - upper_ref) else UPPER
            out.extend(replace(n, voice=v) for n in group)
            if v == BASS:
                bass_ref = update(bass_ref, group[0].pitch)
            else:
                upper_ref = update(upper_ref, group[-1].pitch)
        else:
            n = group[0]
            if abs(n.pitch - bass_ref) < abs(n.pitch - upper_ref):
                out.append(replace(n, voice=BASS))
                bass_ref = update(bass_ref, n.pitch)
            else:
                out.append(replace(n, voice=UPPER))
                upper_ref = update(upper_ref, n.pitch)
    return out
