"""Application wiring: hotkey -> recorder -> ASR -> formatter -> injection.

The hotkey listener thread only starts/stops the recorder and enqueues
finished utterances; a single worker thread runs ASR + formatting +
injection so a long transcription never blocks key handling, and
utterances are delivered in the order they were spoken.
"""

from __future__ import annotations

import logging
import queue
import threading

import numpy as np

from .audio import Recorder, is_speech, rms
from .config import Config
from .formatter import format_text
from .history import History
from .inject import deliver

log = logging.getLogger("flowlocal")


class App:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.recorder = Recorder(cfg.audio)
        self.history = History(cfg.history)
        self._utterances: queue.Queue[np.ndarray | None] = queue.Queue()
        self._transcriber = None

    def _load_model(self) -> None:
        from .transcribe import Transcriber

        log.info("loading whisper model %r (%s)...", self.cfg.asr.model, self.cfg.asr.device)
        self._transcriber = Transcriber(self.cfg.asr)
        log.info("model ready")

    # -- hotkey callbacks (pynput listener thread) --

    def _on_start(self) -> None:
        try:
            self.recorder.start()
            log.info("recording...")
        except Exception:
            log.exception("could not start recording")

    def _on_stop(self) -> None:
        audio = self.recorder.stop()
        log.info("captured %.1fs", audio.size / self.cfg.audio.sample_rate)
        self._utterances.put(audio)

    # -- worker thread --

    def _worker(self) -> None:
        while True:
            audio = self._utterances.get()
            if audio is None:
                return
            try:
                self._process(audio)
            except Exception:
                log.exception("failed to process utterance")

    def _process(self, audio: np.ndarray) -> None:
        if not is_speech(audio, self.cfg.audio.speech_threshold):
            log.info(
                "no speech detected, skipping (rms %.5f <= threshold %.4f; "
                "run `flowlocal --mic-test` to diagnose)",
                rms(audio),
                self.cfg.audio.speech_threshold,
            )
            return
        raw = self._transcriber.transcribe(audio)
        if not raw:
            log.info("empty transcription, skipping")
            return
        text = format_text(raw, self.cfg.format)
        log.info("-> %r", text)
        deliver(text, self.cfg.output)
        self.history.record(raw, text)

    def run(self) -> None:
        from .hotkey import HotkeyListener

        self._load_model()
        worker = threading.Thread(target=self._worker, daemon=True)
        worker.start()
        listener = HotkeyListener(self.cfg.hotkey, self._on_start, self._on_stop)
        mode = "hold to talk" if self.cfg.hotkey.mode == "hold" else "press to toggle"
        log.info("ready — %s: %s", mode, self.cfg.hotkey.combo)
        listener.run_forever()
