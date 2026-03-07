"""Post-processing and validation of LLM-generated HypnoScript."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# Words-per-minute threshold above which a paragraph is flagged as too fast.
# German has longer compound words so fewer WPM = same spoken rate.
_WPM_THRESHOLDS: dict[str, float] = {
    "en": 80.0,
    "de": 65.0,
}
_DEFAULT_WPM_THRESHOLD = 80.0

# Paragraphs with more than this many words are always flagged regardless of WPM.
_MAX_PARAGRAPH_WORDS = 120

# Patterns considered authoritarian or potentially unsafe for hypnotherapy.
_AUTHORITARIAN_PATTERNS = [
    r"\byou must\b",
    r"\byou will\b",
    r"\byou have to\b",
    r"\byou need to\b",
    r"\bdo it now\b",
    r"\bobey\b",
    r"\bcommand you\b",
    r"\binstruct you\b",
    r"\byou are forced\b",
]

# Common LLM HypnoScript syntax mistakes to fix automatically.
# Each entry is (regex_pattern, replacement).
_SYNTAX_FIXES: list[tuple[str, str]] = [
    # Missing colon: @{pause 5s} → @{pause: 5s}
    (r"@\{(\w+)\s+([^}:][^}]*)\}", r"@{\1: \2}"),
    # Trailing/leading spaces inside braces: @{ pause: 5s } → @{pause: 5s}
    (r"@\{\s+", r"@{"),
    (r"\s+\}", r"}"),
]

# Keywords that indicate an induction section.
_INDUCTION_KEYWORDS = [
    "relax",
    "breathe",
    "close your eyes",
    "settle",
    "comfortable",
    "welcome",
    "allow yourself",
    "take a deep breath",
    "let yourself",
]

# Keywords that indicate an emergence/awakening section.
_EMERGENCE_KEYWORDS = [
    "awaken",
    "awakening",
    "wide awake",
    "open your eyes",
    "fully alert",
    "come back",
    "returning",
    "three two one",
    "3 2 1",
    "count up",
    "one two three",
    "1 2 3",
    "slowly returning",
    "fully present",
]


@dataclass
class PostProcessResult:
    """Results from the AI script post-processor."""

    script: str
    warnings: list[str] = field(default_factory=list)
    estimated_duration_minutes: float = 0.0
    fast_pace_paragraphs: list[int] = field(default_factory=list)
    has_induction: bool = False
    has_emergence: bool = False


def fix_syntax(script: str) -> tuple[str, list[str]]:
    """Fix common LLM HypnoScript syntax mistakes.

    Returns:
        (fixed_script, list_of_applied_fix_descriptions)
    """
    fixes: list[str] = []
    result = script
    for pattern, replacement in _SYNTAX_FIXES:
        new = re.sub(pattern, replacement, result)
        if new != result:
            fixes.append(f"Auto-fixed directive syntax ({pattern!r})")
            result = new
    return result, fixes


def safety_scan(script: str) -> list[str]:
    """Scan for authoritarian or potentially unsafe language patterns."""
    issues: list[str] = []
    lower = script.lower()
    for pattern in _AUTHORITARIAN_PATTERNS:
        if re.search(pattern, lower):
            issues.append(
                f"Warning: potentially authoritarian language detected ({pattern.strip()}). "
                "Consider replacing with permissive phrasing."
            )
    return issues


def structure_check(script: str) -> tuple[bool, bool, list[str]]:
    """Check for required structural elements.

    Returns:
        (has_induction, has_emergence, warning_messages)
    """
    warnings_out: list[str] = []
    lower = script.lower()

    has_induction = any(kw in lower for kw in _INDUCTION_KEYWORDS)
    has_emergence = any(kw in lower for kw in _EMERGENCE_KEYWORDS)

    if not has_induction:
        warnings_out.append(
            "No induction section detected. "
            "Consider adding breathing/settling cues at the start."
        )
    if not has_emergence:
        warnings_out.append(
            "No emergence/awakening section detected. "
            "Always end with grounding cues (except sleep inductions)."
        )

    return has_induction, has_emergence, warnings_out


def estimate_duration(script: str) -> float:
    """Estimate script duration in minutes.

    Assumes 70 WPM for spoken sections (comfortable hypnosis pacing).
    """
    words = 0
    pause_seconds = 0.0

    for line in script.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"@\{pause:\s*(\d+(?:\.\d+)?)(s|ms)\}", line)
        if m:
            val, unit = float(m.group(1)), m.group(2)
            pause_seconds += val / 1000.0 if unit == "ms" else val
        elif not line.startswith("@{"):
            words += len(line.split())

    return words / 70.0 + pause_seconds / 60.0


def pacing_analysis(script: str, language: str = "en") -> list[int]:
    """Return 0-based indices of paragraphs that are too dense.

    A paragraph is flagged if it exceeds _MAX_PARAGRAPH_WORDS words,
    which at the language-specific WPM threshold would take too long.
    """
    fast: list[int] = []
    paragraphs = [p.strip() for p in script.split("\n\n") if p.strip()]
    for i, para in enumerate(paragraphs):
        if para.startswith("@{"):
            continue
        word_count = len(para.split())
        if word_count > _MAX_PARAGRAPH_WORDS:
            fast.append(i)
    return fast


def process(script: str, language: str = "en") -> PostProcessResult:
    """Run the full post-processing pipeline on a generated script."""
    all_warnings: list[str] = []

    # 1. Syntax fix
    fixed_script, syntax_fixes = fix_syntax(script)
    all_warnings.extend(syntax_fixes)

    # 2. Safety scan
    all_warnings.extend(safety_scan(fixed_script))

    # 3. Structure check
    has_induction, has_emergence, structure_issues = structure_check(fixed_script)
    all_warnings.extend(structure_issues)

    # 4. Duration estimate
    duration = estimate_duration(fixed_script)

    # 5. Pacing analysis
    fast_paras = pacing_analysis(fixed_script, language)
    if fast_paras:
        indices = ", ".join(str(i) for i in fast_paras)
        all_warnings.append(
            f"Paragraphs at positions [{indices}] exceed {_MAX_PARAGRAPH_WORDS} words. "
            "Consider splitting for better pacing."
        )

    return PostProcessResult(
        script=fixed_script,
        warnings=all_warnings,
        estimated_duration_minutes=round(duration, 1),
        fast_pace_paragraphs=fast_paras,
        has_induction=has_induction,
        has_emergence=has_emergence,
    )
