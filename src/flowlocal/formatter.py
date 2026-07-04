"""Text cleanup — the local stand-in for Wispr Flow's cloud LLM stage.

Two tiers:

1. Rule-based (always available, ~0ms): strips filler words (EN + RU),
   collapses whitespace, fixes spacing around punctuation, capitalizes
   sentence starts, applies spoken commands like "new line".
2. Optional LLM polish through Ollama on *localhost* — the config layer
   rejects any non-local URL, so text still never leaves the machine.
   On any LLM error we fall back to the rule-based result: dictation must
   never block on the polish step.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from .config import FormatConfig

# Standalone filler words/phrases. Word-boundary matched, case-insensitive.
_FILLERS = [
    # English
    r"uh+", r"um+", r"erm+", r"hmm+", r"you know", r"i mean", r"sort of like",
    # Russian
    r"э+м*", r"ну+", r"как бы", r"типа", r"короче говоря", r"это самое",
]
_FILLER_RE = re.compile(
    r"(?<![\w-])(?:" + "|".join(_FILLERS) + r")(?![\w-])[,.]?\s*",
    re.IGNORECASE | re.UNICODE,
)

# Spoken commands -> literal output, matched as whole phrases.
_COMMANDS = {
    r"new line|новая строка|с новой строки": "\n",
    r"new paragraph|новый абзац": "\n\n",
}

_SENTENCE_START_RE = re.compile(r"(^|[.!?…]\s+|\n\s*)([a-zа-яё])", re.UNICODE)


def _apply_commands(text: str) -> str:
    for pattern, replacement in _COMMANDS.items():
        text = re.sub(
            rf"[,.]?\s*\b(?:{pattern})\b[,.]?\s*",
            replacement,
            text,
            flags=re.IGNORECASE | re.UNICODE,
        )
    return text


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.!?;:…])", r"\1", text)  # no space before punctuation
    text = re.sub(r"([,;:]) *(?=\S)", r"\1 ", text)  # one space after
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"([,.]){2,}", r"\1", text)  # ",," left by filler removal
    return text.strip()


def _capitalize(text: str) -> str:
    return _SENTENCE_START_RE.sub(lambda m: m.group(1) + m.group(2).upper(), text)


def format_text(text: str, cfg: FormatConfig) -> str:
    """Rule-based cleanup; optionally polished by a localhost LLM."""
    if not text:
        return ""
    text = _apply_commands(text)
    if cfg.remove_fillers:
        text = _FILLER_RE.sub("", text)
    text = _tidy(text)
    if cfg.capitalize:
        text = _capitalize(text)
    if cfg.llm_enabled and text:
        text = _llm_polish(text, cfg)
    return text


_LLM_PROMPT = (
    "You clean up dictated speech-to-text output. Fix punctuation, grammar, "
    "word agreement and obvious speech-recognition errors (wrong but "
    "similar-sounding words) so the text reads the way the speaker intended. "
    "Keep the original language and meaning; do not add new content, do not "
    "answer questions in the text, do not comment. Return only the corrected "
    "text.\n\nText: {text}"
)


def _llm_polish(text: str, cfg: FormatConfig) -> str:
    payload = json.dumps(
        {
            "model": cfg.llm_model,
            "prompt": _LLM_PROMPT.format(text=text),
            "stream": False,
            "options": {"temperature": 0.0},
        }
    ).encode()
    req = urllib.request.Request(
        cfg.llm_url.rstrip("/") + "/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=cfg.llm_timeout) as resp:
            result = json.loads(resp.read())
        polished = result.get("response", "").strip()
        return polished or text
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return text
