# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for WsoolSTT.exe — main app (windowed, onedir)."""

import os
import sys

block_cipher = None

# --- Locate sounddevice PortAudio DLLs ---
try:
    import sounddevice
    sd_pkg = os.path.dirname(sounddevice.__file__)
    sd_data = os.path.join(os.path.dirname(sd_pkg), '_sounddevice_data')
    sd_binaries = [
        (os.path.join(sd_data, 'portaudio-binaries', '*.dll'),
         '_sounddevice_data/portaudio-binaries'),
    ]
except ImportError:
    sd_binaries = []

# --- Locate Silero VAD ONNX model ---
silero_datas = []
try:
    import silero_vad
    pkg_dir = os.path.dirname(silero_vad.__file__)
    onnx_model = os.path.join(pkg_dir, 'data', 'silero_vad.onnx')
    if os.path.exists(onnx_model):
        silero_datas = [(onnx_model, '.')]
except ImportError:
    pass

# If no pip package, check local data/ directory
if not silero_datas:
    local_model = os.path.join(os.getcwd(), 'data', 'silero_vad.onnx')
    if os.path.exists(local_model):
        silero_datas = [(local_model, '.')]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=sd_binaries,
    datas=silero_datas,
    hiddenimports=[
        # pynput platform backends
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        # pystray platform backend
        'pystray._win32',
        # PIL
        'PIL._tkinter_finder',
        # ONNX Runtime
        'onnxruntime',
        # numpy
        'numpy',
        'numpy.core._methods',
        'numpy.lib.format',
        # audio
        'sounddevice',
        'playsound3',
        # paste
        'pyperclip',
        'pyautogui',
        'pyautogui._pyautogui_win',
        # config
        'dotenv',
        # HTTP
        'httpx',
        'httpx._transports',
        'httpcore',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not needed in main app
        'torch',
        'torchaudio',
        'torchvision',
        'customtkinter',
        'tkinter',
        'unittest',
        'test',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zips, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,       # --onedir mode
    name='WsoolSTT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                   # No UPX — avoids AV false positives
    console=False,               # Windowed app, no console
    icon='assets/WsoolSTT.ico' if os.path.exists('assets/WsoolSTT.ico') else None,
    version='version_info.txt' if os.path.exists('version_info.txt') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='WsoolSTT',
)
