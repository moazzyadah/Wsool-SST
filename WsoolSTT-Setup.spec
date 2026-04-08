# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for WsoolSTT-Setup.exe — installer wizard (windowed, onedir)."""

import os

block_cipher = None

# --- Locate customtkinter assets ---
ctk_datas = []
try:
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)
    ctk_datas = [(ctk_path, 'customtkinter/')]
except ImportError:
    pass

a = Analysis(
    ['installer.py'],
    pathex=[],
    binaries=[],
    datas=ctk_datas,
    hiddenimports=[
        'customtkinter',
        'PIL._tkinter_finder',
        'httpx',
        'httpx._transports',
        'httpcore',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Not needed in installer
        'torch',
        'torchaudio',
        'torchvision',
        'onnxruntime',
        'numpy',
        'sounddevice',
        'pynput',
        'pystray',
        'pyautogui',
        'pyperclip',
        'playsound3',
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
    name='WsoolSTT-Setup',
    debug=False,
    strip=False,
    upx=True,                    # UPX OK here — no torch/ONNX
    console=False,               # Windowed wizard
    icon='assets/WsoolSTT.ico' if os.path.exists('assets/WsoolSTT.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='WsoolSTT-Setup',
)
