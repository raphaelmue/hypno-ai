#!/bin/bash

echo "==================================================="
echo "Hypno-AI Run Script for Unix-based Systems"
echo "==================================================="
echo

# Check for installation directory parameter
INSTALL_DIR="$1"
if [ -z "$INSTALL_DIR" ]; then
    echo "No installation directory specified. Using current directory."
    INSTALL_DIR=$(pwd)
else
    echo "Installation directory specified: $INSTALL_DIR"
    if [ ! -d "$INSTALL_DIR" ]; then
        echo "Error: Directory $INSTALL_DIR does not exist."
        echo "Please run the setup script first."
        exit 1
    fi
    cd "$INSTALL_DIR" || exit 1
fi

# Check if repository exists
if [ ! -d "hypno-ai" ]; then
    echo "Error: Hypno-AI repository not found in $INSTALL_DIR."
    echo "Please run the setup script first."
    exit 1
fi

# Navigate to repository directory
cd hypno-ai || exit 1

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found."
    echo "Please run the setup script first."
    exit 1
fi

# Activate virtual environment and run the application
echo
echo "Activating virtual environment and running the application..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment."
    exit 1
fi

echo
echo "Starting Hypno-AI..."
python main.py
if [ $? -ne 0 ]; then
    echo "Application exited with an error."
    exit 1
fi

# Deactivate virtual environment
deactivate

# Make the script executable
chmod +x run.sh