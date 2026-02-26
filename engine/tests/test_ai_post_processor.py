"""Tests for the AI script post-processor."""
from __future__ import annotations

from hypnoai.ai.post_processor import (
    PostProcessResult,
    estimate_duration,
    fix_syntax,
    pacing_analysis,
    process,
    safety_scan,
    structure_check,
)

# Minimal well-formed script for reuse in tests
_GOOD_SCRIPT = """\
@{section: Induction}

Welcome. Allow yourself to relax and breathe deeply.

@{pause: 3s}

@{section: Deepening}

With each breath, allow yourself to drift deeper.

@{pause: 5s}

@{section: Main}

You may notice a sense of calm spreading through your body.

@{pause: 3s}

@{section: Emergence}

Slowly returning now. Wide awake, fully present.
Count with me: one, two, three, four, five. Open your eyes.
"""


class TestFixSyntax:
    def test_no_changes_needed(self):
        script = "@{pause: 3s}\n\nHello world."
        fixed, fixes = fix_syntax(script)
        assert fixed == script
        assert fixes == []

    def test_fixes_missing_colon(self):
        script = "@{pause 5s}"
        fixed, fixes = fix_syntax(script)
        assert "@{pause: 5s}" in fixed
        assert len(fixes) > 0

    def test_fixes_leading_space_in_braces(self):
        script = "@{ pause: 3s}"
        fixed, fixes = fix_syntax(script)
        assert "@{" in fixed
        assert not fixed.startswith("@{ ")

    def test_fixes_trailing_space_in_braces(self):
        script = "@{pause: 3s }"
        fixed, fixes = fix_syntax(script)
        assert "3s }" not in fixed

    def test_returns_tuple(self):
        result = fix_syntax("Hello.")
        assert isinstance(result, tuple)
        assert len(result) == 2


class TestSafetyScan:
    def test_clean_script_no_warnings(self):
        issues = safety_scan(_GOOD_SCRIPT)
        assert issues == []

    def test_detects_you_must(self):
        script = "You must relax now."
        issues = safety_scan(script)
        assert any("you must" in w for w in issues)

    def test_detects_you_will(self):
        script = "You will feel calm."
        issues = safety_scan(script)
        assert any("you will" in w for w in issues)

    def test_detects_obey(self):
        script = "Obey the sound of my voice."
        issues = safety_scan(script)
        assert any("obey" in w for w in issues)

    def test_case_insensitive(self):
        issues = safety_scan("YOU MUST RELAX")
        assert len(issues) > 0

    def test_returns_list(self):
        assert isinstance(safety_scan("Hello."), list)


class TestStructureCheck:
    def test_good_script_passes(self):
        has_i, has_e, warnings = structure_check(_GOOD_SCRIPT)
        assert has_i is True
        assert has_e is True
        assert warnings == []

    def test_detects_missing_induction(self):
        script = "Ten, nine, eight...\n\nOpen your eyes. Wide awake."
        has_i, has_e, warnings = structure_check(script)
        assert has_i is False
        assert any("induction" in w.lower() for w in warnings)

    def test_detects_missing_emergence(self):
        script = "Allow yourself to relax and breathe deeply.\n\nYou feel calm."
        has_i, has_e, warnings = structure_check(script)
        assert has_e is False
        assert any("emergence" in w.lower() or "awakening" in w.lower() for w in warnings)

    def test_returns_tuple_of_three(self):
        result = structure_check("Hello.")
        assert isinstance(result, tuple)
        assert len(result) == 3


class TestEstimateDuration:
    def test_empty_script(self):
        assert estimate_duration("") == 0.0

    def test_only_pauses(self):
        script = "@{pause: 60s}\n@{pause: 60s}"
        duration = estimate_duration(script)
        assert abs(duration - 2.0) < 0.1

    def test_pause_ms_conversion(self):
        script = "@{pause: 500ms}"
        duration = estimate_duration(script)
        # 500ms = 0.5s / 60 ≈ 0.008 min
        assert duration < 0.1

    def test_words_only(self):
        # 70 words at 70 WPM = 1.0 minute
        words = " ".join(["word"] * 70)
        duration = estimate_duration(words)
        assert abs(duration - 1.0) < 0.1

    def test_directives_not_counted_as_words(self):
        script = "@{voice: calm}\n@{speed: 0.85}\n\nHello world."
        duration = estimate_duration(script)
        # Only "Hello world." = 2 words
        assert duration < 0.1

    def test_combined_speech_and_pauses(self):
        # 70 words (1 min speech) + 60s pause (1 min)
        words = " ".join(["word"] * 70)
        script = words + "\n@{pause: 60s}"
        duration = estimate_duration(script)
        assert abs(duration - 2.0) < 0.2


class TestPacingAnalysis:
    def test_short_paragraphs_not_flagged(self):
        script = "Short paragraph.\n\nAnother short one."
        result = pacing_analysis(script)
        assert result == []

    def test_long_paragraph_flagged(self):
        long_para = " ".join(["word"] * 130)  # > 120 words
        result = pacing_analysis(long_para)
        assert 0 in result

    def test_directive_paragraphs_not_flagged(self):
        script = "@{pause: 5s}"
        result = pacing_analysis(script)
        assert result == []

    def test_multiple_paragraphs_some_long(self):
        short = "This is a short paragraph."
        long = " ".join(["word"] * 130)
        script = f"{short}\n\n{long}\n\n{short}"
        result = pacing_analysis(script)
        assert 1 in result
        assert 0 not in result
        assert 2 not in result

    def test_returns_list(self):
        assert isinstance(pacing_analysis("Hello."), list)


class TestProcess:
    def test_returns_post_process_result(self):
        result = process(_GOOD_SCRIPT)
        assert isinstance(result, PostProcessResult)

    def test_good_script_minimal_warnings(self):
        result = process(_GOOD_SCRIPT)
        # Safety and pacing should be clean; may have structure warnings
        safety_warnings = [w for w in result.warnings if "authoritarian" in w]
        assert safety_warnings == []

    def test_script_preserved(self):
        result = process(_GOOD_SCRIPT)
        # Core content should be unchanged (only syntax might be fixed)
        assert "relax" in result.script.lower()

    def test_duration_positive(self):
        result = process(_GOOD_SCRIPT)
        assert result.estimated_duration_minutes > 0

    def test_syntax_fix_applied(self):
        script = "@{pause 5s}\n\nAllow yourself to relax and breathe. Wide awake."
        result = process(script)
        assert "@{pause: 5s}" in result.script
        assert any("Auto-fixed" in w for w in result.warnings)

    def test_safety_warning_for_authoritarian_language(self):
        script = _GOOD_SCRIPT + "\nYou must obey."
        result = process(script)
        assert any("authoritarian" in w.lower() for w in result.warnings)

    def test_structure_warning_for_missing_emergence(self):
        script = "Allow yourself to relax and breathe deeply.\n\nYou feel calm."
        result = process(script)
        assert any("emergence" in w.lower() or "awakening" in w.lower() for w in result.warnings)

    def test_german_language_parameter_accepted(self):
        result = process(_GOOD_SCRIPT, language="de")
        assert isinstance(result, PostProcessResult)

    def test_fast_paragraphs_detected(self):
        long_para = " ".join(["word"] * 130)
        script = f"Relax and breathe.\n\n{long_para}\n\nWide awake. Open your eyes."
        result = process(script)
        assert len(result.fast_pace_paragraphs) > 0
        assert any("exceed" in w for w in result.warnings)

    def test_has_induction_and_emergence_flags(self):
        result = process(_GOOD_SCRIPT)
        assert result.has_induction is True
        assert result.has_emergence is True
