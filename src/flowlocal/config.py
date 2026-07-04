"""Configuration loading and validation.

Config lives in a TOML file (default: ~/.config/flowlocal/config.toml).
Every field has a safe default so the app runs with no config file at all.
"""

from __future__ import annotations

import dataclasses
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

DEFAULT_CONFIG_PATH = Path(
    os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
) / "flowlocal" / "config.toml"


class ConfigError(ValueError):
    pass


@dataclass
class AudioConfig:
    sample_rate: int = 16000  # Whisper native rate
    device: str | None = None  # None = system default input
    max_seconds: float = 120.0  # hard cap per utterance


@dataclass
class HotkeyConfig:
    # pynput syntax, e.g. "<ctrl>+<alt>+space" or a single key like "<f9>"
    combo: str = "<ctrl>+<alt>+space"
    mode: str = "hold"  # "hold" (push-to-talk) or "toggle"


@dataclass
class AsrConfig:
    model: str = "small"  # any faster-whisper model name or local CTranslate2 dir
    device: str = "auto"  # "auto" | "cpu" | "cuda"
    compute_type: str = "default"  # e.g. "int8", "float16"
    language: str | None = None  # None = autodetect (handles code-switching per utterance)
    beam_size: int = 5


@dataclass
class FormatConfig:
    remove_fillers: bool = True
    capitalize: bool = True
    # Optional LLM cleanup via a *localhost* Ollama server. Off by default.
    llm_enabled: bool = False
    llm_url: str = "http://127.0.0.1:11434"
    llm_model: str = "llama3.2:3b"
    llm_timeout: float = 10.0


@dataclass
class OutputConfig:
    method: str = "auto"  # "auto" | "type" | "clipboard" | "stdout"
    type_interval: float = 0.005  # seconds between keystrokes in "type" mode


@dataclass
class HistoryConfig:
    enabled: bool = False  # opt-in: nothing is persisted unless the user asks
    path: str | None = None  # default: ~/.local/share/flowlocal/history.db


@dataclass
class Config:
    audio: AudioConfig = field(default_factory=AudioConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    format: FormatConfig = field(default_factory=FormatConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    history: HistoryConfig = field(default_factory=HistoryConfig)


_SECTIONS = {f.name: f for f in dataclasses.fields(Config)}


def _build_section(cls, data: dict, section: str):
    known = {f.name for f in dataclasses.fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ConfigError(
            f"unknown key(s) in [{section}]: {', '.join(sorted(unknown))}"
        )
    return cls(**data)


def load_config(path: Path | None = None) -> Config:
    """Load config from `path`, falling back to defaults for anything unset."""
    path = path or DEFAULT_CONFIG_PATH
    if not path.exists():
        return Config()
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    kwargs = {}
    for name, value in raw.items():
        if name not in _SECTIONS:
            raise ConfigError(f"unknown section [{name}]")
        section_cls = _SECTIONS[name].default_factory  # type: ignore[union-attr]
        kwargs[name] = _build_section(section_cls, value, name)
    cfg = Config(**kwargs)
    validate(cfg)
    return cfg


def validate(cfg: Config) -> None:
    if cfg.hotkey.mode not in ("hold", "toggle"):
        raise ConfigError(f"hotkey.mode must be 'hold' or 'toggle', got {cfg.hotkey.mode!r}")
    if cfg.output.method not in ("auto", "type", "clipboard", "stdout"):
        raise ConfigError(f"unknown output.method {cfg.output.method!r}")
    if cfg.format.llm_enabled:
        host = urlparse(cfg.format.llm_url).hostname
        if host not in ("127.0.0.1", "localhost", "::1"):
            # The whole point of this project is that audio and text never
            # leave the machine, so a remote LLM endpoint is a config error.
            raise ConfigError(
                f"format.llm_url must point at localhost, got {cfg.format.llm_url!r}"
            )
