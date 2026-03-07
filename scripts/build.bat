@echo off
REM Build script for packaging HypnoAI desktop app on Windows
REM This script handles both the Python backend and Electron frontend

setlocal enabledelayedexpansion

echo [INFO] Building for Windows...

REM Check if we're in the right directory
if not exist "pyproject.toml" (
    echo [ERROR] Please run this script from the repository root
    exit /b 1
)

REM Step 1: Install Python dependencies
echo [INFO] Installing Python dependencies...
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
)

REM Activate virtual environment
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)

REM Install dependencies including PyInstaller
echo [INFO] Installing Python packages...
pip install -e ".[dev,piper,pitch]"
if errorlevel 1 (
    echo [ERROR] Failed to install Python dependencies
    exit /b 1
)

echo [SUCCESS] Python dependencies installed

REM Step 2: Build Python sidecar with PyInstaller
echo [INFO] Building Python sidecar executable with PyInstaller...
if not exist "dist" mkdir dist

pyinstaller hypnoai-sidecar.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed
    exit /b 1
)

REM Determine architecture
set ARCH=x64
if "%PROCESSOR_ARCHITECTURE%"=="ARM64" set ARCH=arm64

REM Move built executable to dist with platform-specific name
set SIDECAR_SRC=dist\hypnoai-sidecar\hypnoai-sidecar.exe
set SIDECAR_DEST=dist\hypnoai-sidecar-win-%ARCH%

if not exist "%SIDECAR_SRC%" (
    echo [ERROR] Sidecar executable not found at %SIDECAR_SRC%
    exit /b 1
)

if not exist "%SIDECAR_DEST%" mkdir "%SIDECAR_DEST%"
xcopy /E /I /Y dist\hypnoai-sidecar\* "%SIDECAR_DEST%\"
echo [SUCCESS] Python sidecar built: %SIDECAR_DEST%

REM electron-builder expects dist/hypnoai-sidecar/ (already exists from PyInstaller)
echo [SUCCESS] Using existing dist\hypnoai-sidecar for electron-builder

REM Step 3: Build Electron app
echo [INFO] Building Electron app...
cd desktop

REM Install Node dependencies
if not exist "node_modules" (
    echo [INFO] Installing Node dependencies...
    call corepack enable
    call yarn install
    if errorlevel 1 (
        echo [ERROR] Failed to install Node dependencies
        exit /b 1
    )
)

REM Type-check
echo [INFO] Type-checking...
call yarn typecheck
if errorlevel 1 (
    echo [WARN] Type-check failed, continuing anyway...
)

REM Build frontend
echo [INFO] Building frontend...
call yarn build
if errorlevel 1 (
    echo [ERROR] Frontend build failed
    exit /b 1
)

echo [SUCCESS] Frontend built

REM Step 4: Package with electron-builder
echo [INFO] Packaging application with electron-builder...
call yarn build:dist
if errorlevel 1 (
    echo [ERROR] electron-builder packaging failed
    exit /b 1
)

echo [SUCCESS] Application packaged successfully!
echo [INFO] Output directory: desktop\release\

REM List built artifacts
cd release
echo [INFO] Built artifacts:
dir /B

echo [SUCCESS] Build complete!
cd ..\..
