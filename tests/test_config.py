import pytest

from flowlocal.config import Config, ConfigError, load_config, validate


def test_defaults_without_file(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert cfg.asr.model == "small"
    assert cfg.hotkey.mode == "hold"
    assert cfg.history.enabled is False
    assert cfg.format.llm_enabled is False


def test_partial_file_overrides(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[asr]\nmodel = "large-v3"\nlanguage = "ru"\n\n[hotkey]\nmode = "toggle"\n')
    cfg = load_config(p)
    assert cfg.asr.model == "large-v3"
    assert cfg.asr.language == "ru"
    assert cfg.hotkey.mode == "toggle"
    assert cfg.output.method == "auto"  # untouched section keeps defaults


def test_unknown_key_rejected(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[asr]\nmodle = 'small'\n")
    with pytest.raises(ConfigError, match="modle"):
        load_config(p)


def test_unknown_section_rejected(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("[telemetry]\nenabled = true\n")
    with pytest.raises(ConfigError, match="telemetry"):
        load_config(p)


def test_remote_llm_url_rejected():
    cfg = Config()
    cfg.format.llm_enabled = True
    cfg.format.llm_url = "https://api.example.com"
    with pytest.raises(ConfigError, match="localhost"):
        validate(cfg)


def test_localhost_llm_url_accepted():
    cfg = Config()
    cfg.format.llm_enabled = True
    cfg.format.llm_url = "http://localhost:11434"
    validate(cfg)


def test_bad_hotkey_mode_rejected(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text('[hotkey]\nmode = "double-tap"\n')
    with pytest.raises(ConfigError, match="hold"):
        load_config(p)
