import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from app.tts_model.tts_model import (
    get_model_dir, is_model_downloaded, get_model_status,
    download_model_task, start_model_download, get_tts_model,
    MODEL_NAME
)

# Mock for TTS class
class MockTTS:
    def __init__(self, model_name=None):
        self.model_name = model_name
    
    def to(self, device):
        return self

# Mock for torch.cuda
class MockCuda:
    @staticmethod
    def is_available():
        return False

@pytest.fixture
def mock_tts():
    with patch('app.tts_model.tts_model.TTS', MockTTS):
        yield

@pytest.fixture
def mock_torch():
    with patch('app.tts_model.tts_model.torch') as mock_torch:
        mock_torch.cuda = MockCuda
        yield mock_torch

@pytest.fixture
def temp_model_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch('app.tts_model.tts_model.settings.get_data_dir', return_value=temp_dir):
            # Create the model directory structure
            model_dir = os.path.join(temp_dir, "tts_model")
            os.makedirs(model_dir, exist_ok=True)
            
            # Create the model subdirectory
            model_subdir = os.path.join(model_dir, "tts", MODEL_NAME.replace("/", "--"))
            os.makedirs(model_subdir, exist_ok=True)
            
            yield model_dir, model_subdir

def test_get_model_dir(temp_model_dir):
    """Test get_model_dir function"""
    model_dir, _ = temp_model_dir
    
    # Call the function
    result = get_model_dir()
    
    # Verify the result
    assert result == model_dir
    assert os.environ["TTS_HOME"] == model_dir

def test_is_model_downloaded_not_downloaded(temp_model_dir):
    """Test is_model_downloaded function when model is not downloaded"""
    # Call the function
    result = is_model_downloaded()
    
    # Verify the result
    assert result is False

def test_is_model_downloaded_downloaded(temp_model_dir):
    """Test is_model_downloaded function when model is downloaded"""
    _, model_subdir = temp_model_dir
    
    # Create the required files
    required_files = ["model.pth", "config.json", "vocab.json", "speakers_xtts.pth"]
    for file in required_files:
        with open(os.path.join(model_subdir, file), 'w') as f:
            f.write("Mock model file")
    
    # Call the function
    result = is_model_downloaded()
    
    # Verify the result
    assert result is True

def test_get_model_status_not_downloaded():
    """Test get_model_status function when model is not downloaded"""
    with patch('app.tts_model.tts_model.is_model_downloaded', return_value=False):
        with patch('app.tts_model.tts_model.model_status', {'status': 'not_downloaded', 'error': None}):
            # Call the function
            result = get_model_status()
            
            # Verify the result
            assert result['status'] == 'not_downloaded'
            assert result['error'] is None

def test_get_model_status_downloaded():
    """Test get_model_status function when model is downloaded"""
    with patch('app.tts_model.tts_model.is_model_downloaded', return_value=True):
        with patch('app.tts_model.tts_model.model_status', {'status': 'not_downloaded', 'error': None}):
            # Call the function
            result = get_model_status()
            
            # Verify the result
            assert result['status'] == 'downloaded'
            assert result['error'] is None

def test_download_model_task(mock_tts, temp_model_dir):
    """Test download_model_task function"""
    with patch('app.tts_model.tts_model.model_status', {'status': 'not_downloaded', 'error': None}):
        # Call the function
        download_model_task()
        
        # Verify the model status was updated
        from app.tts_model.tts_model import model_status
        assert model_status['status'] == 'downloaded'
        assert model_status['error'] is None

def test_download_model_task_error(mock_tts, temp_model_dir):
    """Test download_model_task function when an error occurs"""
    with patch('app.tts_model.tts_model.model_status', {'status': 'not_downloaded', 'error': None}):
        with patch('app.tts_model.tts_model.TTS', side_effect=Exception("Test error")):
            # Call the function
            download_model_task()
            
            # Verify the model status was updated
            from app.tts_model.tts_model import model_status
            assert model_status['status'] == 'failed'
            assert model_status['error'] == "Test error"

def test_start_model_download_already_downloading():
    """Test start_model_download function when model is already downloading"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'downloading', 'error': None}):
        # Call the function
        result = start_model_download()
        
        # Verify the result
        assert result is False

def test_start_model_download_already_downloaded_no_force():
    """Test start_model_download function when model is already downloaded and force is False"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'downloaded', 'error': None}):
        # Call the function
        result = start_model_download(force=False)
        
        # Verify the result
        assert result is False

def test_start_model_download_already_downloaded_force():
    """Test start_model_download function when model is already downloaded and force is True"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'downloaded', 'error': None}):
        with patch('app.tts_model.tts_model.threading.Thread') as mock_thread:
            with patch('app.tts_model.tts_model.model_status', {'status': 'downloaded', 'error': None}):
                # Call the function
                result = start_model_download(force=True)
                
                # Verify the result
                assert result is True
                assert mock_thread.called
                assert mock_thread.return_value.start.called
                
                # Verify model status was reset
                from app.tts_model.tts_model import model_status
                assert model_status['status'] == 'not_downloaded'

def test_start_model_download_not_downloaded():
    """Test start_model_download function when model is not downloaded"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'not_downloaded', 'error': None}):
        with patch('app.tts_model.tts_model.threading.Thread') as mock_thread:
            # Call the function
            result = start_model_download()
            
            # Verify the result
            assert result is True
            assert mock_thread.called
            assert mock_thread.return_value.start.called

def test_get_tts_model_not_downloaded():
    """Test get_tts_model function when model is not downloaded"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'not_downloaded', 'error': None}):
        # Call the function
        result = get_tts_model()
        
        # Verify the result
        assert result is None

def test_get_tts_model_downloaded(mock_tts, mock_torch):
    """Test get_tts_model function when model is downloaded"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'downloaded', 'error': None}):
        # Call the function
        result = get_tts_model()
        
        # Verify the result
        assert result is not None
        assert isinstance(result, MockTTS)
        assert result.model_name == MODEL_NAME

def test_get_tts_model_error(mock_tts, mock_torch):
    """Test get_tts_model function when an error occurs"""
    with patch('app.tts_model.tts_model.get_model_status', return_value={'status': 'downloaded', 'error': None}):
        with patch('app.tts_model.tts_model.TTS', side_effect=Exception("Test error")):
            # Call the function
            result = get_tts_model()
            
            # Verify the result
            assert result is None