#!/bin/bash
# Build script for packaging HypnoAI desktop app
# This script handles both the Python backend and Electron frontend

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Determine platform
PLATFORM="$(uname -s)"
case "${PLATFORM}" in
    Linux*)     OS=linux;;
    Darwin*)    OS=mac;;
    MINGW*|MSYS*|CYGWIN*) OS=win;;
    *)          OS="unknown";;
esac

# Determine architecture
ARCH="$(uname -m)"
case "${ARCH}" in
    x86_64)     ARCH=x64;;
    aarch64|arm64) ARCH=arm64;;
    *)          ARCH="unknown";;
esac

log_info "Building for ${OS}-${ARCH}"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    log_error "Please run this script from the repository root"
    exit 1
fi

# Step 1: Install Python dependencies
log_info "Installing Python dependencies..."
if [ ! -d ".venv" ]; then
    log_info "Creating virtual environment..."
    python -m venv .venv
fi

# Activate virtual environment
if [ "$OS" = "win" ]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi

# Install dependencies including PyInstaller
pip install -e ".[dev,piper,pitch]" || {
    log_error "Failed to install Python dependencies"
    exit 1
}

log_success "Python dependencies installed"

# Step 2: Build Python sidecar with PyInstaller
log_info "Building Python sidecar executable with PyInstaller..."
mkdir -p dist

# Set extension based on OS
EXT=""
if [ "$OS" = "win" ]; then
    EXT=".exe"
fi

# Build with PyInstaller
pyinstaller hypnoai-sidecar.spec --clean --noconfirm || {
    log_error "PyInstaller build failed"
    exit 1
}

# Move built executable to dist with platform-specific name
SIDECAR_SRC="dist/hypnoai-sidecar/hypnoai-sidecar${EXT}"
SIDECAR_DEST="dist/hypnoai-sidecar-${OS}-${ARCH}"

if [ ! -f "$SIDECAR_SRC" ]; then
    log_error "Sidecar executable not found at $SIDECAR_SRC"
    exit 1
fi

# Create both platform-specific and generic copies
mkdir -p "$SIDECAR_DEST"
cp -r dist/hypnoai-sidecar/* "$SIDECAR_DEST/"
log_success "Python sidecar built: $SIDECAR_DEST"

# Create symlink or copy to generic location for electron-builder
# (electron-builder expects dist/hypnoai-sidecar/)
# Note: This is the active copy that electron-builder will use
log_info "Creating generic sidecar copy for electron-builder..."
# On Windows, copy instead of symlink (symlinks require admin)
if [ "$OS" = "win" ]; then
    # Already have dist/hypnoai-sidecar from PyInstaller
    log_success "Using existing dist/hypnoai-sidecar"
else
    # On Unix, we can keep the original
    log_success "Using dist/hypnoai-sidecar"
fi

# Step 3: Build Electron app
log_info "Building Electron app..."
cd desktop

# Install Node dependencies
if [ ! -d "node_modules" ]; then
    log_info "Installing Node dependencies..."
    corepack enable
    yarn install || {
        log_error "Failed to install Node dependencies"
        exit 1
    }
fi

# Type-check
log_info "Type-checking..."
yarn typecheck || {
    log_warn "Type-check failed, continuing anyway..."
}

# Build frontend
log_info "Building frontend..."
yarn build || {
    log_error "Frontend build failed"
    exit 1
}

log_success "Frontend built"

# Step 4: Package with electron-builder
log_info "Packaging application with electron-builder..."

# Override extraResources path for electron-builder
# electron-builder will look for dist/hypnoai-sidecar-${os}-${arch}
yarn build:dist || {
    log_error "electron-builder packaging failed"
    exit 1
}

log_success "Application packaged successfully!"
log_info "Output directory: desktop/release/"

# List built artifacts
cd release
log_info "Built artifacts:"
ls -lh

log_success "Build complete! 🎉"
