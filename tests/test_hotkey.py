from flowlocal.hotkey import normalize_combo


def test_bare_named_keys_get_wrapped():
    assert normalize_combo("ctrl+alt+space") == "<ctrl>+<alt>+<space>"


def test_old_default_with_bare_space_is_fixed():
    assert normalize_combo("<ctrl>+<alt>+space") == "<ctrl>+<alt>+<space>"


def test_already_valid_combo_unchanged():
    assert normalize_combo("<ctrl>+<alt>+<space>") == "<ctrl>+<alt>+<space>"
    assert normalize_combo("<f9>") == "<f9>"


def test_single_char_keys_stay_bare():
    assert normalize_combo("<ctrl>+j") == "<ctrl>+j"


def test_whitespace_and_case_normalized():
    assert normalize_combo(" CTRL + <alt> + F9 ") == "<ctrl>+<alt>+<f9>"
