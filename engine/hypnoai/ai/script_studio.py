"""AI Script Studio — orchestrates template + LLM + post-processing."""
from __future__ import annotations

import re

from . import post_processor as pp
from .base import GenerationResult, LLMProvider, ScriptGenerationRequest
from .template_loader import load_template

# Matches a simple {identifier} placeholder (no colon, no spaces).
# This deliberately does NOT match:
#   @{section: Title}   → contains ':'
#   @{pause: 3s}        → contains ':'
#   @{speed: 0.85}      → contains ':'
# It also does NOT touch {{...}} double-brace HypnoScript variables because
# those are pre-protected with sentinels before the regex runs.
_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")

_LANG_NAMES: dict[str, str] = {
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}


def _expand_template(text: str, substitutions: dict[str, str]) -> str:
    """Substitute ``{key}`` placeholders while leaving ``{{...}}`` and
    ``@{...}`` HypnoScript directives completely untouched.

    Algorithm:
    1. Temporarily replace ``{{`` / ``}}`` with sentinel strings so the
       double-brace pairs are invisible to the regex.
    2. Replace simple ``{identifier}`` patterns from *substitutions*;
       leave any unrecognised keys intact.
    3. Restore the sentinels back to ``{{`` / ``}}``.
    """
    _L, _R = "\x00LB\x00", "\x00RB\x00"
    text = text.replace("{{", _L).replace("}}", _R)

    def _replace(m: re.Match) -> str:
        key = m.group(1)
        return substitutions.get(key, m.group(0))

    text = _PLACEHOLDER_RE.sub(_replace, text)
    return text.replace(_L, "{{").replace(_R, "}}")


class ScriptStudio:
    """Generates HypnoScript drafts from user intent using an LLM provider."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def generate(self, request: ScriptGenerationRequest) -> GenerationResult:
        """Generate a HypnoScript draft and post-process it.

        Args:
            request: Generation parameters (template, language, duration, theme, …).

        Returns:
            A GenerationResult with the processed script and any warnings.
        """
        template = load_template(request.template_id, request.language)

        # If we fell back to English for a non-English request, add an instruction.
        system_prompt = template.system_prompt
        if request.language != "en" and template.language == "en":
            lang_name = _LANG_NAMES.get(request.language, request.language)
            system_prompt += f"\n\nIMPORTANT: Write the entire script in {lang_name}."

        # Merge template defaults with request variables, request takes priority.
        # These are passed as single-brace {key} substitutions in the user_prompt_template.
        merged_vars: dict[str, str] = {
            "duration": str(request.duration_minutes),
            "theme": request.theme,
            "session_type": request.session_type,
            **template.default_variables,
            **request.variables,
        }

        # Expand {key} placeholders safely without touching @{...} directives
        # or {{name}} HypnoScript variable syntax.
        user_prompt = _expand_template(template.user_prompt_template, merged_vars)

        # Call the LLM.
        raw_script = self._provider.generate(system_prompt, user_prompt)

        # Post-process the output.
        result = pp.process(raw_script, language=request.language)

        return GenerationResult(
            script=result.script,
            warnings=result.warnings,
            estimated_duration_minutes=result.estimated_duration_minutes,
            fast_pace_paragraphs=result.fast_pace_paragraphs,
        )
