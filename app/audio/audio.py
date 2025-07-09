import os
import uuid
import tempfile
import gc
from TTS.api import TTS
from pydub import AudioSegment
from app.config import OUTPUT_FOLDER
from app.utils import slugify

# Global TTS model instance to avoid reloading for each request
_tts_model = None

def get_tts_model():
    """Get or initialize the TTS model"""
    global _tts_model
    if _tts_model is None:
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    return _tts_model

def generate_audio(text, language, voice_path, routine_name=None):
    """Generate audio using XTTS-v2 with support for [break] markers and line breaks"""
    # Get the TTS model instance
    tts = get_tts_model()

    # Generate a filename based on the routine name or a UUID if no name is provided
    if routine_name:
        # Create a slug from the routine name
        slug = slugify(routine_name)
        output_filename = f"{slug}.wav"
    else:
        # Fallback to UUID if no name is provided
        output_filename = f"{uuid.uuid4()}.wav"

    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    # Create a temporary directory for segment audio files
    with tempfile.TemporaryDirectory() as temp_dir:
        segment_files = []

        # Check if text contains [break] markers
        if "[break]" in text:
            # Split text by [break] markers
            main_segments = text.split("[break]")

            # Process each main segment (separated by [break])
            for main_idx, main_segment in enumerate(main_segments):
                main_segment = main_segment.strip()
                if not main_segment:  # Skip empty segments
                    continue

                # Split each main segment by line breaks
                lines = main_segment.split('\n')

                # Process each line within the main segment
                for line_idx, line in enumerate(lines):
                    line = line.strip()
                    if not line:  # Skip empty lines
                        continue

                    # Skip section headers (e.g., "### Introduction ###")
                    if line.startswith("###"):
                        continue

                    segment_path = os.path.join(temp_dir, f"segment_{main_idx}_{line_idx}.wav")
                    tts.tts_to_file(
                        text=line,
                        file_path=segment_path,
                        speaker_wav=voice_path,
                        language=language
                    )
                    segment_files.append(segment_path)
                    # Force garbage collection after each TTS generation
                    gc.collect()
        else:
            # No [break] markers, but still process line breaks
            lines = text.split('\n')

            # Process each line
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:  # Skip empty lines
                    continue

                # Skip section headers (e.g., "### Introduction ###")
                if line.startswith("###"):
                    continue

                segment_path = os.path.join(temp_dir, f"segment_{i}.wav")
                tts.tts_to_file(
                    text=line,
                    file_path=segment_path,
                    speaker_wav=voice_path,
                    language=language
                )
                segment_files.append(segment_path)
                # Force garbage collection after each TTS generation
                gc.collect()

        # Combine audio segments with appropriate silences
        if segment_files:
            break_silence = AudioSegment.silent(duration=5000)  # 5 seconds of silence for [break]
            line_silence = AudioSegment.silent(duration=2000)   # 2 seconds of silence for line breaks

            # Process in batches to reduce memory usage
            batch_size = 10  # Process 10 segments at a time
            temp_combined_path = os.path.join(temp_dir, "temp_combined.wav")
            combined = AudioSegment.empty()

            for i in range(0, len(segment_files), batch_size):
                batch = segment_files[i:i+batch_size]

                # Process each segment in the batch
                for j, file_path in enumerate(batch):
                    segment_audio = AudioSegment.from_wav(file_path)
                    combined += segment_audio

                    # Add silence if not the last segment
                    if i + j < len(segment_files) - 1:
                        current_file = os.path.basename(file_path)
                        next_idx = i + j + 1
                        if next_idx < len(segment_files):
                            next_file = os.path.basename(segment_files[next_idx])

                            # Extract indices from filenames
                            current_parts = current_file.replace("segment_", "").split("_")
                            next_parts = next_file.replace("segment_", "").split("_")

                            # If main segment index changes, it's a [break] boundary
                            if len(current_parts) > 1 and len(next_parts) > 1 and current_parts[0] != next_parts[0]:
                                combined += break_silence
                            else:
                                combined += line_silence

                # Export the batch to a temporary file
                if i + batch_size < len(segment_files):
                    combined.export(temp_combined_path, format="wav")
                    # Free memory
                    del combined
                    gc.collect()
                    # Load the temporary file for the next batch
                    combined = AudioSegment.from_wav(temp_combined_path)

            # Export the final combined audio
            combined.export(output_path, format="wav")

            # Clean up
            del combined
            gc.collect()
        else:
            # Fallback if no valid segments were found
            tts.tts_to_file(
                text="No valid text segments found",
                file_path=output_path,
                speaker_wav=voice_path,
                language=language
            )
            # Force garbage collection after fallback TTS generation
            gc.collect()

    return output_filename
