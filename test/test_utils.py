import pytest
from unittest.mock import patch

from app.utils.utils import allowed_file, slugify

@pytest.fixture
def mock_allowed_extensions():
    with patch('app.utils.utils.ALLOWED_EXTENSIONS', {'wav', 'mp3', 'ogg'}):
        yield

class TestAllowedFile:
    def test_allowed_extensions(self, mock_allowed_extensions):
        """Test allowed_file function with allowed extensions"""
        assert allowed_file('test.wav') is True
        assert allowed_file('test.mp3') is True
        assert allowed_file('test.ogg') is True
        
    def test_disallowed_extensions(self, mock_allowed_extensions):
        """Test allowed_file function with disallowed extensions"""
        assert allowed_file('test.txt') is False
        assert allowed_file('test.pdf') is False
        assert allowed_file('test.exe') is False
        
    def test_no_extension(self, mock_allowed_extensions):
        """Test allowed_file function with no extension"""
        assert allowed_file('test') is False
        
    def test_empty_filename(self, mock_allowed_extensions):
        """Test allowed_file function with empty filename"""
        assert allowed_file('') is False
        
    def test_case_insensitivity(self, mock_allowed_extensions):
        """Test allowed_file function is case insensitive"""
        assert allowed_file('test.WAV') is True
        assert allowed_file('test.Mp3') is True
        assert allowed_file('test.OGG') is True

class TestSlugify:
    def test_basic_slugify(self):
        """Test basic slugify functionality"""
        assert slugify('Hello World') == 'hello-world'
        
    def test_special_characters(self):
        """Test slugify with special characters"""
        assert slugify('Hello, World!') == 'hello-world'
        assert slugify('Hello & World') == 'hello-world'
        assert slugify('Hello_World') == 'hello-world'
        
    def test_multiple_spaces(self):
        """Test slugify with multiple spaces"""
        assert slugify('Hello   World') == 'hello-world'
        
    def test_leading_trailing_spaces(self):
        """Test slugify with leading/trailing spaces"""
        assert slugify('  Hello World  ') == 'hello-world'
        
    def test_unicode_characters(self):
        """Test slugify with unicode characters"""
        assert slugify('Héllö Wörld') == 'hello-world'
        assert slugify('こんにちは世界') == 'routine'  # Non-ASCII characters are removed
        
    def test_numbers(self):
        """Test slugify with numbers"""
        assert slugify('Hello 123') == 'hello-123'
        
    def test_leading_trailing_hyphens(self):
        """Test slugify removes leading/trailing hyphens"""
        assert slugify('-Hello World-') == 'hello-world'
        
    def test_empty_string(self):
        """Test slugify with empty string"""
        assert slugify('') == 'routine'
        
    def test_only_special_characters(self):
        """Test slugify with only special characters"""
        assert slugify('!@#$%^&*()') == 'routine'