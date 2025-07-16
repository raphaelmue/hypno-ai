#!/bin/bash

echo "==================================================="
echo "Hypno-AI Setup Script for Unix-based Systems"
echo "==================================================="
echo

# Check for installation directory parameter
INSTALL_DIR="$1"
if [ -z "$INSTALL_DIR" ]; then
    echo "No installation directory specified. Using default directory."
    INSTALL_DIR=$(pwd)
else
    echo "Installation directory specified: $INSTALL_DIR"
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "Creating directory $INSTALL_DIR..."
        mkdir -p "$INSTALL_DIR"
        if [ $? -ne 0 ]; then
            echo "Failed to create directory."
            exit 1
        fi
    fi
    cd "$INSTALL_DIR" || exit 1
fi

# Check if Python is installed
echo "Checking for Python installation..."
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is not installed or not in PATH."
    echo
    echo "Please install Python 3.10 or higher:"
    echo "- For Ubuntu/Debian: sudo apt update && sudo apt install python3 python3-pip python3-venv"
    echo "- For Fedora: sudo dnf install python3 python3-pip"
    echo "- For macOS with Homebrew: brew install python"
    echo "- Or download from: https://www.python.org/downloads/"
    echo
    echo "After installing Python, run this script again."
    exit 1
else
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
    echo "Found Python $PYTHON_VERSION"

    # Check Python version
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
        echo "Python 3.10 or higher is required."
        echo "Please install a newer version of Python."
        exit 1
    fi
fi

# Check if git is installed
echo
echo "Checking for Git installation..."
if command -v git &> /dev/null; then
    GIT_INSTALLED=true
    echo "Git is installed."
else
    GIT_INSTALLED=false
    echo "Git is not installed. Will use direct download method."
fi

# Repository URL
REPO_URL="https://github.com/raphaelmue/hypno-ai.git"
REPO_ZIP_URL="https://github.com/raphaelmue/hypno-ai/archive/refs/heads/main.zip"
REPO_DIR="hypno-ai"

# Create or navigate to project directory
if [ ! -d "$REPO_DIR" ]; then
    echo
    echo "Repository not found locally. Downloading..."

    if [ "$GIT_INSTALLED" = true ]; then
        echo "Using Git to clone repository..."
        git clone $REPO_URL
        if [ $? -ne 0 ]; then
            echo "Failed to clone repository."
            exit 1
        fi
    else
        echo "Git not found. Downloading ZIP archive..."

        # Check if curl is available
        if command -v curl &> /dev/null; then
            echo "Using curl to download repository..."
            curl -L -o hypno-ai.zip $REPO_ZIP_URL
        # Check if wget is available
        elif command -v wget &> /dev/null; then
            echo "Using wget to download repository..."
            wget -O hypno-ai.zip $REPO_ZIP_URL
        else
            echo "Neither curl nor wget is available. Please install one of them and try again."
            echo "- For Ubuntu/Debian: sudo apt install curl"
            echo "- For Fedora: sudo dnf install curl"
            echo "- For macOS with Homebrew: brew install curl"
            exit 1
        fi

        if [ $? -ne 0 ]; then
            echo "Failed to download repository."
            exit 1
        fi

        echo "Extracting ZIP archive..."
        # Check if unzip is available
        if command -v unzip &> /dev/null; then
            unzip hypno-ai.zip
            mv hypno-ai-main $REPO_DIR
        else
            echo "unzip is not installed. Please install it and try again."
            echo "- For Ubuntu/Debian: sudo apt install unzip"
            echo "- For Fedora: sudo dnf install unzip"
            echo "- For macOS with Homebrew: brew install unzip"
            exit 1
        fi

        rm hypno-ai.zip
    fi
else
    echo
    echo "Repository directory already exists."
fi

# Navigate to repository directory
cd $REPO_DIR || exit 1

# Create virtual environment
echo
echo "Creating virtual environment..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
    echo "Failed to create virtual environment."
    exit 1
fi

# Activate virtual environment and install dependencies
echo
echo "Activating virtual environment and installing dependencies..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment."
    exit 1
fi

echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Failed to install dependencies."
    exit 1
fi

echo
echo "==================================================="
echo "Setup completed successfully!"
echo
echo "To start using Hypno-AI:"
echo "1. Navigate to the repository directory: cd $REPO_DIR"
echo "2. Run run.sh"
echo "==================================================="
echo

# Make the script executable
chmod +x setup.sh
