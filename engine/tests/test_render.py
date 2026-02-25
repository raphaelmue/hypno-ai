"""Tests for the render pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import soundfile as sf

from hypnoai.parser.ast_nodes import (
    CommentBlock,
    PauseBlock,
    PitchChangeBlock,
    SectionBlock,
    SpeedChangeBlock,
    TextBlock,
    UnknownDirectiveBlock,
    VoiceChangeBlock,
)
from hypnoai.render.cache import RenderCache
from hypnoai.render.pipeline import RenderPipeline


class TestRenderPipeline:
    def test_empty_blocks_returns_empty_job(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        job = pipeline.render([], tmp_path, initial_voice="voice")
        assert job.chunk_paths == []
        assert mock_engine.calls == []

    def test_single_text_block_calls_engine(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [TextBlock(text="Hello world.", line=1)]
        job = pipeline.render(blocks, tmp_path, initial_voice="test-voice")
        assert len(job.chunk_paths) == 1
        assert len(mock_engine.calls) == 1
        assert mock_engine.calls[0] == ("Hello world.", "test-voice", 1.0)

    def test_chunk_file_is_created(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [TextBlock(text="Hello.", line=1)]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        assert job.chunk_paths[0].exists()

    def test_pause_generates_silence(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, sample_rate=22050)
        blocks = [PauseBlock(duration_s=2.0, line=1)]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        assert len(job.chunk_paths) == 1
        data, sr = sf.read(str(job.chunk_paths[0]))
        assert sr == 22050
        expected_samples = 2.0 * 22050
        assert len(data) == pytest.approx(expected_samples, abs=1)
        assert np.all(data == 0.0)

    def test_pause_duration_zero(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, sample_rate=22050)
        blocks = [PauseBlock(duration_s=0.0, line=1)]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        data, _ = sf.read(str(job.chunk_paths[0]))
        assert len(data) == 0

    def test_voice_change_updates_voice(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            TextBlock(text="First.", line=1),
            VoiceChangeBlock(voice_id="new-voice", line=2),
            TextBlock(text="Second.", line=3),
        ]
        pipeline.render(blocks, tmp_path, initial_voice="initial-voice")
        assert mock_engine.calls[0][1] == "initial-voice"
        assert mock_engine.calls[1][1] == "new-voice"

    def test_speed_change_updates_speed(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            TextBlock(text="Normal.", line=1),
            SpeedChangeBlock(speed=0.8, line=2),
            TextBlock(text="Slow.", line=3),
        ]
        pipeline.render(blocks, tmp_path, initial_voice="voice")
        assert mock_engine.calls[0][2] == pytest.approx(1.0)
        assert mock_engine.calls[1][2] == pytest.approx(0.8)

    def test_initial_speed_applied(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [TextBlock(text="Test.", line=1)]
        pipeline.render(blocks, tmp_path, initial_voice="voice", initial_speed=0.9)
        assert mock_engine.calls[0][2] == pytest.approx(0.9)

    def test_comment_is_skipped(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            CommentBlock(text="Author note", line=1),
            TextBlock(text="Hello.", line=2),
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        assert len(job.chunk_paths) == 1
        assert len(mock_engine.calls) == 1

    def test_unknown_directive_is_skipped(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            UnknownDirectiveBlock(key="music", value="start", line=1),
            TextBlock(text="Hello.", line=2),
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        assert len(job.chunk_paths) == 1

    def test_sections_recorded_in_order(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            SectionBlock(title="Intro", line=1),
            TextBlock(text="Hello.", line=2),
            SectionBlock(title="Body", line=3),
            TextBlock(text="World.", line=4),
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        section_titles = [s[1] for s in job.sections]
        assert section_titles == ["Intro", "Body"]

    def test_section_chunk_index_before_next_text(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            TextBlock(text="A.", line=1),  # chunk 0
            SectionBlock(title="Part 2", line=2),
            TextBlock(text="B.", line=3),  # chunk 1
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        # Section recorded at chunk index 1 (before "B." is rendered)
        assert job.sections[0] == (1, "Part 2")

    def test_chunks_named_sequentially(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            TextBlock(text="A", line=1),
            PauseBlock(duration_s=1.0, line=2),
            TextBlock(text="B", line=3),
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="voice")
        names = [p.name for p in job.chunk_paths]
        assert names == ["000.wav", "001.wav", "002.wav"]

    def test_output_dir_created_if_missing(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        output_dir = tmp_path / "nested" / "chunks"
        blocks = [TextBlock(text="Hello.", line=1)]
        pipeline.render(blocks, output_dir, initial_voice="voice")
        assert output_dir.exists()

    def test_multiple_voice_changes(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        blocks = [
            VoiceChangeBlock(voice_id="voice-a", line=1),
            TextBlock(text="A.", line=2),
            VoiceChangeBlock(voice_id="voice-b", line=3),
            TextBlock(text="B.", line=4),
            VoiceChangeBlock(voice_id="voice-c", line=5),
            TextBlock(text="C.", line=6),
        ]
        pipeline.render(blocks, tmp_path, initial_voice="initial")
        voices = [c[1] for c in mock_engine.calls]
        assert voices == ["voice-a", "voice-b", "voice-c"]

    def test_job_id_recorded(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine)
        job = pipeline.render([], tmp_path, initial_voice="v", job_id="my-job")
        assert job.job_id == "my-job"


class TestRenderPipelinePhase2:
    """Phase 2: pitch, cache, parallel path."""

    # ------------------------------------------------------------------
    # PitchChangeBlock
    # ------------------------------------------------------------------

    def test_pitch_change_updates_initial_pitch(self, tmp_path, mock_engine):
        from unittest.mock import patch

        pipeline = RenderPipeline(mock_engine)
        blocks = [
            PitchChangeBlock(semitones=-2.0, line=1),
            TextBlock(text="Hello.", line=2),
        ]
        with patch("hypnoai.render.pipeline._apply_pitch_shift") as mock_shift:
            pipeline.render(blocks, tmp_path, initial_voice="v")
        mock_shift.assert_called_once()
        _, semitones = mock_shift.call_args[0]
        assert semitones == pytest.approx(-2.0)

    def test_initial_pitch_applied(self, tmp_path, mock_engine):
        from unittest.mock import patch

        pipeline = RenderPipeline(mock_engine)
        blocks = [TextBlock(text="Test.", line=1)]
        with patch("hypnoai.render.pipeline._apply_pitch_shift") as mock_shift:
            pipeline.render(blocks, tmp_path, initial_voice="v", initial_pitch=-1.5)
        mock_shift.assert_called_once()
        _, semitones = mock_shift.call_args[0]
        assert semitones == pytest.approx(-1.5)

    def test_zero_pitch_skips_pitch_shift(self, tmp_path, mock_engine):
        from unittest.mock import patch

        pipeline = RenderPipeline(mock_engine)
        blocks = [TextBlock(text="Test.", line=1)]
        with patch("hypnoai.render.pipeline._apply_pitch_shift") as mock_shift:
            pipeline.render(blocks, tmp_path, initial_voice="v", initial_pitch=0.0)
        mock_shift.assert_not_called()

    def test_pitch_reset_by_subsequent_pitch_block(self, tmp_path, mock_engine):
        from unittest.mock import patch

        pipeline = RenderPipeline(mock_engine)
        blocks = [
            PitchChangeBlock(semitones=-2.0, line=1),
            TextBlock(text="A.", line=2),
            PitchChangeBlock(semitones=0.0, line=3),
            TextBlock(text="B.", line=4),
        ]
        with patch("hypnoai.render.pipeline._apply_pitch_shift") as mock_shift:
            pipeline.render(blocks, tmp_path, initial_voice="v")
        # Only first text block should trigger pitch shift
        assert mock_shift.call_count == 1

    # ------------------------------------------------------------------
    # Cache integration
    # ------------------------------------------------------------------

    def test_cache_hit_skips_engine(self, tmp_path, mock_engine):
        cache = RenderCache(tmp_path / "cache")
        # Pre-populate cache for the text block we're about to render
        key = cache.cache_key("Hello.", "v", 1.0, 0.0)
        cached_wav = tmp_path / "cached.wav"
        sf.write(str(cached_wav), np.zeros(100, dtype=np.float32), 22050, subtype="FLOAT")
        cache.put(key, cached_wav)

        pipeline = RenderPipeline(mock_engine, cache=cache)
        blocks = [TextBlock(text="Hello.", line=1)]
        pipeline.render(blocks, tmp_path / "out", initial_voice="v")
        assert mock_engine.calls == []

    def test_cache_stores_rendered_chunk(self, tmp_path, mock_engine):
        cache = RenderCache(tmp_path / "cache")
        pipeline = RenderPipeline(mock_engine, cache=cache)
        blocks = [TextBlock(text="Hello.", line=1)]
        pipeline.render(blocks, tmp_path / "out", initial_voice="v")
        key = cache.cache_key("Hello.", "v", 1.0, 0.0)
        assert cache.get(key) is not None

    # ------------------------------------------------------------------
    # Parallel path
    # ------------------------------------------------------------------

    def test_parallel_path_selected_when_max_workers_gt_1(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, max_workers=2)
        blocks = [TextBlock(text="Hello.", line=1)]
        job = pipeline.render(blocks, tmp_path, initial_voice="v")
        assert len(job.chunk_paths) == 1
        assert len(mock_engine.calls) == 1

    def test_parallel_path_preserves_chunk_order(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, max_workers=4)
        blocks = [TextBlock(text=f"Chunk {i}.", line=i) for i in range(5)]
        job = pipeline.render(blocks, tmp_path, initial_voice="v")
        assert len(job.chunk_paths) == 5
        names = [p.name for p in job.chunk_paths]
        assert names == ["000.wav", "001.wav", "002.wav", "003.wav", "004.wav"]

    def test_parallel_path_handles_pause_blocks(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, max_workers=2)
        blocks = [
            TextBlock(text="A.", line=1),
            PauseBlock(duration_s=1.0, line=2),
            TextBlock(text="B.", line=3),
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="v")
        assert len(job.chunk_paths) == 3
        data, sr = sf.read(str(job.chunk_paths[1]))
        assert np.all(data == 0.0)

    def test_parallel_path_handles_voice_change(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, max_workers=2)
        blocks = [
            TextBlock(text="First.", line=1),
            VoiceChangeBlock(voice_id="new-voice", line=2),
            TextBlock(text="Second.", line=3),
        ]
        pipeline.render(blocks, tmp_path, initial_voice="old-voice")
        voices = [c[1] for c in mock_engine.calls]
        assert "old-voice" in voices
        assert "new-voice" in voices

    def test_parallel_path_sections_recorded(self, tmp_path, mock_engine):
        pipeline = RenderPipeline(mock_engine, max_workers=2)
        blocks = [
            SectionBlock(title="Intro", line=1),
            TextBlock(text="Hello.", line=2),
        ]
        job = pipeline.render(blocks, tmp_path, initial_voice="v")
        assert len(job.sections) == 1
        assert job.sections[0][1] == "Intro"
