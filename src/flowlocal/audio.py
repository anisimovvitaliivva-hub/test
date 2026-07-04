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


def rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio))))


def is_speech(audio: np.ndarray, threshold: float = 0.004) -> bool:
    """Cheap energy gate so accidental hotkey taps don't hit the ASR model."""
    if audio.size < 1600:  # <0.1s of audio
        return False
    return rms(audio) > threshold


def mic_test(cfg: AudioConfig, seconds: float = 3.0) -> None:
    """Interactive microphone check: list devices, record, report levels."""
    import sounddevice as sd

    print("Available audio devices (input devices have >0 'in' channels):\n")
    print(sd.query_devices())
    print(f"\nUsing device: {cfg.device or 'system default'}")
    print(f"Recording {seconds:.0f}s — say something now...")
    audio = sd.rec(
        int(seconds * cfg.sample_rate),
        samplerate=cfg.sample_rate,
        channels=1,
        dtype="float32",
        device=cfg.device,
    )
    sd.wait()
    audio = audio[:, 0]
    level = rms(audio)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    print(f"\nRMS level: {level:.5f}   peak: {peak:.5f}   threshold: {cfg.speech_threshold}")
    if peak == 0.0:
        print(
            "Result: TOTAL SILENCE — the app is receiving all zeros.\n"
            "On macOS this almost always means the terminal has no microphone\n"
            "permission: System Settings > Privacy & Security > Microphone,\n"
            "enable your terminal app, then restart the terminal."
        )
    elif level <= cfg.speech_threshold:
        print(
            "Result: signal present but below the speech threshold.\n"
            "Either the wrong input device is selected (see the list above,\n"
            "set audio.device in config.toml) or the mic is very quiet —\n"
            f"lower audio.speech_threshold below {level:.5f}."
        )
    else:
        print("Result: OK — this level passes the speech gate.")
