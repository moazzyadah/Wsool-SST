"""Paste text at cursor position — supports Arabic and English.

Captures the foreground window handle before clipboard operations
and verifies it hasn't changed before sending Ctrl+V.
"""

import time
import logging
import pyperclip

log = logging.getLogger("vtt")


def _get_foreground_hwnd() -> int | None:
    """Get the current foreground window handle (Windows only)."""
    try:
        import ctypes
        return ctypes.windll.user32.GetForegroundWindow()
    except Exception:
        return None


def paste_text(text: str):
    """Paste text at the current cursor position in any application.

    Uses clipboard + Win32 SendInput for reliable Ctrl+V on Windows.
    Verifies the foreground window hasn't changed between copy and paste
    to prevent pasting into the wrong application.
    """
    if not text:
        return

    # Capture target window BEFORE touching the clipboard
    target_hwnd = _get_foreground_hwnd()

    # Save current clipboard
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        old_clipboard = ""

    try:
        pyperclip.copy(text)
        time.sleep(0.1)

        # Verify focus hasn't changed
        current_hwnd = _get_foreground_hwnd()
        if target_hwnd is not None and current_hwnd != target_hwnd:
            log.warning("[PASTE] Focus changed between copy and paste — aborting to prevent wrong-window paste.")
            return

        _send_ctrl_v()
        time.sleep(0.15)
    finally:
        try:
            pyperclip.copy(old_clipboard)
        except Exception:
            pass


def _send_ctrl_v():
    """Send Ctrl+V using the most reliable method available."""
    try:
        _send_ctrl_v_win32()
    except Exception as e:
        log.warning(f"[PASTE] win32 failed ({e}), trying pyautogui...")
        _send_ctrl_v_pyautogui()


def _send_ctrl_v_win32():
    """Send Ctrl+V via Win32 SendInput — works regardless of focus."""
    import ctypes

    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1
    VK_CONTROL = 0x11
    VK_V = 0x56

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class INPUT(ctypes.Structure):
        _fields_ = [
            ("type", ctypes.c_ulong),
            ("ki", KEYBDINPUT),
            ("padding", ctypes.c_ubyte * 8),
        ]

    def make_key(vk, flags=0):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki.wVk = vk
        inp.ki.dwFlags = flags
        return inp

    inputs = [
        make_key(VK_CONTROL),                       # Ctrl down
        make_key(VK_V),                             # V down
        make_key(VK_V, KEYEVENTF_KEYUP),            # V up
        make_key(VK_CONTROL, KEYEVENTF_KEYUP),      # Ctrl up
    ]

    arr = (INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _send_ctrl_v_pyautogui():
    """Fallback: send Ctrl+V via pyautogui."""
    import pyautogui
    pyautogui.hotkey("ctrl", "v")
