"""Microphone capture.

Records 16 kHz mono float32 audio between "start" and "stop" events
(driven by the hotkey). Uses a background sounddevice InputStream and an
in-memory buffer; nothing is ever written to disk.
"""

from __future__ import annotations

import threading

import numpy as np

from .config import AudioConfig


class Recorder:
    def __init__(self, cfg: AudioConfig):
        self.cfg = cfg
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream = None
        self._max_samples = int(cfg.max_seconds * cfg.sample_rate)
        self._recorded = 0

    def start(self) -> None:
        import sounddevice as sd  # lazy: lets tests run without PortAudio

        with self._lock:
            self._chunks = []
            self._recorded = 0
        self._stream = sd.InputStream(
            samplerate=self.cfg.sample_rate,
            channels=1,
            dtype="float32",
            device=self.cfg.device,
            callback=self._on_audio,
        )
        self._stream.start()

    def _on_audio(self, indata, frames, time_info, status) -> None:
        with self._lock:
            if self._recorded >= self._max_samples:
                return
            self._chunks.append(indata[:, 0].copy())
            self._recorded += frames

    def stop(self) -> np.ndarray:
        """Stop capturing and return the utterance as mono float32 @16kHz."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        with self._lock:
            if not self._chunks:
                return np.zeros(0, dtype=np.float32)
            audio = np.concatenate(self._chunks)
            self._chunks = []
        return audio[: self._max_samples]


def is_speech(audio: np.ndarray, threshold: float = 0.004) -> bool:
    """Cheap energy gate so accidental hotkey taps don't hit the ASR model."""
    if audio.size < 1600:  # <0.1s of audio
        return False
    rms = float(np.sqrt(np.mean(np.square(audio))))
    return rms > threshold
