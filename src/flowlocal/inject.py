"""Delivering text into the active window.

Wispr Flow injects the final text as if the user typed it; we do the same
with whatever mechanism the desktop supports:

- "type": synthetic keystrokes — wtype (Wayland), xdotool (X11), or pynput
  (X11/macOS/Windows) as fallback.
- "clipboard": put text on the clipboard and send Ctrl+V — much faster for
  long dictations; restores the previous clipboard afterwards.
- "stdout": print to stdout (piping/debugging, headless machines).
- "auto": clipboard for long texts, typing for short ones.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time

from .config import OutputConfig

_CLIPBOARD_THRESHOLD = 200  # chars; above this "auto" switches to paste


def _run(cmd: list[str], input_text: str | None = None) -> bool:
    try:
        subprocess.run(
            cmd,
            input=input_text.encode() if input_text is not None else None,
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return False


def _type_keystrokes(text: str, interval: float) -> bool:
    if shutil.which("wtype"):  # Wayland
        return _run(["wtype", "-"], input_text=text)
    if shutil.which("xdotool"):  # X11
        return _run(["xdotool", "type", "--delay", str(int(interval * 1000)), text])
    try:
        from pynput.keyboard import Controller

        kb = Controller()
        for ch in text:
            kb.type(ch)
            time.sleep(interval)
        return True
    except Exception:
        return False


def _clipboard_get() -> str | None:
    for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"]):
        if shutil.which(cmd[0]):
            try:
                out = subprocess.run(cmd, check=True, capture_output=True, timeout=5)
                return out.stdout.decode(errors="replace")
            except (subprocess.SubprocessError, OSError):
                return None
    return None


def _clipboard_set(text: str) -> bool:
    if shutil.which("wl-copy"):
        return _run(["wl-copy"], input_text=text)
    if shutil.which("xclip"):
        return _run(["xclip", "-selection", "clipboard"], input_text=text)
    return False


def _paste_via_clipboard(text: str) -> bool:
    previous = _clipboard_get()
    if not _clipboard_set(text):
        return False
    time.sleep(0.05)  # let the clipboard settle before the paste keystroke
    ok = False
    if shutil.which("wtype"):
        ok = _run(["wtype", "-M", "ctrl", "-k", "v", "-m", "ctrl"])
    elif shutil.which("xdotool"):
        ok = _run(["xdotool", "key", "--clearmodifiers", "ctrl+v"])
    else:
        try:
            from pynput.keyboard import Controller, Key

            kb = Controller()
            with kb.pressed(Key.ctrl):
                kb.press("v")
                kb.release("v")
            ok = True
        except Exception:
            ok = False
    if previous is not None:
        time.sleep(0.15)  # give the target app time to read the clipboard
        _clipboard_set(previous)
    return ok


def deliver(text: str, cfg: OutputConfig) -> None:
    """Send `text` to the active window using the configured method."""
    if not text:
        return
    method = cfg.method
    if method == "auto":
        method = "clipboard" if len(text) > _CLIPBOARD_THRESHOLD else "type"

    if method == "stdout":
        print(text, flush=True)
        return
    if method == "clipboard" and _paste_via_clipboard(text):
        return
    if _type_keystrokes(text, cfg.type_interval):
        return
    # Last resort so the dictation is never silently lost.
    print(text, file=sys.stderr, flush=True)
