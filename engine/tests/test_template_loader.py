"""Tests for the prompt template loader."""
from __future__ import annotations

import pytest

from hypnoai.ai.template_loader import (
    AVAILABLE_TEMPLATES,
    SUPPORTED_LANGUAGES,
    PromptTemplate,
    list_templates,
    load_template,
)


class TestLoadTemplate:
    def test_loads_english_template(self):
        t = load_template("custom", "en")
        assert isinstance(t, PromptTemplate)
        assert t.id == "custom"
        assert t.language == "en"

    def test_loads_german_template(self):
        t = load_template("custom", "de")
        assert t.language == "de"

    def test_loads_all_templates_english(self):
        for template_id in AVAILABLE_TEMPLATES:
            t = load_template(template_id, "en")
            assert t.id == template_id
            assert t.name
            assert t.category
            assert t.system_prompt
            assert t.user_prompt_template

    def test_loads_all_templates_german(self):
        for template_id in AVAILABLE_TEMPLATES:
            t = load_template(template_id, "de")
            assert t.id == template_id

    def test_falls_back_to_english_for_unsupported_language(self):
        t = load_template("custom", "fr")  # French not supported
        assert t.language == "en"

    def test_raises_for_unknown_template(self):
        with pytest.raises(ValueError, match="Unknown template"):
            load_template("nonexistent_template")

    def test_template_has_default_variables(self):
        t = load_template("progressive_relaxation", "en")
        assert isinstance(t.default_variables, dict)
        assert "name" in t.default_variables

    def test_template_has_validation_rules(self):
        t = load_template("progressive_relaxation", "en")
        assert isinstance(t.validation_rules, list)
        assert len(t.validation_rules) > 0

    def test_user_prompt_contains_duration_placeholder(self):
        t = load_template("custom", "en")
        assert "{duration}" in t.user_prompt_template

    def test_user_prompt_contains_theme_placeholder(self):
        t = load_template("custom", "en")
        assert "{theme}" in t.user_prompt_template

    def test_progressive_relaxation_en(self):
        t = load_template("progressive_relaxation", "en")
        assert t.category == "relaxation"

    def test_sleep_induction_en(self):
        t = load_template("sleep_induction", "en")
        assert t.category == "sleep"

    def test_focus_enhancement_en(self):
        t = load_template("focus_enhancement", "en")
        assert t.category == "focus"

    def test_habit_change_en(self):
        t = load_template("habit_change", "en")
        assert t.category == "habit"

    def test_anxiety_relief_en(self):
        t = load_template("anxiety_relief", "en")
        assert t.category == "anxiety"

    def test_confidence_boost_en(self):
        t = load_template("confidence_boost", "en")
        assert t.category == "self-esteem"

    def test_pain_management_en(self):
        t = load_template("pain_management", "en")
        assert t.category == "pain"


class TestListTemplates:
    def test_returns_all_templates(self):
        templates = list_templates()
        ids = [t["id"] for t in templates]
        for tid in AVAILABLE_TEMPLATES:
            assert tid in ids

    def test_each_entry_has_required_keys(self):
        templates = list_templates()
        for t in templates:
            assert "id" in t
            assert "name" in t
            assert "category" in t

    def test_returns_list_of_dicts(self):
        templates = list_templates()
        assert isinstance(templates, list)
        assert all(isinstance(t, dict) for t in templates)


class TestAvailableConstants:
    def test_available_templates_count(self):
        assert len(AVAILABLE_TEMPLATES) == 8

    def test_supported_languages(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert "de" in SUPPORTED_LANGUAGES
