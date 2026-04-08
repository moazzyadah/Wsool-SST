"""Transcription history — saves transcriptions to a local file with file locking."""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

# Module-level lock to serialize concurrent save calls within the process
_write_lock = threading.Lock()


def _history_path() -> Path:
    """Get the history file path in AppData (Windows) or ~/.config (Linux)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", "")) / "voice-to-text"
    else:
        base = Path.home() / ".config" / "voice-to-text"
    base.mkdir(parents=True, exist_ok=True)
    return base / "history.json"


def save_transcription(text: str, language: str, duration_bytes: int):
    """Append a transcription entry to the history file.

    Thread-safe: uses a lock to prevent concurrent read-modify-write corruption.

    Args:
        text: The transcribed text.
        language: Language code used ("ar", "en", "auto").
        duration_bytes: Size of the WAV file in bytes (rough duration indicator).
    """
    with _write_lock:
        path = _history_path()

        entries = []
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                entries = []

        entries.append({
            "text": text,
            "language": language,
            "timestamp": datetime.now().isoformat(),
            "bytes": duration_bytes,
        })

        # Keep last 500 entries max
        if len(entries) > 500:
            entries = entries[-500:]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
