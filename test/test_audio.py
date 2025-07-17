import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from app.audio.audio import AudioGenerator, generate_audio
from app.config import AUDIO_GENERATION_THREADS

# Mock for AudioSegment
class MockAudioSegment:
    @staticmethod
    def empty():
        return MockAudioSegment()
    
    @staticmethod
    def silent(duration=1000):
        segment = MockAudioSegment()
        segment.duration = duration
        return segment
    
    @staticmethod
    def from_file(file_path):
        segment = MockAudioSegment()
        segment.file_path = file_path
        segment.duration = 1000  # 1 second
        return segment
    
    def __init__(self):
        self.duration = 0
        self.file_path = None
    
    def __add__(self, other):
        result = MockAudioSegment()
        result.duration = self.duration + other.duration
        return result
    
    def __len__(self):
        return self.duration
    
    def export(self, output_path, format="wav"):
        # Simulate exporting by creating an empty file
        with open(output_path, 'w') as f:
            f.write("Mock audio content")
        return output_path

# Mock for TTS model
class MockTTSModel:
    def __init__(self):
        pass
    
    def to(self, device):
        return self
    
    def tts_to_file(self, text, file_path, speaker_wav, language):
        # Simulate TTS by creating an empty file
        with open(file_path, 'w') as f:
            f.write(f"Mock TTS output for: {text}")
        return file_path

@pytest.fixture
def mock_tts_model():
    with patch('app.audio.audio.get_tts_model') as mock_get_tts:
        mock_get_tts.return_value = MockTTSModel()
        yield mock_get_tts

@pytest.fixture
def mock_audio_segment():
    with patch('app.audio.audio.AudioSegment', MockAudioSegment):
        yield

@pytest.fixture
def temp_output_folder():
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.audio.audio.OUTPUT_FOLDER', temp_dir):
            yield temp_dir

@pytest.fixture
def sample_voice_path():
    # Create a temporary file to use as a voice sample
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
        temp_file.write(b"Mock voice sample")
        temp_file_path = temp_file.name
    
    yield temp_file_path
    
    # Clean up
    if os.path.exists(temp_file_path):
        os.unlink(temp_file_path)

class TestAudioGenerator:
    def test_init(self):
        """Test AudioGenerator initialization"""
        generator = AudioGenerator()
        assert generator.num_threads == AUDIO_GENERATION_THREADS
        assert generator.model_name == "tts_models/multilingual/multi-dataset/xtts_v2"
    
    def test_load_pause_durations(self, mock_audio_segment):
        """Test loading pause durations from settings"""
        generator = AudioGenerator()
        generator._load_pause_durations()
        
        assert generator.heading_silence is not None
        assert generator.ellipsis_silence is not None
        assert generator.line_silence is not None
        assert generator.break_silence is not None
    
    def test_generate_output_filename(self):
        """Test generating output filename"""
        generator = AudioGenerator()
        
        # Test with routine name
        filename = generator._generate_output_filename("Test Routine")
        assert filename.endswith(".wav")
        assert "test-routine" in filename.lower()
        
        # Test without routine name (should use UUID)
        filename = generator._generate_output_filename(None)
        assert filename.endswith(".wav")
        assert len(filename) > 30  # UUID is long
    
    @patch('app.audio.audio.queue.Queue')
    def test_prepare_segments(self, mock_queue):
        """Test preparing text segments"""
        generator = AudioGenerator()
        
        # Test with simple text
        text = "This is a test."
        segments = generator._prepare_segments(text)
        assert len(segments) == 1
        assert segments[0][0] == "This is a test."
        assert segments[0][1][1] == 0  # Type 0 = normal text
        
        # Test with line breaks
        text = "Line 1\nLine 2"
        segments = generator._prepare_segments(text)
        assert len(segments) == 3  # Line 1, line break, Line 2
        assert segments[0][0] == "Line 1"
        assert segments[1][1][1] == 2  # Type 2 = line break
        assert segments[2][0] == "Line 2"
        
        # Test with [break]
        text = "Before break[break]After break"
        segments = generator._prepare_segments(text)
        assert len(segments) == 3  # Before break, [break], After break
        assert segments[0][0] == "Before break"
        assert segments[1][1][1] == 5  # Type 5 = [break]
        assert segments[2][0] == "After break"
        
        # Test with heading
        text = "### Heading\nContent"
        segments = generator._prepare_segments(text)
        assert len(segments) == 3  # Heading, line break, Content
        assert segments[0][0] == "### Heading"
        assert segments[0][1][1] == 1  # Type 1 = heading
        assert segments[1][1][1] == 2  # Type 2 = line break
        assert segments[2][0] == "Content"
        
        # Test with ellipsis
        text = "Before...After"
        segments = generator._prepare_segments(text)
        assert len(segments) == 3  # Before, ellipsis pause, After
        assert segments[0][0] == "Before"
        assert segments[1][1][1] == 4  # Type 4 = ellipsis pause
        assert segments[2][0] == "After"

    @patch('app.audio.audio.tempfile.TemporaryDirectory')
    def test_generate(self, mock_temp_dir, mock_tts_model, mock_audio_segment, temp_output_folder, sample_voice_path):
        """Test the generate method"""
        # Set up the mock temporary directory
        mock_temp_dir.return_value.__enter__.return_value = os.path.join(temp_output_folder, "temp")
        os.makedirs(os.path.join(temp_output_folder, "temp"), exist_ok=True)
        
        # Create a progress callback mock
        progress_callback = MagicMock()
        
        # Create the generator
        generator = AudioGenerator(num_threads=1)  # Use 1 thread for simplicity
        
        # Call the generate method
        text = "This is a test script.\n[break]\nSecond paragraph."
        language = "en"
        routine_name = "Test Routine"
        
        output_filename = generator.generate(
            text=text,
            language=language,
            voice_path=sample_voice_path,
            routine_name=routine_name,
            progress_callback=progress_callback
        )
        
        # Verify the result
        assert output_filename is not None
        assert output_filename.endswith(".wav")
        assert os.path.exists(os.path.join(temp_output_folder, output_filename))
        
        # Verify the progress callback was called
        assert progress_callback.call_count > 0

def test_generate_audio_function(mock_tts_model, mock_audio_segment, temp_output_folder, sample_voice_path):
    """Test the generate_audio function"""
    # Create a progress callback mock
    progress_callback = MagicMock()
    
    # Call the generate_audio function
    text = "This is a test script."
    language = "en"
    routine_name = "Test Function"
    
    output_filename = generate_audio(
        text=text,
        language=language,
        voice_path=sample_voice_path,
        routine_name=routine_name,
        num_threads=1,  # Use 1 thread for simplicity
        progress_callback=progress_callback
    )
    
    # Verify the result
    assert output_filename is not None
    assert output_filename.endswith(".wav")
    assert os.path.exists(os.path.join(temp_output_folder, output_filename))
    
    # Verify the progress callback was called
    assert progress_callback.call_count > 0

def test_generate_audio_error_handling(mock_tts_model, mock_audio_segment, temp_output_folder, sample_voice_path):
    """Test error handling in the generate_audio function"""
    # Create a mock that raises an exception
    with patch('app.audio.audio.AudioGenerator.generate', side_effect=Exception("Test error")):
        # Call the generate_audio function
        with pytest.raises(Exception) as excinfo:
            generate_audio(
                text="This is a test script.",
                language="en",
                voice_path=sample_voice_path,
                routine_name="Test Error"
            )
        
        # Verify the exception
        assert "Test error" in str(excinfo.value)