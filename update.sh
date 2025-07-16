#!/bin/bash

echo "==================================================="
echo "Hypno-AI Update Script for Unix-based Systems"
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

# Check if git is installed and if this is a git repository
echo "Checking for Git installation..."
if command -v git &> /dev/null; then
    GIT_INSTALLED=true
    echo "Git is installed."
else
    GIT_INSTALLED=false
    echo "Git is not installed. Cannot update automatically."
    echo "Consider reinstalling using the setup script."
    exit 1
fi

if [ "$GIT_INSTALLED" = true ]; then
    if [ -d ".git" ]; then
        echo "Using Git to update repository..."
        git pull
        if [ $? -ne 0 ]; then
            echo "Warning: Failed to pull latest changes. Continuing with existing code."
        fi
    else
        echo "This is not a Git repository. Cannot update automatically."
        echo "Consider reinstalling using the setup script."
        exit 1
    fi
fi

# Activate virtual environment and update dependencies
echo
echo "Activating virtual environment and updating dependencies..."
if [ ! -d ".venv" ]; then
    echo "Error: Virtual environment not found."
    echo "Please run the setup script first."
    exit 1
fi

source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "Failed to activate virtual environment."
    exit 1
fi

echo "Updating dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt --upgrade
if [ $? -ne 0 ]; then
    echo "Failed to update dependencies."
    exit 1
fi

echo
echo "==================================================="
echo "Update completed successfully!"
echo
echo "To run Hypno-AI:"
echo "1. Use the run.sh script"
echo "  or"
echo "2. Navigate to the repository directory: cd hypno-ai"
echo "3. Activate the virtual environment: source .venv/bin/activate"
echo "4. Run the application: python main.py"
echo "==================================================="
echo

# Make the script executable
chmod +x update.sh