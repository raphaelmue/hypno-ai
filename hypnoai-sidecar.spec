# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for hypnoai-sidecar executable.
This bundles the Python backend into a standalone executable for distribution.
"""
import sys
from pathlib import Path

block_cipher = None

# Determine the engine directory (where hypnoai module lives)
engine_dir = Path('engine').resolve()
hypnoai_dir = engine_dir / 'hypnoai'

# Collect all hypnoai package modules
a = Analysis(
    [str(hypnoai_dir / 'sidecar' / '__main__.py')],
    pathex=[str(engine_dir)],
    binaries=[],
    datas=[
        # Include AI templates
        (str(hypnoai_dir / 'ai' / 'templates'), 'hypnoai/ai/templates'),
    ],
    hiddenimports=[
        # Core modules
        'hypnoai.sidecar',
        'hypnoai.sidecar.server',
        'hypnoai.sidecar.session',
        'hypnoai.sidecar.handlers',
        'hypnoai.sidecar.handlers.config',
        'hypnoai.sidecar.handlers.voices',
        'hypnoai.sidecar.handlers.render',
        'hypnoai.sidecar.handlers.script_studio',
        'hypnoai.sidecar.handlers.models',
        # Parser
        'hypnoai.parser',
        'hypnoai.parser.lexer',
        'hypnoai.parser.parser',
        'hypnoai.parser.ast_nodes',
        'hypnoai.parser.variables',
        # TTS engines
        'hypnoai.tts',
        'hypnoai.tts.base',
        'hypnoai.tts.piper_engine',
        'hypnoai.tts.coqui_engine',
        'hypnoai.tts.kokoro_engine',
        'hypnoai.tts.styletts_engine',
        'hypnoai.tts.f5tts_engine',
        'hypnoai.tts.bark_engine',
        'hypnoai.tts.voice_registry',
        # Audio processing
        'hypnoai.audio',
        'hypnoai.audio.assembler',
        'hypnoai.audio.effects',
        'hypnoai.audio.normalize',
        'hypnoai.audio.limiter',
        'hypnoai.audio.post_processor',
        # Render pipeline
        'hypnoai.render',
        'hypnoai.render.pipeline',
        'hypnoai.render.cache',
        'hypnoai.render.worker',
        # AI integration
        'hypnoai.ai',
        'hypnoai.ai.base',
        'hypnoai.ai.ollama_provider',
        'hypnoai.ai.openai_provider',
        'hypnoai.ai.anthropic_provider',
        'hypnoai.ai.template_loader',
        'hypnoai.ai.script_studio',
        'hypnoai.ai.post_processor',
        # Resource management
        'hypnoai.resources',
        'hypnoai.resources.model_manager',
        'hypnoai.resources.model_downloader',
        'hypnoai.resources.voice_manager',
        # Config
        'hypnoai.config',
        # Third-party dependencies that need explicit imports
        'soundfile',
        'numpy',
        'scipy',
        'scipy.signal',
        'pyloudnorm',
        'librosa',
        'librosa.core',
        'librosa.effects',
        # Rich/Typer (for CLI functionality if used by sidecar)
        'rich',
        'typer',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test modules
        'tests',
        'pytest',
        'unittest',
        # Exclude dev tools
        'IPython',
        'jupyter',
        'matplotlib',
        # Exclude unnecessary standard library modules to reduce size
        'tkinter',
        'tcl',
        'test',
    ],
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
    name='hypnoai-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Console app for stdout/stderr communication
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
    name='hypnoai-sidecar',
)
