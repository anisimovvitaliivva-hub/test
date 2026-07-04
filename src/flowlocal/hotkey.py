"""Global hotkey handling via pynput.

Two modes:
- "hold": push-to-talk — recording runs while the combo is held.
- "toggle": first press starts recording, second press stops it.

Callbacks are invoked from the pynput listener thread; the app hands the
heavy work (ASR) off to its own worker so key handling stays responsive.
"""

from __future__ import annotations

from collections.abc import Callable

from .config import HotkeyConfig


class HotkeyListener:
    def __init__(self, cfg: HotkeyConfig, on_start: Callable[[], None], on_stop: Callable[[], None]):
        from pynput import keyboard  # lazy: needs a display server

        self._keyboard = keyboard
        self.cfg = cfg
        self.on_start = on_start
        self.on_stop = on_stop
        self._combo = {
            self._canonical(k)
            for k in keyboard.HotKey.parse(cfg.combo)
        }
        self._pressed: set = set()
        self._active = False  # recording in progress
        self._listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )

    def _canonical(self, key):
        return self._listener.canonical(key) if self._listener else key

    def _on_press(self, key) -> None:
        key = self._listener.canonical(key)
        if key not in self._combo:
            return
        self._pressed.add(key)
        if self._pressed != self._combo:
            return
        if self.cfg.mode == "toggle":
            if self._active:
                self._active = False
                self.on_stop()
            else:
                self._active = True
                self.on_start()
        elif not self._active:
            self._active = True
            self.on_start()

    def _on_release(self, key) -> None:
        key = self._listener.canonical(key)
        self._pressed.discard(key)
        if self.cfg.mode == "hold" and self._active and key in self._combo:
            self._active = False
            self.on_stop()

    def run_forever(self) -> None:
        with self._listener:
            self._listener.join()
