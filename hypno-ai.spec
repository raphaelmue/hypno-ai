# -*- mode: python ; coding: utf-8 -*-
import sys, os
from PyInstaller.utils.hooks import (
    get_package_paths,
    copy_metadata,
    collect_dynamic_libs,
    collect_submodules,
    collect_data_files,
)

block_cipher = None

def fix_path(path):
    return path.replace('/', os.sep)

is_windows = sys.platform.startswith('win')
is_mac     = sys.platform.startswith('darwin')
is_linux   = sys.platform.startswith('linux')

# Collect your app’s voices as before…
datas = [
    (fix_path('app/static/voices'), fix_path('app/static/voices')),
]

# 1) your voices folder
datas = [
    (fix_path('app/static/voices'), fix_path('app/static/voices')),
]

# 2) bundle TTS as a real folder + its metadata
pkg_base, pkg_dir = get_package_paths('TTS')
datas.append((pkg_dir, 'TTS'))
datas += copy_metadata('coqui-tts')
datas += collect_data_files('TTS', include_py_files=True)

# 3) bundle torch as a real folder + its metadata + its data
torch_base, torch_dir = get_package_paths('torch')
datas.append((torch_dir, 'torch'))
datas += copy_metadata('torch')
datas += collect_data_files('torch', include_py_files=True)

# 4) collect torch native libs and any submodules
binaries = collect_dynamic_libs('torch')
hiddenimports = (
    collect_submodules('torch')
    + ['pickletools', 'unittest.mock', 'fsspec', 'coqpit', 'trainer', 'librosa', 'torchaudio', 'transformers', 'anyascii', 'inflect']
)

# 5) prevent both packages from being zipped into the .pyz
excludes = ['TTS', 'torch']

# 6) Bundle torchgen so `import torchgen` actually finds real code
try:
    tg_base, tg_dir = get_package_paths('torchgen')
    datas.append((tg_dir, 'torchgen'))
    datas += copy_metadata('torchgen')
    hiddenimports += collect_submodules('torchgen')
except ModuleNotFoundError:
    # if for some reason torchgen isn't a standalone dir in your site-packages
    pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
   pyz,
   a.scripts,
   a.binaries,
   a.zipfiles,
   a.datas,
   name='Hypno-AI',
   debug=False,
   strip=False,
   upx=True,
   upx_exclude=[],
   console=True,
   noarchive=True
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
