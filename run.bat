@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo Hypno-AI Run Script for Windows
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

:: Check if virtual environment exists
if not exist ".venv" (
    echo Error: Virtual environment not found.
    echo Please run the setup script first.
    pause
    exit /b 1
)

:: Activate virtual environment and run the application
echo.
echo Activating virtual environment and running the application...
call .venv\Scripts\activate.bat
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo.
echo Starting Hypno-AI...
python main.py
if %errorlevel% neq 0 (
    echo Application exited with an error.
    pause
    exit /b 1
)

:: Deactivate virtual environment
call deactivate

pause