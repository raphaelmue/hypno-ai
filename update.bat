@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo Hypno-AI Update Script for Windows
echo ===================================================
echo.

:: Check for installation directory parameter
set INSTALL_DIR=%~1
if "%INSTALL_DIR%"=="" (
    echo No installation directory specified. Using current directory.
    set "INSTALL_DIR=%CD%"
) else (
    echo Installation directory specified: %INSTALL_DIR%
    if not exist "%INSTALL_DIR%" (
        echo Error: Directory %INSTALL_DIR% does not exist.
        echo Please run the setup script first.
        pause
        exit /b 1
    )
    cd /d "%INSTALL_DIR%"
)

:: Check if repository exists
if not exist "hypno-ai" (
    echo Error: Hypno-AI repository not found in %INSTALL_DIR%.
    echo Please run the setup script first.
    pause
    exit /b 1
)

:: Navigate to repository directory
cd hypno-ai

:: Check if git is installed and if this is a git repository
echo Checking for Git installation...
git --version > nul 2>&1
set GIT_INSTALLED=%errorlevel%

if %GIT_INSTALLED% equ 0 (
    if exist ".git" (
        echo Using Git to update repository...
        git pull
        if %errorlevel% neq 0 (
            echo Warning: Failed to pull latest changes. Continuing with existing code.
        )
    ) else (
        echo This is not a Git repository. Cannot update automatically.
        echo Consider reinstalling using the setup script.
        pause
        exit /b 1
    )
) else (
    echo Git not installed. Cannot update automatically.
    echo Consider reinstalling using the setup script.
    pause
    exit /b 1
)

:: Activate virtual environment and update dependencies
echo.
echo Activating virtual environment and updating dependencies...
if not exist ".venv" (
    echo Error: Virtual environment not found.
    echo Please run the setup script first.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Updating dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt --upgrade
if %errorlevel% neq 0 (
    echo Failed to update dependencies.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Update completed successfully!
echo.
echo To run Hypno-AI:
echo 1. Use the run.bat script
echo   or
echo 2. Navigate to the repository directory: cd hypno-ai
echo 3. Activate the virtual environment: .venv\Scripts\activate
echo 4. Run the application: python main.py
echo ===================================================
echo.

pause