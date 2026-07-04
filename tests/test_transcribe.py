import pytest

from flowlocal.config import Config, ConfigError, validate
from flowlocal.transcribe import mlx_repo


def test_known_models_map_to_mlx_community():
    assert mlx_repo("small") == "mlx-community/whisper-small-mlx"
    assert mlx_repo("large-v3-turbo") == "mlx-community/whisper-large-v3-turbo"


def test_explicit_repo_passes_through():
    assert mlx_repo("mlx-community/whisper-large-v3-mlx") == "mlx-community/whisper-large-v3-mlx"
    assert mlx_repo("someone/custom-model") == "someone/custom-model"


def test_unknown_backend_rejected():
    cfg = Config()
    cfg.asr.backend = "whispercpp"
    with pytest.raises(ConfigError, match="backend"):
        validate(cfg)
