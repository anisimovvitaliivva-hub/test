from flowlocal.config import FormatConfig
from flowlocal.formatter import format_text


CFG = FormatConfig()  # rules on, LLM off


def test_empty():
    assert format_text("", CFG) == ""


def test_removes_english_fillers():
    out = format_text("um so I think, uh, we should ship it", CFG)
    assert "um" not in out.lower()
    assert "uh" not in out.lower()
    assert "ship it" in out


def test_removes_russian_fillers():
    out = format_text("ну, короче говоря, надо типа отправить письмо", CFG)
    assert "типа" not in out
    assert "короче говоря" not in out
    assert "отправить письмо" in out


def test_does_not_eat_filler_lookalikes_inside_words():
    out = format_text("the umbrella is human", CFG)
    assert "umbrella" in out
    assert "human" in out


def test_capitalizes_sentences():
    out = format_text("привет. как дела? отлично", CFG)
    assert out == "Привет. Как дела? Отлично"


def test_new_line_command():
    out = format_text("first item new line second item", CFG)
    assert out == "First item\nSecond item"


def test_new_paragraph_command_russian():
    out = format_text("привет, новый абзац, пока", CFG)
    assert out == "Привет\n\nПока"


def test_punctuation_spacing():
    out = format_text("hello ,  world .", CFG)
    assert out == "Hello, world."


def test_fillers_kept_when_disabled():
    cfg = FormatConfig(remove_fillers=False, capitalize=False)
    assert "типа" in format_text("надо типа сделать", cfg)


def test_llm_failure_falls_back_to_rule_based(monkeypatch):
    # Unreachable localhost port: polish must fail soft, not raise.
    cfg = FormatConfig(llm_enabled=True, llm_url="http://127.0.0.1:1", llm_timeout=0.2)
    assert format_text("hello world", cfg) == "Hello world"
