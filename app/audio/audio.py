import logging
import os
import queue
import tempfile
import threading
import time
import uuid

from pydub import AudioSegment

from app.config import OUTPUT_FOLDER, AUDIO_GENERATION_THREADS
from app.models.settings import settings
from app.tts_model.tts_model import get_tts_model
from app.utils import slugify


class AudioGenerator:
    """
    A class for generating audio from text using XTTS-v2 with support for multi-threading.
    Processes text in small chunks to avoid memory issues and concatenates at the end.
    """

    def __init__(self, model_name="tts_models/multilingual/multi-dataset/xtts_v2", num_threads=AUDIO_GENERATION_THREADS):
        """
        Initialize the AudioGenerator with the specified TTS model and number of threads.

        Args:
            model_name (str): The name of the TTS model to use
            num_threads (int): Number of threads to use for parallel processing
        """
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing AudioGenerator with model={model_name}, threads={num_threads}")

        self.model_name = model_name
        self.num_threads = max(1, num_threads)  # Ensure at least 1 thread

        # Get pause durations from settings
        heading_pause_duration = settings.get('heading_pause_duration', 5)  # Default to 5 seconds
        ellipsis_pause_duration = settings.get('ellipsis_pause_duration', 2)  # Default to 2 seconds
        line_break_pause_duration = settings.get('line_break_pause_duration', 2)  # Default to 2 seconds
        break_pause_duration = settings.get('break_pause_duration', 5)  # Default to 5 seconds

        # Create silence segments
        self.break_silence = AudioSegment.silent(duration=break_pause_duration * 1000)  # Silence for [break] tags
        self.line_silence = AudioSegment.silent(duration=line_break_pause_duration * 1000)  # Silence for line breaks
        self.heading_silence = AudioSegment.silent(duration=heading_pause_duration * 1000)  # Silence for ### headings
        self.ellipsis_silence = AudioSegment.silent(duration=ellipsis_pause_duration * 1000)  # Silence for ... ellipses

    def _process_text_segment(self, text, temp_dir, language, voice_path, segment_info):
        """
        Process a single text segment and generate audio for it.

        Args:
            text (str): The text to convert to audio
            temp_dir (str): Directory to store temporary files
            language (str): Language code
            voice_path (str): Path to the voice sample file
            segment_info (tuple): Information about the segment (main_idx, line_idx)

        Returns:
            str: Path to the generated audio file
        """
        main_idx, line_idx = segment_info
        start_time = time.time()

        # Log the truncated version for brevity
        self.logger.debug(f"Processing segment {main_idx}_{line_idx}: '{text[:50]}...' if len(text) > 50 else text")
        # Log the full segment text as requested
        self.logger.debug(f"Full segment {main_idx}_{line_idx} content: '{text}'")

        # Skip empty lines
        text = text.strip()
        if not text:
            self.logger.debug(f"Skipping empty segment {main_idx}_{line_idx}")
            return None

        # Mark section headers and ellipses for special handling
        is_heading = False
        has_ellipsis = False

        if text.startswith("###"):
            self.logger.debug(f"Processing section header segment {main_idx}_{line_idx}")
            is_heading = True
            # Remove the ### prefix for TTS processing
            text = text[3:].strip()

        # Check for ellipsis in the text
        if "..." in text:
            self.logger.debug(f"Segment {main_idx}_{line_idx} contains ellipsis")
            has_ellipsis = True
            # Replace ellipsis with a space for better TTS processing
            text = text.replace("...", " ")

        # Generate a unique filename for this segment
        segment_path = os.path.join(temp_dir, f"segment_{main_idx}_{line_idx}.wav")

        try:
            # Initialize TTS (each thread needs its own instance)
            tts = get_tts_model()

            # Generate audio for this segment
            self.logger.debug(f"Generating audio for segment {main_idx}_{line_idx}")
            tts.tts_to_file(
                text=text,
                file_path=segment_path,
                speaker_wav=voice_path,
                language=language
            )

            processing_time = time.time() - start_time
            self.logger.info(f"Generated audio for segment {main_idx}_{line_idx} in {processing_time:.2f} seconds")

            # Return the segment path along with flags for special handling
            return segment_path, is_heading, has_ellipsis
        except Exception as e:
            self.logger.error(f"Error processing segment {main_idx}_{line_idx}: {str(e)}")
            raise

    def _worker(self, work_queue, result_queue, temp_dir, language, voice_path):
        """
        Worker function for processing text segments in parallel.

        Args:
            work_queue (Queue): Queue containing text segments to process
            result_queue (Queue): Queue to store results
            temp_dir (str): Directory to store temporary files
            language (str): Language code
            voice_path (str): Path to the voice sample file
        """
        thread_id = threading.get_ident()
        self.logger.info(f"Worker thread {thread_id} started")
        segments_processed = 0

        while True:
            try:
                # Get the next item from the queue
                text, segment_info = work_queue.get(block=False)
                main_idx, line_idx = segment_info

                self.logger.debug(f"Worker {thread_id} processing segment {main_idx}_{line_idx}")

                # Process the segment
                result = self._process_text_segment(text, temp_dir, language, voice_path, segment_info)

                # Add the result to the result queue if valid
                if result:
                    segment_path, is_heading, has_ellipsis = result
                    result_queue.put((segment_info, segment_path, is_heading, has_ellipsis))
                    segments_processed += 1
                    self.logger.debug(f"Worker {thread_id} completed segment {main_idx}_{line_idx}")

                # Mark the task as done
                work_queue.task_done()
            except queue.Empty:
                # No more work to do
                self.logger.info(f"Worker thread {thread_id} finished after processing {segments_processed} segments")
                break
            except Exception as e:
                # Log the error and continue
                self.logger.error(f"Worker {thread_id} error processing segment: {str(e)}", exc_info=True)
                work_queue.task_done()

    def _prepare_segments(self, text):
        """
        Prepare text segments for processing.

        Args:
            text (str): The input text

        Returns:
            list: List of (text, segment_info) tuples
        """
        self.logger.info(f"Preparing text segments from {len(text)} characters of text")
        segments = []

        # Check if text contains [break] markers
        if "[break]" in text:
            # Split text by [break] markers
            main_segments = text.split("[break]")
            self.logger.debug(f"Text contains {len(main_segments)} main segments separated by [break] markers")

            # Process each main segment (separated by [break])
            for main_idx, main_segment in enumerate(main_segments):
                main_segment = main_segment.strip()
                if not main_segment:  # Skip empty segments
                    self.logger.debug(f"Skipping empty main segment at index {main_idx}")
                    continue

                # Split each main segment by line breaks
                lines = main_segment.split('\n')
                self.logger.debug(f"Main segment {main_idx} contains {len(lines)} lines")

                # Add each line as a segment
                for line_idx, line in enumerate(lines):
                    segments.append((line, (main_idx, line_idx)))
        else:
            # No [break] markers, but still process line breaks
            lines = text.split('\n')
            self.logger.debug(f"Text contains {len(lines)} lines (no [break] markers)")

            # Add each line as a segment
            for i, line in enumerate(lines):
                segments.append((line, (0, i)))

        self.logger.info(f"Prepared {len(segments)} text segments for processing")
        return segments

    def _combine_audio_segments(self, segment_files, output_path):
        """
        Combine audio segments with appropriate silences.

        Args:
            segment_files (list): List of (segment_info, file_path, is_heading, has_ellipsis) tuples
            output_path (str): Path to save the combined audio
        """
        start_time = time.time()
        self.logger.info(f"Combining {len(segment_files)} audio segments into {output_path}")

        # Sort segments by main_idx and line_idx
        segment_files.sort(key=lambda x: (x[0][0], x[0][1]))
        self.logger.debug("Sorted segments by main_idx and line_idx")

        # Extract the file paths and flags in the correct order
        processed_segments = [(file_path, is_heading, has_ellipsis) 
                             for _, file_path, is_heading, has_ellipsis in segment_files]

        if processed_segments:
            combined = AudioSegment.empty()
            total_duration = 0
            break_count = 0
            line_break_count = 0
            heading_count = 0
            ellipsis_count = 0

            for i, (file_path, is_heading, has_ellipsis) in enumerate(processed_segments):
                try:
                    segment_audio = AudioSegment.from_wav(file_path)

                    # If this is a heading, add heading silence before the segment
                    if is_heading:
                        combined += self.heading_silence
                        total_duration += len(self.heading_silence)
                        heading_count += 1
                        self.logger.debug(f"Added heading silence before segment {segment_files[i][0][0]}_{segment_files[i][0][1]}")

                    # Add the segment audio
                    combined += segment_audio
                    total_duration += len(segment_audio)

                    # If this segment has ellipsis, add ellipsis silence after it
                    if has_ellipsis:
                        combined += self.ellipsis_silence
                        total_duration += len(self.ellipsis_silence)
                        ellipsis_count += 1
                        self.logger.debug(f"Added ellipsis silence after segment {segment_files[i][0][0]}_{segment_files[i][0][1]}")

                    if i < len(processed_segments) - 1:
                        # Determine if this is a [break] boundary or just a line break
                        current_info = segment_files[i][0]
                        next_info = segment_files[i+1][0]

                        # If main segment index changes, it's a [break] boundary
                        if current_info[0] != next_info[0]:
                            combined += self.break_silence
                            total_duration += len(self.break_silence)
                            break_count += 1
                            self.logger.debug(f"Added [break] silence after segment {current_info[0]}_{current_info[1]}")
                        else:
                            combined += self.line_silence
                            total_duration += len(self.line_silence)
                            line_break_count += 1
                            self.logger.debug(f"Added line break silence after segment {current_info[0]}_{current_info[1]}")
                except Exception as e:
                    self.logger.error(f"Error processing audio file {file_path}: {str(e)}")
                    # Continue with the next file

            # Export the combined audio
            self.logger.info(f"Exporting combined audio ({total_duration/1000:.2f} seconds) to {output_path}")
            combined.export(output_path, format="wav")

            processing_time = time.time() - start_time
            self.logger.info(f"Combined audio segments in {processing_time:.2f} seconds with {break_count} breaks, {line_break_count} line breaks, {heading_count} headings, and {ellipsis_count} ellipses")

            return True
        else:
            self.logger.warning("No valid audio segments to combine")
            return False

    def generate(self, text, language, voice_path, routine_name=None, progress_callback=None):
        """
        Generate audio from text using multi-threading.

        Args:
            text (str): The text to convert to audio
            language (str): Language code
            voice_path (str): Path to the voice sample file
            routine_name (str, optional): Name of the routine
            progress_callback (callable, optional): Callback function for progress updates

        Returns:
            str: Filename of the generated audio
        """
        start_time = time.time()
        self.logger.info(f"Starting audio generation for text of length {len(text)} in language {language}")

        # Reload pause durations from settings to ensure we have the latest values
        heading_pause_duration = settings.get('heading_pause_duration', 5)
        ellipsis_pause_duration = settings.get('ellipsis_pause_duration', 2)
        line_break_pause_duration = settings.get('line_break_pause_duration', 2)
        break_pause_duration = settings.get('break_pause_duration', 5)

        self.heading_silence = AudioSegment.silent(duration=heading_pause_duration * 1000)
        self.ellipsis_silence = AudioSegment.silent(duration=ellipsis_pause_duration * 1000)
        self.line_silence = AudioSegment.silent(duration=line_break_pause_duration * 1000)
        self.break_silence = AudioSegment.silent(duration=break_pause_duration * 1000)

        self.logger.debug(f"Using pause durations: heading={heading_pause_duration}s, ellipsis={ellipsis_pause_duration}s, line break={line_break_pause_duration}s, [break]={break_pause_duration}s")

        # Generate a filename based on the routine name or a UUID if no name is provided
        if routine_name:
            # Create a slug from the routine name
            slug = slugify(routine_name)
            output_filename = f"{slug}.wav"
            self.logger.info(f"Using routine name '{routine_name}' for output filename: {output_filename}")
        else:
            # Fallback to UUID if no name is provided
            output_filename = f"{uuid.uuid4()}.wav"
            self.logger.info(f"No routine name provided, using UUID for output filename: {output_filename}")

        output_path = os.path.join(OUTPUT_FOLDER, output_filename)

        try:
            # Create a temporary directory for segment audio files
            with tempfile.TemporaryDirectory() as temp_dir:
                self.logger.debug(f"Created temporary directory for audio segments: {temp_dir}")

                # Prepare segments for processing
                segments = self._prepare_segments(text)

                # Create queues for work and results
                work_queue = queue.Queue()
                result_queue = queue.Queue()

                # Add segments to the work queue
                for segment in segments:
                    work_queue.put(segment)
                self.logger.info(f"Added {len(segments)} segments to the work queue")

                # Create and start worker threads
                thread_count = min(self.num_threads, len(segments))
                threads = []
                self.logger.info(f"Starting {thread_count} worker threads")

                for i in range(thread_count):
                    thread = threading.Thread(
                        target=self._worker,
                        args=(work_queue, result_queue, temp_dir, language, voice_path)
                    )
                    thread.daemon = True
                    thread.start()
                    threads.append(thread)
                    self.logger.debug(f"Started worker thread {i+1}/{thread_count}")

                # Wait for all tasks to be processed and track progress
                self.logger.debug("Waiting for all tasks to be processed")
                total_segments = len(segments)
                processed_segments = 0
                segment_files = []

                # Monitor the result queue for progress updates
                while processed_segments < total_segments:
                    # Check if any new results are available
                    if not result_queue.empty():
                        # Get the result and increment the counter
                        segment_files.append(result_queue.get())
                        processed_segments += 1

                        # Report progress if callback is provided
                        if progress_callback:
                            progress_percent = int(processed_segments / total_segments * 100)
                            progress_callback(progress_percent, f"Processing segments: {processed_segments} / {total_segments}")
                            self.logger.debug(f"Progress update: {processed_segments}/{total_segments} segments processed")

                    # Check if all threads have exited but we haven't processed all segments
                    all_threads_exited = all(not thread.is_alive() for thread in threads)
                    if all_threads_exited and processed_segments < total_segments:
                        if work_queue.empty():
                            # If the work queue is empty but we haven't processed all segments,
                            # there might be segments that were never added to the queue or were lost
                            self.logger.warning(f"All worker threads exited, work queue empty, but only {processed_segments}/{total_segments} segments processed.")

                            # Check which segments haven't been processed
                            processed_segment_infos = set(info for info, _, _, _ in segment_files)
                            all_segment_infos = set(info for _, info in segments)
                            missing_segment_infos = all_segment_infos - processed_segment_infos

                            if missing_segment_infos:
                                self.logger.warning(f"Found {len(missing_segment_infos)} missing segments. Re-adding to work queue.")
                                for segment_text, segment_info in segments:
                                    if segment_info in missing_segment_infos:
                                        work_queue.put((segment_text, segment_info))
                                        self.logger.debug(f"Re-added segment {segment_info[0]}_{segment_info[1]} to work queue")

                        # Start a new worker thread
                        self.logger.warning(f"Starting new worker thread to process remaining segments.")
                        thread = threading.Thread(
                            target=self._worker,
                            args=(work_queue, result_queue, temp_dir, language, voice_path)
                        )
                        thread.daemon = True
                        thread.start()
                        threads.append(thread)

                    # Small sleep to prevent CPU spinning
                    time.sleep(0.1)

                    # Check if all work is done
                    if processed_segments >= total_segments:
                        self.logger.info(f"All {total_segments} segments have been processed. Breaking loop.")
                        break

                    # If all threads have exited and the work queue is empty, but we haven't processed all segments,
                    # it means we've lost some segments and couldn't recover them
                    if all_threads_exited and work_queue.empty() and processed_segments < total_segments:
                        self.logger.warning(f"All threads exited, work queue empty, but only {processed_segments}/{total_segments} segments processed. Unable to recover missing segments.")
                        break

                # Ensure all tasks are marked as done
                work_queue.join()
                self.logger.info("All worker threads have completed their tasks")

                # Make sure we've collected all results
                while not result_queue.empty():
                    segment_files.append(result_queue.get())

                self.logger.info(f"Collected {len(segment_files)} processed segments from result queue")

                # Combine audio segments
                success = self._combine_audio_segments(segment_files, output_path)

                if not success:
                    # Fallback if no valid segments were found
                    self.logger.warning("No valid segments were found, generating fallback audio")
                    tts = get_tts_model()
                    tts.tts_to_file(
                        text="No valid text segments found",
                        file_path=output_path,
                        speaker_wav=voice_path,
                        language=language
                    )
                    self.logger.info("Generated fallback audio message")

            total_time = time.time() - start_time
            self.logger.info(f"Audio generation completed in {total_time:.2f} seconds: {output_filename}")
            return output_filename

        except Exception as e:
            self.logger.error(f"Error during audio generation: {str(e)}", exc_info=True)
            raise


def generate_audio(text, language, voice_path, routine_name=None, num_threads=AUDIO_GENERATION_THREADS, progress_callback=None):
    """Generate audio using XTTS-v2 with support for [break] markers and line breaks"""
    logger = logging.getLogger(__name__)
    logger.info(f"generate_audio called with language={language}, routine_name={routine_name}, num_threads={num_threads}")

    try:
        generator = AudioGenerator(num_threads=num_threads)
        result = generator.generate(text, language, voice_path, routine_name, progress_callback)
        logger.info(f"generate_audio completed successfully, generated file: {result}")
        return result
    except Exception as e:
        logger.error(f"generate_audio failed: {str(e)}", exc_info=True)
        raise
