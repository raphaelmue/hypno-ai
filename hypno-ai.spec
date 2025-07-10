# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import site
from pathlib import Path
import importlib.util

block_cipher = None

# Create a directory for gruut VERSION file if needed
gruut_version_dir = os.path.join('build', 'temp', 'gruut')
os.makedirs(gruut_version_dir, exist_ok=True)
with open(os.path.join(gruut_version_dir, 'VERSION'), 'w') as f:
    f.write('0.0.0')  # Placeholder version

# Fix path separators for cross-platform compatibility
def fix_path(path):
    return path.replace('/', os.sep)

# Platform-specific configurations
is_windows = sys.platform.startswith('win')
is_mac = sys.platform.startswith('darwin')
is_linux = sys.platform.startswith('linux')

# Find the TTS package location
def find_tts_package():
    # Try to find TTS using importlib
    tts_spec = importlib.util.find_spec('TTS')
    if tts_spec and tts_spec.origin:
        # Get the directory containing the TTS package
        tts_dir = os.path.dirname(os.path.dirname(tts_spec.origin))
        return os.path.join(tts_dir, 'TTS')

    # Fallback to site-packages
    for site_dir in site.getsitepackages():
        tts_path = os.path.join(site_dir, 'TTS')
        if os.path.exists(tts_path):
            return tts_path

    # Check for virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        venv_site_packages = os.path.join(sys.prefix, 'lib', 'python{}.{}'.format(
            sys.version_info.major, sys.version_info.minor), 'site-packages')
        tts_path = os.path.join(venv_site_packages, 'TTS')
        if os.path.exists(tts_path):
            return tts_path

        # Windows-specific path
        if is_windows:
            venv_site_packages = os.path.join(sys.prefix, 'Lib', 'site-packages')
            tts_path = os.path.join(venv_site_packages, 'TTS')
            if os.path.exists(tts_path):
                return tts_path

    # Last resort: try current directory
    local_tts = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'TTS')
    if os.path.exists(local_tts):
        return local_tts

    # If all else fails, return a default path and let PyInstaller handle the error
    return os.path.join(site.getsitepackages()[0], 'TTS')

tts_path = find_tts_package()

# Common data files
datas = [
    # Built-in voices that are packaged with the application
    (fix_path('app/static/voices'), fix_path('app/static/voices')),
    # Add gruut VERSION file
    (os.path.join(gruut_version_dir, 'VERSION'), 'gruut'),
]

# Add TTS vocoder directories if they exist
tts_vocoder_dirs = [
    ('configs', os.path.join('TTS', 'vocoder', 'configs')),
    ('models', os.path.join('TTS', 'vocoder', 'models')),
    ('utils', os.path.join('TTS', 'vocoder', 'utils')),
    ('datasets', os.path.join('TTS', 'vocoder', 'datasets')),
    ('layers', os.path.join('TTS', 'vocoder', 'layers')),
]

for dir_name, dest_path in tts_vocoder_dirs:
    src_path = os.path.join(tts_path, 'vocoder', dir_name)
    if os.path.exists(src_path):
        print(f"Adding TTS vocoder directory: {src_path}")
        datas.append((src_path, dest_path))
    else:
        print(f"Warning: TTS vocoder directory not found: {src_path}")
        # Create an empty directory to satisfy PyInstaller
        os.makedirs(os.path.join('build', 'temp', dest_path), exist_ok=True)
        datas.append((os.path.join('build', 'temp', dest_path), dest_path))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'app.desktop.main_window',
        'app.desktop.routines_list',
        'app.desktop.routine_editor',
        'app.desktop.task_manager',
        'app.desktop.settings_dialog',
        'app.models.database',
        'app.models.migrations',
        'app.models.routine',
        'app.models.settings',
        'app.audio.audio',
        'app.tasks.tasks',
        'app.utils',
        'app.config',
        'TTS',
        'TTS.api',
        'pydub',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtMultimedia',
        'alembic',
        'inflect',
        'inflect.compat',
        'inflect.compat.py38',
        'gruut',
        'gruut.const',
        'gruut.g2p',
        'gruut.lang',
        'gruut.phonemize',
        'gruut.pos',
        'gruut.resources',
        'gruut.text_processor',
        'gruut.utils',
        'gruut_ipa',
    ],
    hookspath=['build/hooks'],
    hooksconfig={},
    runtime_hooks=['build/hooks/runtime_hook.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Common EXE configuration
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Hypno-AI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add an icon file here if available
)

# Create the collection
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Hypno-AI',
)

# macOS specific bundle
if is_mac:
    app = BUNDLE(
        coll,
        name='Hypno-AI.app',
        bundle_identifier='com.hypno-ai.app',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '1.0.0',
            'CFBundleVersion': '1.0.0',
            'CFBundleName': 'Hypno-AI',
            'CFBundleDisplayName': 'Hypno-AI',
            'CFBundleExecutable': 'Hypno-AI',
            'CFBundleIconFile': 'icon.icns',  # Add an icon file here if available
        },
    )
