# Hypno-AI Setup Instructions

This document provides instructions for setting up the Hypno-AI application on your system.

## Automatic Setup

We provide automated setup scripts for both Windows and Unix-based systems (Linux, macOS) that will:
1. Check if Python is installed (and guide you to install it if needed)
2. Download the repository (with or without Git)
3. Create a virtual environment
4. Install all required dependencies

### Windows Setup

1. Download the `setup.bat` file
2. Double-click the file or run it from Command Prompt
3. Follow the on-screen instructions

To specify a custom installation directory:
```
setup.bat C:\path\to\install\directory
```

If Python is not installed, the script will direct you to download and install Python 3.10 or higher from the official Python website.

### Unix-based Systems Setup (Linux, macOS)

1. Download the `setup.sh` file
2. Make it executable: `chmod +x setup.sh`
3. Run the script: `./setup.sh`
4. Follow the on-screen instructions

To specify a custom installation directory:
```
./setup.sh /path/to/install/directory
```

If Python is not installed, the script will provide distribution-specific instructions for installing Python 3.10 or higher.

## Update and Run Scripts

We also provide scripts to update and run the application:

### Update Scripts

These scripts will update an existing installation by pulling the latest changes from the repository and updating dependencies.

#### Windows
```
update.bat [installation_directory]
```

#### Unix-based Systems
```
./update.sh [installation_directory]
```

### Run Scripts

These scripts will activate the virtual environment and run the application.

#### Windows
```
run.bat [installation_directory]
```

#### Unix-based Systems
```
./run.sh [installation_directory]
```

The installation directory parameter is optional. If not provided, the current directory will be used.

## Manual Setup

If you prefer to set up the project manually, follow these steps:

### Prerequisites

- Python 3.10 or higher
- Git (optional, for cloning the repository)

### Steps

1. **Clone or download the repository**:
   ```
   git clone https://github.com/raphaelmue/hypno-ai.git
   ```
   Or download and extract the ZIP file from the GitHub repository.

2. **Navigate to the project directory**:
   ```
   cd hypno-ai
   ```

3. **Create a virtual environment**:
   - Windows:
     ```
     python -m venv .venv
     .venv\Scripts\activate
     ```
   - Unix-based systems:
     ```
     python3 -m venv .venv
     source .venv/bin/activate
     ```

4. **Install dependencies**:
   ```
   pip install -r requirements.txt
   ```

5. **Run the application**:
   ```
   python main.py
   ```

## Troubleshooting

If you encounter any issues during setup:

1. **Python not found**: Ensure Python 3.10+ is installed and added to your PATH
2. **Virtual environment creation fails**: Make sure you have the venv module installed
3. **Dependency installation fails**: Check your internet connection and try again
4. **Permission issues on Unix**: Make sure the setup script is executable (`chmod +x setup.sh`)

For additional help, please open an issue on the GitHub repository.
