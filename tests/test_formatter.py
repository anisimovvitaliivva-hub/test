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


def test_polish_that_switches_language_is_rejected(monkeypatch):
    import flowlocal.formatter as f

    monkeypatch.setattr(f, "_llm_generate", lambda prompt, cfg: "Hello world, how are you?")
    cfg = FormatConfig(llm_enabled=True)
    out = format_text("привет мир как дела", cfg)
    assert out == "Привет мир как дела"  # rule-based result, translation discarded


def test_polish_in_same_language_is_kept(monkeypatch):
    import flowlocal.formatter as f

    monkeypatch.setattr(f, "_llm_generate", lambda prompt, cfg: "Привет, мир! Как дела?")
    cfg = FormatConfig(llm_enabled=True)
    assert format_text("привет мир как дела", cfg) == "Привет, мир! Как дела?"


def test_spoken_translate_command(monkeypatch):
    import flowlocal.formatter as f

    prompts = []

    def fake(prompt, cfg):
        prompts.append(prompt)
        return "Hello world"

    monkeypatch.setattr(f, "_llm_generate", fake)
    cfg = FormatConfig(llm_enabled=True)
    out = format_text("Переведи на английский, привет мир", cfg)
    assert out == "Hello world"
    assert "Translate" in prompts[0]


def test_translate_command_inert_without_llm():
    cfg = FormatConfig(llm_enabled=False)
    out = format_text("переведи на английский привет мир", cfg)
    assert "переведи" in out.lower()  # phrase passes through untouched
