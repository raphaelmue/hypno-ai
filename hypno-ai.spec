# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/static/voices', 'app/static/voices'),
        ('app/static/output', 'app/static/output'),
        ('app/data', 'app/data'),
    ],
    hiddenimports=[
        'app.desktop.main_window',
        'app.desktop.routines_list',
        'app.desktop.routine_editor',
        'app.desktop.task_manager',
        'app.models.routine',
        'app.audio.audio',
        'app.tasks.tasks',
        'app.utils',
        'app.config',
        'TTS',
        'TTS.api',
        'pydub',
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtWidgets',
        'PyQt6.QtMultimedia',
    ],
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
)

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

# macOS specific
app = BUNDLE(
    coll,
    name='Hypno-AI.app',
    bundle_identifier='com.yourusername.hypno-ai',
    info_plist={
        'NSHighResolutionCapable': 'True',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
    },
)
