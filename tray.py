"""System tray icon with status indicator.

All icon/menu mutations are serialized through a threading lock
to prevent cross-thread state corruption.
"""

import threading
import time
from PIL import Image, ImageDraw
import pystray


class TrayIcon:
    """System tray icon that shows recording/idle status.

    States:
        - idle (gray): Waiting for hotkey
        - recording (red): Recording audio
        - processing (yellow): Sending to STT API
        - continuous (orange): Continuous dictation mode
    """

    COLORS = {
        "idle": "#808080",
        "recording": "#FF3333",
        "processing": "#FFB800",
        "continuous": "#FF8C00",
    }

    def __init__(self, on_quit=None, on_toggle_language=None):
        self._on_quit = on_quit
        self._on_toggle_language = on_toggle_language
        self._state = "idle"
        self._language = "auto"
        self._icon = None
        self._thread = None
        self._blink_thread = None
        self._blink_active = False
        self._blink_colors = ["#FF3333", "#661111"]
        self._lock = threading.Lock()

    def _create_icon_image(self, color: str) -> Image.Image:
        """Create a simple circular icon with the given color."""
        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Outer circle
        draw.ellipse([4, 4, size - 4, size - 4], fill=color)
        # Inner microphone symbol (white rectangle)
        cx, cy = size // 2, size // 2
        draw.rectangle([cx - 6, cy - 14, cx + 6, cy + 6], fill="white")
        draw.arc([cx - 10, cy - 4, cx + 10, cy + 14], 0, 180, fill="white", width=2)
        draw.line([cx, cy + 14, cx, cy + 20], fill="white", width=2)
        return img

    def _build_menu(self):
        """Build the right-click menu."""
        lang_label = {"auto": "Auto-detect", "ar": "Arabic", "en": "English"}
        items = [
            pystray.MenuItem(
                f"Language: {lang_label.get(self._language, self._language)}",
                self._cycle_language,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        ]
        return pystray.Menu(*items)

    def _cycle_language(self):
        """Cycle through language options."""
        cycle = ["auto", "ar", "en"]
        with self._lock:
            idx = cycle.index(self._language) if self._language in cycle else 0
            self._language = cycle[(idx + 1) % len(cycle)]
            lang = self._language
        if self._on_toggle_language:
            self._on_toggle_language(lang)
        self._update_icon()

    def _quit(self):
        """Handle quit from tray menu."""
        if self._on_quit:
            self._on_quit()
        with self._lock:
            if self._icon:
                self._icon.stop()

    def _update_menu(self):
        """Rebuild the tray menu (e.g. after language change)."""
        with self._lock:
            if self._icon is not None:
                self._icon.menu = self._build_menu()

    def _update_icon(self):
        """Update the tray icon to reflect current state."""
        with self._lock:
            if self._icon is not None:
                color = self.COLORS.get(self._state, self.COLORS["idle"])
                self._icon.icon = self._create_icon_image(color)
                state_labels = {
                    "idle": "Ready",
                    "recording": "Recording...",
                    "processing": "Transcribing...",
                    "continuous": "Continuous Mode",
                }
                lang_label = {"auto": "Auto", "ar": "AR", "en": "EN"}.get(self._language, "?")
                self._icon.title = f"Wsool STT [{lang_label}] — {state_labels.get(self._state, '')}"

    @property
    def language(self) -> str:
        with self._lock:
            return self._language

    @language.setter
    def language(self, lang: str):
        with self._lock:
            self._language = lang
        self._update_menu()
        self._update_icon()

    def set_state(self, state: str):
        """Set tray state: 'idle', 'recording', 'processing', or 'continuous'."""
        with self._lock:
            self._state = state
        if state == "recording":
            self._start_blink(["#FF3333", "#661111"])
        elif state == "continuous":
            self._start_blink(["#FF8C00", "#663300"])
        else:
            self._stop_blink()
            self._update_icon()

    def _start_blink(self, colors: list):
        """Start blinking the tray icon between two colors."""
        self._stop_blink()
        self._blink_active = True
        self._blink_colors = colors
        self._blink_thread = threading.Thread(target=self._blink_loop, daemon=True)
        self._blink_thread.start()

    def _stop_blink(self):
        """Stop blinking."""
        self._blink_active = False

    def _blink_loop(self):
        """Alternate between two colors every 0.5s."""
        colors = self._blink_colors
        i = 0
        while self._blink_active:
            with self._lock:
                if self._icon is not None:
                    self._icon.icon = self._create_icon_image(colors[i % 2])
            i += 1
            time.sleep(0.5)

    def start(self):
        """Start the tray icon in a background thread."""
        color = self.COLORS["idle"]
        self._icon = pystray.Icon(
            name="wsool-stt",
            icon=self._create_icon_image(color),
            title="Wsool STT [Auto] — Ready",
            menu=self._build_menu(),
        )

        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def set_tooltip(self, text: str | None):
        """Override tray tooltip. Pass None to reset to default."""
        with self._lock:
            if self._icon:
                if text:
                    self._icon.title = text
                else:
                    pass  # Will be reset by next _update_icon call
        if not text:
            self._update_icon()

    def stop(self):
        """Stop the tray icon."""
        self._stop_blink()
        with self._lock:
            if self._icon:
                self._icon.stop()
