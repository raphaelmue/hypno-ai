@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo Hypno-AI Setup Script for Windows
echo ===================================================
echo.

:: Check for installation directory parameter
set INSTALL_DIR=%~1
if "%INSTALL_DIR%"=="" (
    echo No installation directory specified. Using default directory.
    set "INSTALL_DIR=%CD%"
) else (
    echo Installation directory specified: %INSTALL_DIR%
    if not exist "%INSTALL_DIR%" (
        echo Creating directory %INSTALL_DIR%...
        mkdir "%INSTALL_DIR%"
        if %errorlevel% neq 0 (
            echo Failed to create directory.
            pause
            exit /b 1
        )
    )
    cd /d "%INSTALL_DIR%"
)

:: Check if Python is installed
echo Checking for Python installation...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10 using the following command:
    echo winget install -e --id Python.Python.3.10
    echo.
    echo Make sure to check "Add Python to PATH" during installation.
    echo After installing Python, run this script again.
    pause
    exit /b 1
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo Found Python !PYTHON_VERSION!

    :: Check Python version
    for /f "tokens=1,2 delims=." %%a in ("!PYTHON_VERSION!") do (
        set PYTHON_MAJOR=%%a
        set PYTHON_MINOR=%%b
    )

    if !PYTHON_MAJOR! LSS 3 (
        echo Python 3.10 or higher is required.
        echo Please install a newer version of Python.
        pause
        exit /b 1
    ) else if !PYTHON_MAJOR! EQU 3 (
        if !PYTHON_MINOR! LSS 10 (
            echo Python 3.10 or higher is required.
            echo Please install a newer version of Python.
            pause
            exit /b 1
        )
    )
)

:: Check if git is installed
echo.
echo Checking for Git installation...
git --version > nul 2>&1
set GIT_INSTALLED=%errorlevel%

:: Repository URL
set REPO_URL=https://github.com/raphaelmue/hypno-ai.git
set REPO_ZIP_URL=https://github.com/raphaelmue/hypno-ai/archive/refs/heads/main.zip
set REPO_DIR=hypno-ai

:: Create or navigate to project directory
if not exist "%REPO_DIR%" (
    echo.
    echo Repository not found locally. Downloading...

    if %GIT_INSTALLED% equ 0 (
        echo Using Git to clone repository...
        git clone %REPO_URL%
        if %errorlevel% neq 0 (
            echo Failed to clone repository.
            pause
            exit /b 1
        )
    ) else (
        echo Git not found. Downloading ZIP archive...

        :: Check if curl is available
        curl --version > nul 2>&1
        if %errorlevel% equ 0 (
            echo Using curl to download repository...
            curl -L -o hypno-ai.zip %REPO_ZIP_URL%
        ) else (
            :: Use PowerShell if curl is not available
            echo Using PowerShell to download repository...
            powershell -Command "Invoke-WebRequest -Uri '%REPO_ZIP_URL%' -OutFile 'hypno-ai.zip'"
        )

        if %errorlevel% neq 0 (
            echo Failed to download repository.
            pause
            exit /b 1
        )

        echo Extracting ZIP archive...
        powershell -Command "Expand-Archive -Path 'hypno-ai.zip' -DestinationPath '.'"
        move hypno-ai-main %REPO_DIR%
        del hypno-ai.zip
    )
) else (
    echo.
    echo Repository directory already exists.
)

:: Navigate to repository directory
cd %REPO_DIR%

:: Create virtual environment
echo.
echo Creating virtual environment...
python -m venv .venv
if %errorlevel% neq 0 (
    echo Failed to create virtual environment.
    pause
    exit /b 1
)

:: Activate virtual environment and install dependencies
echo.
echo Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo Setup completed successfully!
echo.
echo To start using Hypno-AI:
echo 1. Navigate to the repository directory: cd %REPO_DIR%
echo 2. Run the file run.bat
echo ===================================================
echo.

pause
