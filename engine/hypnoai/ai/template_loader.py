"""Loads HypnoScript prompt templates from TOML files."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

_TEMPLATES_DIR = Path(__file__).parent / "templates"

AVAILABLE_TEMPLATES = [
    "progressive_relaxation",
    "sleep_induction",
    "focus_enhancement",
    "habit_change",
    "anxiety_relief",
    "confidence_boost",
    "pain_management",
    "custom",
]

SUPPORTED_LANGUAGES = ["en", "de"]


@dataclass
class PromptTemplate:
    """A loaded prompt template ready for use."""

    id: str
    name: str
    category: str
    language: str
    system_prompt: str
    user_prompt_template: str
    default_variables: dict[str, str] = field(default_factory=dict)
    validation_rules: list[str] = field(default_factory=list)


def load_template(template_id: str, language: str = "en") -> PromptTemplate:
    """Load a prompt template by ID and language.

    Falls back to English if no variant exists for the requested language.

    Raises:
        ValueError: If *template_id* is not in AVAILABLE_TEMPLATES.
        FileNotFoundError: If the TOML file is missing.
    """
    if template_id not in AVAILABLE_TEMPLATES:
        raise ValueError(
            f"Unknown template: {template_id!r}. "
            f"Available: {AVAILABLE_TEMPLATES}"
        )

    lang = language if language in SUPPORTED_LANGUAGES else "en"
    toml_path = _TEMPLATES_DIR / template_id / f"{lang}.toml"

    if not toml_path.exists():
        # Fallback to English
        toml_path = _TEMPLATES_DIR / template_id / "en.toml"

    if not toml_path.exists():
        raise FileNotFoundError(f"Template file not found: {toml_path}")

    with open(toml_path, "rb") as f:
        data = tomllib.load(f)

    return PromptTemplate(
        id=data["id"],
        name=data["name"],
        category=data["category"],
        language=data["language"],
        system_prompt=data["system_prompt"],
        user_prompt_template=data["user_prompt_template"],
        default_variables=data.get("default_variables", {}),
        validation_rules=data.get("validation_rules", []),
    )


def list_templates() -> list[dict[str, str]]:
    """Return summary metadata for all available templates (English variants)."""
    result = []
    for template_id in AVAILABLE_TEMPLATES:
        try:
            t = load_template(template_id, "en")
            result.append({"id": t.id, "name": t.name, "category": t.category})
        except FileNotFoundError:
            pass
    return result
