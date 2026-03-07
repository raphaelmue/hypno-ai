"""ai.generate handler — streaming LLM script generation."""
from __future__ import annotations

from typing import Any, Generator

from ...ai.base import ScriptGenerationRequest
from ...ai.script_studio import ScriptStudio, _expand_template
from ...ai import post_processor as pp
from ...ai.template_loader import AVAILABLE_TEMPLATES, load_template
from ...config import Config
from ..session import SidecarSession

_LANG_NAMES: dict[str, str] = {
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}


def _build_provider(provider_name: str, cfg: Config):
    """Instantiate an LLM provider (matching cli._build_llm_provider)."""
    if provider_name == "ollama":
        from ...ai.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=cfg.ollama_url, model=cfg.ollama_model)
    if provider_name == "openai":
        if not cfg.openai_api_key:
            raise PermissionError(
                "OpenAI API key not configured. Set 'openai_api_key' in hypnoai.toml."
            )
        from ...ai.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=cfg.openai_api_key,
            model=cfg.openai_model,
            base_url=cfg.openai_base_url,
        )
    if provider_name == "anthropic":
        if not cfg.anthropic_api_key:
            raise PermissionError(
                "Anthropic API key not configured. Set 'anthropic_api_key' in hypnoai.toml."
            )
        from ...ai.anthropic_provider import AnthropicProvider
        return AnthropicProvider(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model)
    raise ValueError(
        f"Unknown LLM provider: {provider_name!r}. Available: ollama, openai, anthropic."
    )


def handle_ai_generate(
    session: SidecarSession, params: dict[str, Any]
) -> Generator[dict, None, None]:
    """Generate a HypnoScript via an LLM (streaming).

    Optional params:
        template (str, default "custom")
        language (str, default "en")
        variables (dict, default {})
        provider (str, default from config)
        duration (int, minutes, default 20)
        theme (str, default "relaxation")

    Yields:
        {"chunk": "<text>"} for each streamed token
        {"done": True, "script": "<full>", "validation": {"warnings": [...]}}
    """
    cfg = Config.load()

    template_id = params.get("template", "custom")
    language = params.get("language", "en")
    variables: dict = params.get("variables", {})
    provider_name = params.get("provider", cfg.llm_provider)
    duration = int(params.get("duration", 20))
    theme = params.get("theme", "relaxation")

    if template_id not in AVAILABLE_TEMPLATES:
        raise ValueError(
            f"Unknown template {template_id!r}. "
            "Use 'hypnoai generate --list-templates' to see options."
        )

    llm = _build_provider(provider_name, cfg)
    if not llm.is_available():
        raise PermissionError(
            f"LLM provider '{provider_name}' is not available. "
            "Check that Ollama is running or your API key is configured."
        )

    template = load_template(template_id, language)

    # Mirror ScriptStudio._expand_template logic
    system_prompt = template.system_prompt
    if language != "en" and template.language == "en":
        lang_name = _LANG_NAMES.get(language, language)
        system_prompt += f"\n\nIMPORTANT: Write the entire script in {lang_name}."

    merged_vars: dict[str, str] = {
        "duration": str(duration),
        "theme": theme,
        "session_type": template_id.replace("_", " "),
        **template.default_variables,
        **{k: str(v) for k, v in variables.items()},
    }
    user_prompt = _expand_template(template.user_prompt_template, merged_vars)

    full_script = ""
    for chunk in llm.stream(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=0.7,
        max_tokens=4096,
    ):
        full_script += chunk
        yield {"chunk": chunk}

    # Post-process the complete script
    result = pp.process(full_script, language=language)

    yield {
        "done": True,
        "script": result.script,
        "validation": {"warnings": result.warnings},
    }
