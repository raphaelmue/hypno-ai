"""
Audio generation module.
Handles text-to-speech conversion and audio processing.
"""

import logging
import os
import queue
import tempfile
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from pydub import AudioSegment

from app.config import OUTPUT_FOLDER, AUDIO_GENERATION_THREADS
from app.models.settings import settings
from app.tts_model.tts_model import get_tts_model
from app.utils import slugify


class AudioGenerator:
    """
    Generator for audio from text using multi-threading.
    Handles text segmentation, audio generation, and combining segments.
    """

    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2", 
                num_threads: int = AUDIO_GENERATION_THREADS):
        """
        Initialize the audio generator.
        
        Args:
            model_name: Name of the TTS model to use
            num_threads: Number of threads to use for audio generation
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing AudioGenerator with model {model_name} and {num_threads} threads")
        
        # Store parameters
        self.model_name = model_name
        self.num_threads = num_threads
        
        # Initialize silence segments
        self.heading_silence = None
        self.ellipsis_silence = None
        self.line_silence = None
        self.break_silence = None
        
        # Load pause durations from settings
        self._load_pause_durations()
        
        self.logger.info("AudioGenerator initialized")
    
    def _load_pause_durations(self) -> None:
        """Load pause durations from settings and create silence segments."""
        # Get pause durations from settings
        heading_pause_duration = settings.get('heading_pause_duration', 5)
        ellipsis_pause_duration = settings.get('ellipsis_pause_duration', 2)
        line_break_pause_duration = settings.get('line_break_pause_duration', 2)
        break_pause_duration = settings.get('break_pause_duration', 5)
        
        # Create silence segments
        self.heading_silence = AudioSegment.silent(duration=heading_pause_duration * 1000)
        self.ellipsis_silence = AudioSegment.silent(duration=ellipsis_pause_duration * 1000)
        self.line_silence = AudioSegment.silent(duration=line_break_pause_duration * 1000)
        self.break_silence = AudioSegment.silent(duration=break_pause_duration * 1000)
        
        self.logger.debug(f"Using pause durations: heading={heading_pause_duration}s, "
                         f"ellipsis={ellipsis_pause_duration}s, "
                         f"line break={line_break_pause_duration}s, "
                         f"[break]={break_pause_duration}s")
    
    def _generate_output_filename(self, routine_name: Optional[str]) -> str:
        """
        Generate an output filename based on the routine name or a UUID.
        
        Args:
            routine_name: Name of the routine, or None to use a UUID
            
        Returns:
            str: Generated filename
        """
        if routine_name:
            # Create a slug from the routine name
            slug = slugify(routine_name)
            output_filename = f"{slug}.wav"
            self.logger.info(f"Using routine name '{routine_name}' for output filename: {output_filename}")
        else:
            # Fallback to UUID if no name is provided
            output_filename = f"{uuid.uuid4()}.wav"
            self.logger.info(f"No routine name provided, using UUID for output filename: {output_filename}")
        
        return output_filename
    
    def _process_text_segment(self, text: str, temp_dir: str, language: str, 
                             voice_path: str, segment_info: Tuple[int, int]) -> Tuple[Tuple[int, int], str, int, bool]:
        """
        Process a single text segment to generate audio.
        
        Args:
            text: Text segment to process
            temp_dir: Temporary directory for output files
            language: Language code
            voice_path: Path to the voice sample file
            segment_info: Tuple of (segment_index, segment_type)
            
        Returns:
            Tuple containing:
                - segment_info: Tuple of (segment_index, segment_type)
                - output_file: Path to the generated audio file
                - duration: Duration of the generated audio in milliseconds
                - success: True if processing was successful, False otherwise
        """
        segment_index, segment_type = segment_info
        self.logger.debug(f"Processing segment {segment_index} (type {segment_type}): {text[:50]}...")
        
        # Skip audio generation for empty text segments (used as markers for line breaks, etc.)
        if not text.strip():
            self.logger.debug(f"Skipping empty text segment {segment_index} (type {segment_type})")
            return segment_info, "", 0, True
        
        try:
            # Get the TTS model
            tts = get_tts_model()
            if not tts:
                self.logger.error(f"Failed to get TTS model for segment {segment_index}")
                return segment_info, "", 0, False
            
            # Generate a unique filename for this segment
            output_file = os.path.join(temp_dir, f"segment_{segment_index}_{segment_type}.wav")
            
            # Generate audio for the segment
            start_time = time.time()
            tts.tts_to_file(
                text=text,
                file_path=output_file,
                speaker_wav=voice_path,
                language=language
            )
            
            # Check if the file was created and get its duration
            if os.path.exists(output_file):
                # Load the audio to get its duration
                audio = AudioSegment.from_file(output_file)
                duration = len(audio)
                
                processing_time = time.time() - start_time
                self.logger.debug(f"Processed segment {segment_index} in {processing_time:.2f} seconds, "
                                 f"duration: {duration/1000:.2f} seconds")
                
                return segment_info, output_file, duration, True
            else:
                self.logger.error(f"Output file not created for segment {segment_index}")
                return segment_info, "", 0, False
                
        except Exception as e:
            self.logger.error(f"Error processing segment {segment_index}: {str(e)}", exc_info=True)
            return segment_info, "", 0, False
    
    def _worker(self, work_queue: queue.Queue, result_queue: queue.Queue, 
               temp_dir: str, language: str, voice_path: str) -> None:
        """
        Worker function for processing text segments in a thread.
        
        Args:
            work_queue: Queue containing text segments to process
            result_queue: Queue to store processing results
            temp_dir: Temporary directory for output files
            language: Language code
            voice_path: Path to the voice sample file
        """
        self.logger.debug(f"Worker thread started")
        
        while not work_queue.empty():
            try:
                # Get a segment from the work queue
                segment_text, segment_info = work_queue.get()
                
                # Process the segment
                result = self._process_text_segment(segment_text, temp_dir, language, voice_path, segment_info)
                
                # Put the result in the result queue
                result_queue.put(result)
                
                # Mark the task as done
                work_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in worker thread: {str(e)}", exc_info=True)
                # Mark the task as done even if it failed
                work_queue.task_done()
        
        self.logger.debug(f"Worker thread exiting")
    
    def _prepare_segments(self, text: str) -> List[Tuple[str, Tuple[int, int]]]:
        """
        Prepare text segments for processing.
        
        Args:
            text: Text to segment
            
        Returns:
            List of tuples containing (segment_text, segment_info)
        """
        self.logger.info(f"Preparing segments for text of length {len(text)}")
        
        # Split the text into segments
        segments = []
        segment_index = 0
        
        # Split by [break] markers first
        break_parts = text.split("[break]")
        
        for i, part in enumerate(break_parts):
            # Skip empty parts
            if not part.strip():
                continue
            
            # Split by line breaks
            lines = part.split("\n")
            
            for j, line in enumerate(lines):
                # Skip empty lines
                if not line.strip():
                    continue
                
                # Check if the line is a heading (starts with ###)
                if line.strip().startswith("###"):
                    segments.append((line.strip(), (segment_index, 1)))  # Type 1 = heading
                    segment_index += 1
                # Check if the line contains ellipsis (...)
                elif "..." in line:
                    # Split by ellipsis
                    ellipsis_parts = line.split("...")
                    
                    for k, ellipsis_part in enumerate(ellipsis_parts):
                        # Skip empty parts
                        if not ellipsis_part.strip():
                            continue
                        
                        segments.append((ellipsis_part.strip(), (segment_index, 3)))  # Type 3 = ellipsis part
                        segment_index += 1
                        
                        # Add a marker for ellipsis pause if not the last part
                        if k < len(ellipsis_parts) - 1:
                            segments.append(("", (segment_index, 4)))  # Type 4 = ellipsis pause
                            segment_index += 1
                else:
                    segments.append((line.strip(), (segment_index, 0)))  # Type 0 = normal text
                    segment_index += 1
                
                # Add a marker for line break if not the last line
                if j < len(lines) - 1:
                    segments.append(("", (segment_index, 2)))  # Type 2 = line break
                    segment_index += 1
            
            # Add a marker for [break] if not the last part
            if i < len(break_parts) - 1:
                segments.append(("", (segment_index, 5)))  # Type 5 = [break]
                segment_index += 1
        
        # Filter out empty segments
        segments = [(text, info) for text, info in segments if text.strip() or info[1] in (2, 4, 5)]
        
        self.logger.info(f"Prepared {len(segments)} segments for processing")
        return segments
    
    def _combine_audio_segments(self, segment_files: List[Tuple[Tuple[int, int], str, int, bool]], 
                               output_path: str) -> bool:
        """
        Combine processed audio segments into a single audio file.
        
        Args:
            segment_files: List of tuples containing (segment_info, output_file, duration, success)
            output_path: Path to the output audio file
            
        Returns:
            bool: True if combining was successful, False otherwise
        """
        self.logger.info(f"Combining {len(segment_files)} audio segments")
        
        # Sort segments by index
        segment_files.sort(key=lambda x: x[0][0])
        
        # Filter out failed segments
        valid_segments = [s for s in segment_files if s[3]]
        
        if valid_segments:
            start_time = time.time()
            
            # Initialize counters for different types of pauses
            break_count = 0
            line_break_count = 0
            heading_count = 0
            ellipsis_count = 0
            
            # Start with an empty audio segment
            combined = AudioSegment.empty()
            
            # Process each segment
            for segment_info, output_file, duration, success in valid_segments:
                segment_index, segment_type = segment_info
                
                if segment_type == 0:  # Normal text
                    # Add the audio segment
                    segment_audio = AudioSegment.from_file(output_file)
                    combined += segment_audio
                    self.logger.debug(f"Added normal text segment {segment_index}, duration: {duration/1000:.2f}s")
                    
                elif segment_type == 1:  # Heading
                    # Add the audio segment
                    segment_audio = AudioSegment.from_file(output_file)
                    combined += segment_audio
                    # Add a pause after the heading
                    combined += self.heading_silence
                    heading_count += 1
                    self.logger.debug(f"Added heading segment {segment_index}, duration: {duration/1000:.2f}s + {len(self.heading_silence)/1000:.2f}s pause")
                    
                elif segment_type == 2:  # Line break
                    # Add a pause for the line break
                    combined += self.line_silence
                    line_break_count += 1
                    self.logger.debug(f"Added line break pause, duration: {len(self.line_silence)/1000:.2f}s")
                    
                elif segment_type == 3:  # Ellipsis part
                    # Add the audio segment
                    segment_audio = AudioSegment.from_file(output_file)
                    combined += segment_audio
                    self.logger.debug(f"Added ellipsis part segment {segment_index}, duration: {duration/1000:.2f}s")
                    
                elif segment_type == 4:  # Ellipsis pause
                    # Add a pause for the ellipsis
                    combined += self.ellipsis_silence
                    ellipsis_count += 1
                    self.logger.debug(f"Added ellipsis pause, duration: {len(self.ellipsis_silence)/1000:.2f}s")
                    
                elif segment_type == 5:  # [break]
                    # Add a pause for the [break]
                    combined += self.break_silence
                    break_count += 1
                    self.logger.debug(f"Added [break] pause, duration: {len(self.break_silence)/1000:.2f}s")
            
            # Export the combined audio
            combined.export(output_path, format="wav")
            
            processing_time = time.time() - start_time
            self.logger.info(f"Combined audio segments in {processing_time:.2f} seconds with "
                            f"{break_count} breaks, {line_break_count} line breaks, "
                            f"{heading_count} headings, and {ellipsis_count} ellipses")
            
            return True
        else:
            self.logger.warning("No valid audio segments to combine")
            return False
    
    def _setup_worker_threads(self, work_queue: queue.Queue, result_queue: queue.Queue, 
                             temp_dir: str, language: str, voice_path: str, 
                             num_segments: int) -> List[threading.Thread]:
        """
        Set up and start worker threads for processing text segments.
        
        Args:
            work_queue: Queue containing text segments to process
            result_queue: Queue to store processing results
            temp_dir: Temporary directory for output files
            language: Language code
            voice_path: Path to the voice sample file
            num_segments: Number of segments to process
            
        Returns:
            List of started worker threads
        """
        # Create and start worker threads
        thread_count = min(self.num_threads, num_segments)
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
        
        return threads
    
    def _monitor_progress(self, result_queue: queue.Queue, total_segments: int, 
                         progress_callback: Optional[Callable[[int, str], None]] = None) -> List[Tuple[Tuple[int, int], str, int, bool]]:
        """
        Monitor progress of segment processing and collect results.
        
        Args:
            result_queue: Queue containing processing results
            total_segments: Total number of segments to process
            progress_callback: Callback function for progress updates
            
        Returns:
            List of tuples containing (segment_info, output_file, duration, success)
        """
        self.logger.debug("Monitoring progress of segment processing")
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
            
            # Small sleep to prevent CPU spinning
            time.sleep(0.1)
            
            # Check if all work is done
            if processed_segments >= total_segments:
                self.logger.info(f"All {total_segments} segments have been processed. Breaking loop.")
                break
        
        # Make sure we've collected all results
        while not result_queue.empty():
            segment_files.append(result_queue.get())
        
        self.logger.info(f"Collected {len(segment_files)} processed segments from result queue")
        return segment_files
    
    def generate(self, text: str, language: str, voice_path: str, 
                routine_name: Optional[str] = None, 
                progress_callback: Optional[Callable[[int, str], None]] = None) -> str:
        """
        Generate audio from text using multi-threading.
        
        Args:
            text: The text to convert to audio
            language: Language code
            voice_path: Path to the voice sample file
            routine_name: Name of the routine
            progress_callback: Callback function for progress updates
            
        Returns:
            str: Filename of the generated audio
        """
        start_time = time.time()
        self.logger.info(f"Starting audio generation for text of length {len(text)} in language {language}")
        
        # Reload pause durations from settings to ensure we have the latest values
        self._load_pause_durations()
        
        # Generate an output filename
        output_filename = self._generate_output_filename(routine_name)
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
                
                # Set up and start worker threads
                threads = self._setup_worker_threads(
                    work_queue, result_queue, temp_dir, language, voice_path, len(segments)
                )
                
                # Monitor progress and collect results
                segment_files = self._monitor_progress(result_queue, len(segments), progress_callback)
                
                # Ensure all tasks are marked as done
                work_queue.join()
                self.logger.info("All worker threads have completed their tasks")
                
                # Combine audio segments
                success = self._combine_audio_segments(segment_files, output_path)
                
                if not success:
                    # Fallback if no valid segments were found
                    self._generate_fallback_audio(output_path, language, voice_path)
            
            total_time = time.time() - start_time
            self.logger.info(f"Audio generation completed in {total_time:.2f} seconds: {output_filename}")
            return output_filename
            
        except Exception as e:
            self.logger.error(f"Error during audio generation: {str(e)}", exc_info=True)
            raise
    
    def _generate_fallback_audio(self, output_path: str, language: str, voice_path: str) -> None:
        """
        Generate a fallback audio message when no valid segments are found.
        
        Args:
            output_path: Path to the output audio file
            language: Language code
            voice_path: Path to the voice sample file
        """
        self.logger.warning("No valid segments were found, generating fallback audio")
        tts = get_tts_model()
        tts.tts_to_file(
            text="No valid text segments found",
            file_path=output_path,
            speaker_wav=voice_path,
            language=language
        )
        self.logger.info("Generated fallback audio message")


def generate_audio(text: str, language: str, voice_path: str, 
                  routine_name: Optional[str] = None, 
                  num_threads: int = AUDIO_GENERATION_THREADS,
                  progress_callback: Optional[Callable[[int, str], Union[None, bool]]] = None) -> str:
    """
    Generate audio using XTTS-v2 with support for [break] markers and line breaks.
    
    Args:
        text: Text to convert to audio
        language: Language code
        voice_path: Path to the voice sample file
        routine_name: Name of the routine
        num_threads: Number of threads to use for audio generation
        progress_callback: Callback function for progress updates
        
    Returns:
        str: Filename of the generated audio
    """
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