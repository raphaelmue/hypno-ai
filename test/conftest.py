"""
Pytest configuration file.
This file is automatically loaded by pytest and can be used to configure the test environment.
"""

import os
import sys

# Add the project root directory to the Python path
# This allows the tests to import modules from the app package
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Import pytest fixtures that should be available to all tests
import pytest

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Set up the test environment.
    This fixture runs automatically before any tests and sets up the environment.
    """
    # Print information about the test environment
    print(f"Setting up test environment")
    print(f"Python path: {sys.path}")
    print(f"Project root: {project_root}")
    
    # Yield to allow tests to run
    yield
    
    # Clean up after tests if needed
    print(f"Cleaning up test environment")