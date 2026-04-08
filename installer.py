"""Voice-to-Text Installer — Setup Wizard."""

import os
import sys
import json
import subprocess
import threading
import winreg
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageDraw

# ── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_DIR = Path(__file__).parent
VENV_PYTHON = APP_DIR / "venv" / "Scripts" / "pythonw.exe"
STARTUP_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WsoolSTT"

PROVIDERS = {
    "Groq (Whisper — Fastest)": {
        "env_key": "GROQ_API_KEY",
        "url": "https://console.groq.com/keys",
        "placeholder": "gsk_...",
        "model": "whisper-large-v3",
    },
    "Google Gemini (Flash — Free)": {
        "env_key": "GEMINI_API_KEY",
        "url": "https://aistudio.google.com/app/apikey",
        "placeholder": "AIza...",
        "model": "gemini-2.0-flash",
    },
    "OpenAI (Whisper)": {
        "env_key": "OPENAI_API_KEY",
        "url": "https://platform.openai.com/api-keys",
        "placeholder": "sk-...",
        "model": "whisper-1",
    },
}

LANGUAGES = {
    "Auto-detect": "auto",
    "Arabic  عربي": "ar",
    "English": "en",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def test_groq_key(key: str) -> bool:
    try:
        import httpx
        r = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def test_gemini_key(key: str) -> bool:
    try:
        import httpx
        r = httpx.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key}",
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def test_openai_key(key: str) -> bool:
    try:
        import httpx
        r = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=8,
        )
        return r.status_code == 200
    except Exception:
        return False


def test_key(provider_name: str, key: str) -> bool:
    if "Groq" in provider_name:
        return test_groq_key(key)
    elif "Gemini" in provider_name:
        return test_gemini_key(key)
    elif "OpenAI" in provider_name:
        return test_openai_key(key)
    return False


def save_env(provider_name: str, api_key: str):
    """Write API key to .env file."""
    env_key = PROVIDERS[provider_name]["env_key"]
    env_path = APP_DIR / ".env"

    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{env_key}="):
            lines[i] = f"{env_key}={api_key}"
            updated = True

    if not updated:
        lines.append(f"{env_key}={api_key}")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_config(language: str, provider_name: str, hotkey_record: str, hotkey_language: str):
    """Write config.json."""
    config_dir = Path(os.environ.get("APPDATA", "")) / "voice-to-text"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.json"

    config = {}
    if config_file.exists():
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    config["language"] = language
    config["provider"] = provider_name
    config["hotkey_record"] = hotkey_record or "ctrl+alt+space"
    config["hotkey_language"] = hotkey_language or "ctrl+alt+l"
    config_file.write_text(json.dumps(config, indent=2), encoding="utf-8")


def add_to_startup():
    """Add app to Windows startup registry."""
    try:
        vbs = APP_DIR / "run_silent.vbs"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'wscript.exe "{vbs}"')
        return True
    except Exception:
        return False


def remove_from_startup():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except Exception:
        pass


# ── Wizard ────────────────────────────────────────────────────────────────────

class InstallerWizard(ctk.CTk):

    STEPS = ["Welcome", "Provider", "API Key", "Language", "Hotkeys", "Install", "Done"]

    def __init__(self):
        super().__init__()
        self.title("Wsool STT — Setup Wizard")
        self.geometry("580x460")
        self.resizable(False, False)

        # State
        self._step = 0
        self._provider = ctk.StringVar(value=list(PROVIDERS.keys())[0])
        self._api_key = ctk.StringVar()
        self._language = ctk.StringVar(value=list(LANGUAGES.keys())[0])
        self._startup = ctk.BooleanVar(value=True)
        self._key_valid = False
        self._hotkey_record = ctk.StringVar(value="ctrl+alt+space")
        self._hotkey_language = ctk.StringVar(value="ctrl+alt+l")

        # Layout
        self._build_header()
        self._build_progress()
        self._content = ctk.CTkFrame(self, fg_color="transparent")
        self._content.pack(fill="both", expand=True, padx=30, pady=(0, 10))
        self._build_footer()

        self._show_step(0)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = ctk.CTkFrame(self, height=70, fg_color="#1a1a2e", corner_radius=0)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="🎙  Wsool STT",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="#4fc3f7",
        ).pack(side="left", padx=20)
        self._subtitle = ctk.CTkLabel(
            hdr,
            text="Setup Wizard",
            font=ctk.CTkFont(size=13),
            text_color="#aaaaaa",
        )
        self._subtitle.pack(side="left", padx=4)

    # ── Progress bar ──────────────────────────────────────────────────────────

    def _build_progress(self):
        bar_frame = ctk.CTkFrame(self, height=6, fg_color="#2a2a3e", corner_radius=0)
        bar_frame.pack(fill="x")
        bar_frame.pack_propagate(False)
        self._progress = ctk.CTkProgressBar(bar_frame, height=6, corner_radius=0)
        self._progress.pack(fill="x")
        self._progress.set(0)

    def _update_progress(self):
        self._progress.set(self._step / (len(self.STEPS) - 1))

    # ── Footer ────────────────────────────────────────────────────────────────

    def _build_footer(self):
        foot = ctk.CTkFrame(self, height=60, fg_color="#111122", corner_radius=0)
        foot.pack(fill="x", side="bottom")
        foot.pack_propagate(False)

        self._btn_back = ctk.CTkButton(
            foot, text="← Back", width=100, fg_color="#333355",
            hover_color="#444477", command=self._back,
        )
        self._btn_back.pack(side="left", padx=20, pady=12)

        self._btn_next = ctk.CTkButton(
            foot, text="Next →", width=120, command=self._next,
        )
        self._btn_next.pack(side="right", padx=20, pady=12)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _next(self):
        if self._step == 2:  # API key step — validate first
            self._validate_key()
            return
        self._step = min(self._step + 1, len(self.STEPS) - 1)
        self._show_step(self._step)

    def _back(self):
        self._step = max(self._step - 1, 0)
        self._show_step(self._step)

    # ── Steps ─────────────────────────────────────────────────────────────────

    def _show_step(self, step: int):
        self._update_progress()
        for w in self._content.winfo_children():
            w.destroy()

        self._btn_back.configure(state="normal" if step > 0 else "disabled")
        self._btn_next.configure(state="normal", text="Next →")

        builders = [
            self._step_welcome,
            self._step_provider,
            self._step_apikey,
            self._step_language,
            self._step_hotkeys,
            self._step_install,
            self._step_done,
        ]
        builders[step]()

    # Step 0 — Welcome
    def _step_welcome(self):
        self._subtitle.configure(text="Welcome")
        f = self._content
        ctk.CTkLabel(f, text="Welcome to Wsool STT! 👋", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(30, 10))
        ctk.CTkLabel(
            f,
            text=(
                "This wizard will set up Wsool STT on your computer.\n\n"
                "Press a hotkey → speak → text appears wherever your cursor is.\n\n"
                "You'll need a free API key from one of the supported providers.\n"
                "The setup takes less than 2 minutes."
            ),
            font=ctk.CTkFont(size=13),
            text_color="#cccccc",
            justify="center",
        ).pack(pady=10)

    # Step 1 — Provider
    def _step_provider(self):
        self._subtitle.configure(text="Choose Provider")
        f = self._content
        ctk.CTkLabel(f, text="Choose your STT provider", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(
            f, text="All providers have a free tier. Groq is the fastest.",
            font=ctk.CTkFont(size=12), text_color="#aaaaaa",
        ).pack(pady=(0, 15))

        for name, info in PROVIDERS.items():
            row = ctk.CTkFrame(f, fg_color="#1e1e2e", corner_radius=10)
            row.pack(fill="x", pady=4)
            ctk.CTkRadioButton(
                row, text=name, variable=self._provider, value=name,
                font=ctk.CTkFont(size=13),
            ).pack(side="left", padx=15, pady=12)

    # Step 2 — API Key
    def _step_apikey(self):
        self._subtitle.configure(text="Enter API Key")
        f = self._content
        provider = self._provider.get()
        info = PROVIDERS[provider]

        ctk.CTkLabel(f, text="Enter your API Key", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))

        link_frame = ctk.CTkFrame(f, fg_color="transparent")
        link_frame.pack()
        ctk.CTkLabel(link_frame, text="Get a free key at:", font=ctk.CTkFont(size=12), text_color="#aaaaaa").pack(side="left")
        ctk.CTkLabel(
            link_frame, text=info["url"],
            font=ctk.CTkFont(size=12), text_color="#4fc3f7", cursor="hand2",
        ).pack(side="left", padx=5)

        entry = ctk.CTkEntry(
            f, textvariable=self._api_key,
            placeholder_text=info["placeholder"],
            width=400, height=42, font=ctk.CTkFont(size=13),
            show="•",
        )
        entry.pack(pady=15)

        show_var = ctk.BooleanVar(value=False)
        def toggle_show():
            entry.configure(show="" if show_var.get() else "•")
        ctk.CTkCheckBox(f, text="Show key", variable=show_var, command=toggle_show).pack()

        self._key_status = ctk.CTkLabel(f, text="", font=ctk.CTkFont(size=12))
        self._key_status.pack(pady=8)

        self._btn_next.configure(text="Test & Continue →")

    def _validate_key(self):
        key = self._api_key.get().strip()
        if not key:
            self._key_status.configure(text="Please enter your API key.", text_color="#ff6b6b")
            return

        self._key_status.configure(text="Testing connection...", text_color="#aaaaaa")
        self._btn_next.configure(state="disabled")

        def do_test():
            ok = test_key(self._provider.get(), key)
            self.after(0, lambda: self._on_test_done(ok))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_test_done(self, ok: bool):
        if ok:
            self._key_status.configure(text="✓ Connected successfully!", text_color="#69f0ae")
            self._key_valid = True
            self._step += 1
            self._show_step(self._step)
        else:
            self._key_status.configure(text="✗ Invalid key or no connection. Please check and retry.", text_color="#ff6b6b")
            self._btn_next.configure(state="normal", text="Test & Continue →")

    # Step 3 — Language
    def _step_language(self):
        self._subtitle.configure(text="Default Language")
        f = self._content
        ctk.CTkLabel(f, text="Default language", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(
            f, text="You can always change this with Ctrl+Alt+L while running.",
            font=ctk.CTkFont(size=12), text_color="#aaaaaa",
        ).pack(pady=(0, 15))

        for label in LANGUAGES:
            row = ctk.CTkFrame(f, fg_color="#1e1e2e", corner_radius=10)
            row.pack(fill="x", pady=4)
            ctk.CTkRadioButton(
                row, text=label, variable=self._language, value=label,
                font=ctk.CTkFont(size=13),
            ).pack(side="left", padx=15, pady=12)

    # Step 4 — Hotkeys
    def _step_hotkeys(self):
        self._subtitle.configure(text="Hotkeys")
        f = self._content
        ctk.CTkLabel(f, text="Customize Hotkeys", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 5))
        ctk.CTkLabel(
            f, text="Use combinations like: ctrl+alt+space  /  ctrl+shift+r  /  alt+r",
            font=ctk.CTkFont(size=11), text_color="#aaaaaa",
        ).pack(pady=(0, 15))

        for label, var, placeholder in [
            ("Record / Stop", self._hotkey_record, "ctrl+alt+space"),
            ("Switch Language", self._hotkey_language, "ctrl+alt+l"),
        ]:
            row = ctk.CTkFrame(f, fg_color="#1e1e2e", corner_radius=10)
            row.pack(fill="x", pady=6)
            ctk.CTkLabel(
                row, text=label, width=130,
                font=ctk.CTkFont(size=12), text_color="#aaaaaa", anchor="w",
            ).pack(side="left", padx=15, pady=12)
            ctk.CTkEntry(
                row, textvariable=var,
                placeholder_text=placeholder,
                width=220, height=34, font=ctk.CTkFont(size=12),
            ).pack(side="left", padx=10)

        ctk.CTkLabel(
            f, text="Leave default if unsure.",
            font=ctk.CTkFont(size=11), text_color="#666688",
        ).pack(pady=(10, 0))

    # Step 5 — Install
    def _step_install(self):
        self._subtitle.configure(text="Ready to Install")
        f = self._content
        ctk.CTkLabel(f, text="Ready to install!", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(20, 10))

        summary = ctk.CTkFrame(f, fg_color="#1e1e2e", corner_radius=10)
        summary.pack(fill="x", pady=10)

        provider = self._provider.get()
        lang = self._language.get()

        for label, value in [("Provider", provider.split("(")[0].strip()), ("Language", lang)]:
            row = ctk.CTkFrame(summary, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=4)
            ctk.CTkLabel(row, text=label + ":", width=80, font=ctk.CTkFont(size=12), text_color="#aaaaaa", anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=ctk.CTkFont(size=12, weight="bold"), anchor="w").pack(side="left")

        ctk.CTkCheckBox(
            f, text="Start automatically with Windows",
            variable=self._startup, font=ctk.CTkFont(size=13),
        ).pack(pady=15)

        self._btn_next.configure(text="Install ✓")

    # Step 5 — Done
    def _step_install_action(self):
        provider = self._provider.get()
        key = self._api_key.get().strip()
        lang_label = self._language.get()
        language = LANGUAGES[lang_label]
        startup = self._startup.get()
        hotkey_record = self._hotkey_record.get().strip()
        hotkey_language = self._hotkey_language.get().strip()

        save_env(provider, key)
        save_config(language, provider, hotkey_record, hotkey_language)

        if startup:
            add_to_startup()
        else:
            remove_from_startup()

        self._step += 1
        self._show_step(self._step)

    def _step_done(self):
        self._subtitle.configure(text="Installation Complete")
        f = self._content
        ctk.CTkLabel(f, text="🎉 All done!", font=ctk.CTkFont(size=22, weight="bold"), text_color="#69f0ae").pack(pady=(30, 10))
        ctk.CTkLabel(
            f,
            text=(
                "Voice-to-Text is ready.\n\n"
                "Ctrl+Alt+Space  →  Start / Stop recording\n"
                "Ctrl+Alt+L         →  Switch language\n\n"
                "The app will start automatically with Windows."
                if self._startup.get() else
                "Voice-to-Text is ready.\n\n"
                "Ctrl+Alt+Space  →  Start / Stop recording\n"
                "Ctrl+Alt+L         →  Switch language\n\n"
                'Run "run_silent.vbs" to start the app.'
            ),
            font=ctk.CTkFont(size=13),
            text_color="#cccccc",
            justify="center",
        ).pack(pady=10)

        self._btn_back.configure(state="disabled")
        self._btn_next.configure(text="Launch App →", command=self._launch_and_close)

    def _launch_and_close(self):
        vbs = APP_DIR / "run_silent.vbs"
        subprocess.Popen(["wscript.exe", str(vbs)], shell=False)
        self.after(500, self.destroy)

    # ── Override next for install step ────────────────────────────────────────
    def _next(self):
        if self._step == 2:
            self._validate_key()
        elif self._step == 5:
            self._step_install_action()
        else:
            self._step = min(self._step + 1, len(self.STEPS) - 1)
            self._show_step(self._step)


if __name__ == "__main__":
    app = InstallerWizard()
    app.mainloop()
