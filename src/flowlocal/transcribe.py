"""Local ASR via faster-whisper (CTranslate2).

The model is loaded once at startup and kept in memory, mirroring the
"always warm" property of cloud dictation services — the per-utterance
cost is inference only. Model weights are downloaded once by
faster-whisper and cached locally; after that everything runs offline
(set HF_HUB_OFFLINE=1 to enforce it).
"""

from __future__ import annotations

import numpy as np

from .config import AsrConfig


class Transcriber:
    def __init__(self, cfg: AsrConfig):
        from faster_whisper import WhisperModel  # lazy: heavy import

        self.cfg = cfg
        self.model = WhisperModel(
            cfg.model, device=cfg.device, compute_type=cfg.compute_type
        )

    def transcribe(self, audio: np.ndarray) -> str:
        """Transcribe mono float32 @16kHz audio to raw text."""
        segments, _info = self.model.transcribe(
            audio,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            vad_filter=True,  # trims silence/breaths around the utterance
            condition_on_previous_text=False,  # avoids hallucination loops
        )
        return " ".join(seg.text.strip() for seg in segments).strip()
