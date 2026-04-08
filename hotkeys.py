"""Global hotkey listener using pynput — manual key tracking for reliability."""

import threading
from pynput import keyboard


def _parse_combo(combo: str) -> frozenset:
    """Parse combo string like 'ctrl+alt+space' into a frozenset of key names."""
    parts = combo.lower().replace("<", "").replace(">", "").split("+")
    keys = set()
    for p in parts:
        p = p.strip()
        if p in ("ctrl", "ctrl_l", "ctrl_r"):
            keys.add("ctrl")
        elif p in ("alt", "alt_l", "alt_r"):
            keys.add("alt")
        elif p in ("shift", "shift_l", "shift_r"):
            keys.add("shift")
        elif p == "space":
            keys.add("space")
        else:
            keys.add(p)
    return frozenset(keys)


def _key_to_name(key) -> str:
    """Convert a pynput key to a normalized name string."""
    if isinstance(key, keyboard.Key):
        name = key.name  # e.g. "ctrl_l", "alt_r", "space", "shift"
        if name.startswith("ctrl"):
            return "ctrl"
        if name.startswith("alt"):
            return "alt"
        if name.startswith("shift"):
            return "shift"
        return name
    elif isinstance(key, keyboard.KeyCode):
        if key.char:
            return key.char.lower()
        if key.vk:
            # fallback: map vk to character
            return chr(key.vk).lower() if 32 <= key.vk <= 126 else str(key.vk)
    return ""


class HotkeyManager:
    """Registers global hotkeys using manual key-state tracking.

    More reliable than pynput.GlobalHotKeys on Windows because it
    tracks pressed keys directly instead of relying on the combo parser.
    """

    def __init__(self):
        self._combos: list[tuple[frozenset, callable]] = []
        self._pressed: set[str] = set()
        self._listener = None
        self._fired: set[frozenset] = set()  # prevent repeat-fire while held

    def register(self, combo: str, callback: callable):
        """Register a hotkey combination.

        Args:
            combo: e.g. "ctrl+alt+space", "<ctrl>+<shift>+l"
            callback: Function to call when hotkey is pressed.
        """
        keys = _parse_combo(combo)
        self._combos.append((keys, callback))

    def _on_press(self, key):
        name = _key_to_name(key)
        if not name:
            return
        self._pressed.add(name)

        for combo_keys, callback in self._combos:
            if combo_keys <= self._pressed and combo_keys not in self._fired:
                self._fired.add(combo_keys)
                threading.Thread(target=callback, daemon=True).start()

    def _on_release(self, key):
        name = _key_to_name(key)
        if not name:
            return
        self._pressed.discard(name)
        # Allow re-firing once any key in the combo is released
        to_remove = set()
        for combo_keys in self._fired:
            if name in combo_keys:
                to_remove.add(combo_keys)
        self._fired -= to_remove

    def start(self):
        """Start listening for hotkeys (blocking)."""
        if not self._combos:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        self._listener.join()

    def start_nonblocking(self):
        """Start listening for hotkeys (non-blocking daemon thread)."""
        if not self._combos:
            return
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.daemon = True
        self._listener.start()

    def stop(self):
        """Stop the hotkey listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
