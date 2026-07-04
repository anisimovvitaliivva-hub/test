"""Local ASR.

Two backends, both fully local:

- "faster-whisper" (default): CTranslate2, best on CPU (use int8) and
  NVIDIA GPUs (cuda/float16). No Apple GPU support.
- "mlx": mlx-whisper on Apple Silicon — runs on the M-series GPU and is
  several times faster than CPU inference on the same machine.
  Install with `pip install ".[mlx]"`.

The model is loaded/warmed once at startup and kept in memory, mirroring
the "always warm" property of cloud dictation services — the
per-utterance cost is inference only. Model weights are downloaded once
and cached locally; after that everything runs offline (set
HF_HUB_OFFLINE=1 to enforce it).
"""

from __future__ import annotations

import numpy as np

from .config import AsrConfig

# Plain Whisper model names -> mlx-community conversions.
_MLX_REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}


def mlx_repo(model: str) -> str:
    """Map a bare model name to its mlx-community repo; pass repos through."""
    if "/" in model:  # already a HF repo or local path
        return model
    return _MLX_REPOS.get(model, model)


class Transcriber:
    def __init__(self, cfg: AsrConfig):
        self.cfg = cfg
        if cfg.backend == "mlx":
            self._init_mlx()
        else:
            self._init_faster_whisper()

    # -- faster-whisper (CPU / NVIDIA) --

    def _init_faster_whisper(self) -> None:
        from faster_whisper import WhisperModel  # lazy: heavy import

        self._model = WhisperModel(
            self.cfg.model, device=self.cfg.device, compute_type=self.cfg.compute_type
        )
        self.transcribe = self._transcribe_faster_whisper

    def _transcribe_faster_whisper(self, audio: np.ndarray) -> str:
        segments, _info = self._model.transcribe(
            audio,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            vad_filter=True,  # trims silence/breaths around the utterance
            condition_on_previous_text=False,  # avoids hallucination loops
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    # -- mlx-whisper (Apple Silicon GPU) --

    def _init_mlx(self) -> None:
        try:
            import mlx_whisper  # lazy: only exists on Apple Silicon installs
        except ImportError as exc:
            raise RuntimeError(
                "asr.backend = 'mlx' requires mlx-whisper (Apple Silicon only): "
                'pip install ".[mlx]"'
            ) from exc

        self._mlx = mlx_whisper
        self._repo = mlx_repo(self.cfg.model)
        # Warm up: downloads/loads weights and compiles kernels now, not on
        # the first real utterance.
        self._transcribe_mlx(np.zeros(16000, dtype=np.float32))
        self.transcribe = self._transcribe_mlx

    def _transcribe_mlx(self, audio: np.ndarray) -> str:
        result = self._mlx.transcribe(
            audio,
            path_or_hf_repo=self._repo,
            language=self.cfg.language,
            condition_on_previous_text=False,
            fp16=True,
        )
        return result.get("text", "").strip()
