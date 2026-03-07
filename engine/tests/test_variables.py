"""Tests for variable injection."""
from __future__ import annotations

import warnings

from hypnoai.parser.variables import find_variables, inject_variables


# ---------------------------------------------------------------------------
# inject_variables
# ---------------------------------------------------------------------------


def test_no_placeholders():
    result = inject_variables("Hello world.", {})
    assert result == "Hello world."


def test_single_variable():
    result = inject_variables("Hello {{name}}!", {"name": "Sarah"})
    assert result == "Hello Sarah!"


def test_multiple_different_variables():
    result = inject_variables("{{greeting}}, {{name}}!", {"greeting": "Hi", "name": "Bob"})
    assert result == "Hi, Bob!"


def test_repeated_variable_both_replaced():
    result = inject_variables("{{name}} and {{name}}", {"name": "Alice"})
    assert result == "Alice and Alice"


def test_undefined_variable_emits_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = inject_variables("Hello {{name}}!", {})
    assert any("Undefined variable" in str(w.message) for w in caught)
    assert result == "Hello {{name}}!"  # unchanged


def test_undefined_variable_warning_contains_variable_name():
    """Warning message must show the actual variable name, not the literal text 'key'."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        inject_variables("Hello {{myvar}}!", {})
    messages = [str(w.message) for w in caught]
    assert any("myvar" in m for m in messages), f"Variable name missing from: {messages}"
    assert not any("{{{key}}}" in m for m in messages), "Bug: literal 'key' shown instead of variable name"


def test_undefined_variable_leaves_placeholder():
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = inject_variables("{{missing}}", {})
    assert result == "{{missing}}"


def test_partial_variables_defined():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = inject_variables("{{name}} loves {{place}}.", {"name": "Tom"})
    assert result == "Tom loves {{place}}."
    assert any("Undefined variable" in str(w.message) for w in caught)


def test_numeric_value():
    result = inject_variables("Session {{count}} of 10.", {"count": "3"})
    assert result == "Session 3 of 10."


def test_value_with_spaces():
    result = inject_variables("Go to {{place}}.", {"place": "the sunlit meadow"})
    assert result == "Go to the sunlit meadow."


def test_multiline_text():
    text = "Hello {{name}}.\n\nYou are at {{place}}."
    result = inject_variables(text, {"name": "Sarah", "place": "the beach"})
    assert result == "Hello Sarah.\n\nYou are at the beach."


def test_extra_variables_ignored():
    result = inject_variables("Hello {{name}}.", {"name": "Alice", "unused": "ignored"})
    assert result == "Hello Alice."


def test_empty_string_value():
    result = inject_variables("Hello {{name}}!", {"name": ""})
    assert result == "Hello !"


# ---------------------------------------------------------------------------
# find_variables
# ---------------------------------------------------------------------------


def test_find_variables_empty():
    assert find_variables("No variables here.") == []


def test_find_variables_single():
    assert find_variables("Hello {{name}}!") == ["name"]


def test_find_variables_multiple():
    found = find_variables("{{a}} and {{b}}")
    assert found == ["a", "b"]


def test_find_variables_preserves_duplicates():
    found = find_variables("{{a}} and {{b}} and {{a}}")
    assert found == ["a", "b", "a"]


def test_find_variables_in_script():
    script = (
        "@{voice: calm}\n"
        "Hello {{name}}.\n"
        "\n"
        "Your safe place is {{safe_place}}."
    )
    found = find_variables(script)
    assert "name" in found
    assert "safe_place" in found
