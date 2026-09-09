# -*- mode: python ; coding: utf-8 -*-
# SWARAJ Desktop — PyInstaller build spec
# Output: dist/SwarajDesktop/SwarajDesktop.exe  (one-dir bundle)
#
# NOTE: The GGUF model file is NOT bundled here because it is 2+ GB.
# After building, copy your .gguf model into:
#   dist/SwarajDesktop/models/<your-model>.gguf
# The launcher auto-discovers any *.gguf file in that folder at runtime.

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None
BASE_DIR = Path.cwd()

# ── Data files bundled into _MEIPASS ──────────────────────────────────────────
datas = [
    (str(BASE_DIR / "ui-web" / "dist"),                                   "ui-web/dist"),
    (str(BASE_DIR / "src" / "swaraj" / "registry" / "manifests"),        "src/swaraj/registry/manifests"),
    (str(BASE_DIR / "policies"),                                           "policies"),
    (str(BASE_DIR / "users.json"),                                         "."),
    (str(BASE_DIR / "data" / "capability_vectors.json"),                  "data"),
    (str(BASE_DIR / "data" / "calibration.json"),                         "data"),
]

# ── Native binaries (llama_cpp shared libs) ───────────────────────────────────
binaries = []
try:
    binaries += collect_dynamic_libs('llama_cpp')
except Exception:
    pass

# ── Hidden imports that PyInstaller misses ────────────────────────────────────
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'pydantic',
    'pydantic_settings',
    'starlette',
    'docx',
    'openpyxl',
    'llama_cpp',
    'cryptography',
    'psutil',
    'yaml',
    'pypdf',
    'chromadb',
]
hiddenimports += collect_submodules('swaraj')

a = Analysis(
    ['desktop_launcher.py'],
    pathex=[str(BASE_DIR), str(BASE_DIR / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'IPython', 'notebook', 'pytest'],
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
    name='SwarajDesktop',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # Keep console for startup diagnostics — set False for silent launch
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,     # TODO: add icon=str(BASE_DIR / "assets/icon.ico") when available
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SwarajDesktop',
)

