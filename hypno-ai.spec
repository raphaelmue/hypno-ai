# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# Fix path separators for cross-platform compatibility
def fix_path(path):
    return path.replace('/', os.sep)

# Platform-specific configurations
is_windows = sys.platform.startswith('win')
is_mac = sys.platform.startswith('darwin')
is_linux = sys.platform.startswith('linux')

# Common data files
datas = [
    # Built-in voices that are packaged with the application
    (fix_path('app/static/voices'), fix_path('app/static/voices')),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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
