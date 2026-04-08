"""Configuration management — loads from .env and config file."""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv


def _app_dir() -> Path:
    """Get the application directory — works both as script and frozen .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# Default config
DEFAULTS = {
    "language": "auto",           # "auto", "ar", "en"
    "hotkey_record": "ctrl+alt+space",
    "hotkey_language": "ctrl+alt+l",
    "silence_duration": 2.0,      # seconds
    "speech_threshold": 0.5,      # VAD sensitivity (0-1)
    "max_recording_duration": 120, # seconds
    "save_history": True,         # save transcriptions to history.json
}

# Config file location: %APPDATA%/voice-to-text/config.json (Windows)
# or ~/.config/voice-to-text/config.json (Linux)
if os.name == "nt":
    CONFIG_DIR = Path(os.environ.get("APPDATA", "")) / "voice-to-text"
else:
    CONFIG_DIR = Path.home() / ".config" / "voice-to-text"

CONFIG_FILE = CONFIG_DIR / "config.json"


class Config:
    """App configuration — merges .env + config.json + defaults."""

    def __init__(self, env_path: str = None):
        if env_path:
            load_dotenv(env_path)
        else:
            # Load .env from app directory (works as script or frozen .exe)
            load_dotenv(_app_dir() / ".env")
            # Also check AppData for .env written by installer
            if os.name == "nt":
                load_dotenv(CONFIG_DIR / ".env", override=False)

        # API keys from environment
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")

        # Load saved config or use defaults
        self._settings = dict(DEFAULTS)
        self._load_config_file()

    def _load_config_file(self):
        """Load config.json if it exists."""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._settings.update(saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        """Persist current settings to config.json."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self._settings, f, indent=2)

    def get(self, key: str):
        return self._settings.get(key, DEFAULTS.get(key))

    def set(self, key: str, value):
        self._settings[key] = value

    @property
    def language(self) -> str:
        return self._settings["language"]

    @language.setter
    def language(self, lang: str):
        self._settings["language"] = lang

    @property
    def hotkey_record(self) -> str:
        return self._settings["hotkey_record"]

    @property
    def hotkey_language(self) -> str:
        return self._settings["hotkey_language"]

    @property
    def silence_duration(self) -> float:
        return self._settings["silence_duration"]

    @property
    def speech_threshold(self) -> float:
        return self._settings["speech_threshold"]

    @property
    def max_recording_duration(self) -> float:
        return self._settings["max_recording_duration"]

    @property
    def save_history(self) -> bool:
        return self._settings.get("save_history", True)

    @save_history.setter
    def save_history(self, value: bool):
        self._settings["save_history"] = value

    def get_api_key(self) -> str:
        """Get the primary (Groq) API key."""
        return self.groq_api_key

    def get_gemini_api_key(self) -> str:
        """Get the Gemini API key."""
        return self.gemini_api_key

    def get_openai_api_key(self) -> str:
        """Get the OpenAI API key."""
        return self.openai_api_key

    def has_any_api_key(self) -> bool:
        """Check if at least one STT provider key is configured."""
        return bool(self.groq_api_key or self.gemini_api_key or self.openai_api_key)
