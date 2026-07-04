"""flowlocal — private, fully-local voice dictation.

Pipeline: hotkey -> mic capture -> local Whisper ASR -> local formatting
-> keystroke injection into the active window. No network calls; the only
optional remote is an LLM served by Ollama on localhost.
"""

__version__ = "0.1.0"
