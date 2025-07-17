import os
import pytest
import tempfile
import time
import logging
from unittest.mock import patch, MagicMock, call

from app.tasks.base_task_manager import BaseTaskManager, TaskProgressNotifier
from app.tasks.file_task_manager import FileTaskProgressNotifier, TaskManager as FileTaskManager
from app.desktop.qt_task_manager import QtTaskProgressNotifier, TaskManager as QtTaskManager

# Mock for TaskProgressNotifier
class MockTaskProgressNotifier(TaskProgressNotifier):
    def __init__(self):
        self.started_tasks = []
        self.progress_updates = []
        self.completed_tasks = []
        self.failed_tasks = []
    
    def notify_started(self, task_id):
        self.started_tasks.append(task_id)
    
    def notify_progress(self, task_id, percent, message):
        self.progress_updates.append((task_id, percent, message))
    
    def notify_completed(self, task_id, result):
        self.completed_tasks.append((task_id, result))
    
    def notify_failed(self, task_id, error):
        self.failed_tasks.append((task_id, error))

# Mock for QObject
class MockQObject:
    def __init__(self):
        pass

# Mock for pyqtSignal
class MockPyQtSignal:
    def __init__(self, *args):
        self.args = args
        self.connections = []
    
    def emit(self, *args):
        for callback in self.connections:
            callback(*args)
    
    def connect(self, callback):
        self.connections.append(callback)

@pytest.fixture
def mock_task_notifier():
    return MockTaskProgressNotifier()

@pytest.fixture
def mock_generate_audio():
    with patch('app.tasks.base_task_manager.generate_audio') as mock:
        mock.return_value = "test_output.wav"
        yield mock

@pytest.fixture
def mock_routine_functions():
    with patch('app.tasks.base_task_manager.add_routine') as mock_add, \
         patch('app.tasks.base_task_manager.update_routine') as mock_update, \
         patch('app.tasks.base_task_manager.get_routine') as mock_get:
        
        mock_routine = {
            'id': 'test_id',
            'name': 'Test Routine',
            'text': 'Test text',
            'language': 'en',
            'voice_type': 'sample',
            'voice_id': 'male1'
        }
        
        mock_add.return_value = mock_routine
        mock_update.return_value = mock_routine
        mock_get.return_value = mock_routine
        
        yield mock_add, mock_update, mock_get

@pytest.fixture
def mock_pyqt():
    # Create a mock QtTaskProgressNotifier class that matches the actual implementation
    class MockQtTaskProgressNotifier(MockQObject):
        def __init__(self):
            MockQObject.__init__(self)
            self.logger = logging.getLogger(__name__)
            self.task_started = MockPyQtSignal()
            self.task_progress = MockPyQtSignal(int, str)
            self.task_completed = MockPyQtSignal(dict)
            self.task_failed = MockPyQtSignal(str)
        
        def notify_started(self, task_id):
            self.task_started.emit()
        
        def notify_progress(self, task_id, percent, message):
            self.task_progress.emit(percent, message)
        
        def notify_completed(self, task_id, result):
            self.task_completed.emit(result)
        
        def notify_failed(self, task_id, error):
            self.task_failed.emit(error)
    
    with patch('app.desktop.qt_task_manager.QObject', MockQObject), \
         patch('app.desktop.qt_task_manager.pyqtSignal', MockPyQtSignal), \
         patch('app.desktop.qt_task_manager.QtTaskProgressNotifier', MockQtTaskProgressNotifier):
        yield

@pytest.fixture
def mock_json_operations():
    with patch('app.tasks.file_task_manager.json.dump') as mock_dump, \
         patch('app.tasks.file_task_manager.json.load') as mock_load:
        
        mock_load.return_value = {
            'status': 'processing',
            'result': None,
            'error': None,
            'created_at': time.time(),
            'progress': {
                'percent': 0,
                'message': 'Task started'
            }
        }
        
        yield mock_dump, mock_load

class TestBaseTaskManager:
    def test_init(self, mock_task_notifier):
        """Test BaseTaskManager initialization"""
        manager = BaseTaskManager(mock_task_notifier)
        assert manager.progress_notifier == mock_task_notifier
        assert manager.current_task is None
        assert manager.cancel_requested is False
    
    def test_is_task_running(self, mock_task_notifier):
        """Test is_task_running method"""
        manager = BaseTaskManager(mock_task_notifier)
        
        # No task running
        assert manager.is_task_running() is False
        
        # Mock a running task
        mock_task = MagicMock()
        mock_task.is_alive.return_value = True
        manager.current_task = mock_task
        
        assert manager.is_task_running() is True
        
        # Mock a completed task
        mock_task.is_alive.return_value = False
        assert manager.is_task_running() is False
    
    def test_cancel_task(self, mock_task_notifier):
        """Test cancel_task method"""
        manager = BaseTaskManager(mock_task_notifier)
        
        # No task running
        manager.cancel_task()
        assert manager.cancel_requested is False
        
        # Mock a running task
        mock_task = MagicMock()
        mock_task.is_alive.return_value = True
        manager.current_task = mock_task
        
        manager.cancel_task()
        assert manager.cancel_requested is True
    
    @patch('app.tasks.base_task_manager.threading.Thread')
    def test_start_task(self, mock_thread, mock_task_notifier, mock_generate_audio, mock_routine_functions):
        """Test start_task method"""
        manager = BaseTaskManager(mock_task_notifier)
        
        # Start a task
        task_id = manager.start_task(
            text="Test text",
            language="en",
            voice_path="/path/to/voice.wav",
            routine_name="Test Routine"
        )
        
        # Verify task ID is a string
        assert isinstance(task_id, str)
        
        # Verify thread was created and started
        assert mock_thread.called
        assert mock_thread.return_value.start.called
        
        # Verify notifier was called
        assert task_id in mock_task_notifier.started_tasks
    
    def test_cleanup_temp_file(self, mock_task_notifier, tmp_path):
        """Test _cleanup_temp_file method"""
        manager = BaseTaskManager(mock_task_notifier)
        
        # Create a temporary file
        temp_file = tmp_path / "voice.wav"
        temp_file.write_text("test")
        
        # Test with non-temporary file (should not be removed)
        manager._cleanup_temp_file("sample", str(temp_file))
        assert temp_file.exists(), "Non-temporary file should not be removed"
        
        # Test with upload file but without 'temp_' in name (should not be removed)
        manager._cleanup_temp_file("upload", str(temp_file))
        assert temp_file.exists(), "Upload file without 'temp_' in name should not be removed"
        
        # Test with temporary file that has 'temp_' in the name (should be removed)
        temp_file = tmp_path / "temp_voice.wav"
        temp_file.write_text("test")
        
        # Verify the file exists before cleanup
        assert temp_file.exists(), "File should exist before cleanup"
        
        # Call the cleanup method
        manager._cleanup_temp_file("upload", str(temp_file))
        
        # Verify the file was removed
        assert not os.path.exists(str(temp_file)), "File with 'temp_' in name should be removed"

class TestQtTaskManager:
    def test_init(self, mock_pyqt):
        """Test QtTaskManager initialization"""
        # Initialize the manager
        manager = QtTaskManager()
        
        # In the test environment, the notifier should have the required signals
        assert manager.notifier is not None, "TaskManager.notifier should not be None"
        assert hasattr(manager.notifier, 'task_started'), "Notifier should have task_started signal"
        assert hasattr(manager.notifier, 'task_progress'), "Notifier should have task_progress signal"
        assert hasattr(manager.notifier, 'task_completed'), "Notifier should have task_completed signal"
        assert hasattr(manager.notifier, 'task_failed'), "Notifier should have task_failed signal"
    
    def test_properties(self, mock_pyqt):
        """Test QtTaskManager properties"""
        manager = QtTaskManager()
        
        assert hasattr(manager, 'task_started')
        assert hasattr(manager, 'task_progress')
        assert hasattr(manager, 'task_completed')
        assert hasattr(manager, 'task_failed')

class TestFileTaskManager:
    def test_init(self):
        """Test FileTaskManager initialization"""
        manager = FileTaskManager()
        assert isinstance(manager.notifier, FileTaskProgressNotifier)
    
    def test_get_task_status(self):
        """Test get_task_status method"""
        # Create a mock status dictionary
        mock_status = {
            'status': 'processing',
            'result': None,
            'error': None,
            'created_at': time.time(),
            'progress': {
                'percent': 0,
                'message': 'Task started'
            }
        }
        
        # Create a task manager with a mocked notifier
        manager = FileTaskManager()
        
        # Replace the _load_task method with a mock that returns our status
        manager.notifier._load_task = MagicMock(return_value=mock_status)
        
        # Get status of a task
        status = manager.get_task_status("test_task_id")
        
        # Verify the _load_task method was called with the correct task_id
        manager.notifier._load_task.assert_called_once_with("test_task_id")
        
        # Verify status is returned
        assert status is not None, "get_task_status should return a status dictionary"
        assert 'status' in status, "Status dictionary should have a 'status' field"
        assert status['status'] == 'processing', "Status should be 'processing'"

@pytest.mark.parametrize("task_manager_class", [
    FileTaskManager,
    lambda: QtTaskManager() if QtTaskManager else None
])
def test_task_manager_factory_functions(task_manager_class, mock_pyqt, mock_json_operations):
    """Test task manager factory functions"""
    if task_manager_class == QtTaskManager and not QtTaskManager:
        pytest.skip("QtTaskManager not available")
    
    # Create a task manager
    manager = task_manager_class()
    
    # Verify it's the correct type
    assert isinstance(manager, BaseTaskManager)

def test_clean_old_tasks():
    """Test clean_old_tasks function"""
    from app.tasks.file_task_manager import clean_old_tasks, TASKS_FOLDER
    
    # Create a temporary task file
    os.makedirs(TASKS_FOLDER, exist_ok=True)
    task_file = os.path.join(TASKS_FOLDER, "old_task.json")
    with open(task_file, 'w') as f:
        f.write('{"status": "completed"}')
    
    # Set the file's modification time to 48 hours ago
    os.utime(task_file, (time.time() - 48*3600, time.time() - 48*3600))
    
    # Run the cleanup
    with patch('app.tasks.file_task_manager.time.time', return_value=time.time()):
        removed = clean_old_tasks()
    
    # Verify the file was removed
    assert removed >= 1
    assert not os.path.exists(task_file)