# 🎙 Wsool STT

**Universal speech-to-text for Windows** — press a hotkey, speak, and text appears wherever your cursor is.

> Supports Groq · Gemini · OpenAI · Local models

---

🇸🇦 **هل تتحدث العربية؟** ويندوز لا يدعم التعرف على الصوت باللغة العربية — هذا البرنامج يحل تلك المشكلة.
[اقرأ التوثيق بالعربية ←](README.ar.md)

---

## 🤔 Why does this exist?

**Windows speech recognition doesn't support Arabic.**

The built-in Windows STT and most dictation tools are English-only. If you write in Arabic — or switch between Arabic and English constantly — you're stuck typing manually.

Wsool STT was built to fix that. It uses state-of-the-art AI models (Whisper, Gemini) that handle Arabic natively, and pastes the result directly into any app — browsers, Office, chat apps, IDEs, everything.

---

## ✨ Features

- **Works everywhere** — any app, any text field
- **Arabic & English** — auto-detect or manual switch
- **Auto-stop** — silence detection stops recording automatically
- **Continuous mode** — double-press hotkey to dictate non-stop
- **Multiple providers** — switch between Groq, Gemini, OpenAI
- **Free tier friendly** — auto-fallback when rate limit is hit
- **Runs silently** — lives in the system tray, no terminal needed

---

## 🚀 Quick Start

### 1. Get a free API key

| Provider | Free Tier | Speed | Link |
|----------|-----------|-------|------|
| **Groq** | 7,200 sec/day | Fastest | [console.groq.com](https://console.groq.com/keys) |
| **Google Gemini** | 1,500 req/day | Fast | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **OpenAI** | Paid | Fast | [platform.openai.com](https://platform.openai.com/api-keys) |

### 2. Install

```bash
git clone https://github.com/moazzyadah/Wsool-SST.git
cd Wsool-SST
install.bat
```

### 3. Add your API key

Copy `.env.example` to `.env` and add your key:

```env
GROQ_API_KEY=your_key_here
# or
GEMINI_API_KEY=your_key_here
```

### 4. Run

```
run.bat          # with console (for testing)
run_silent.vbs   # background, no window
startup.bat      # add to Windows startup
```

---

## ⌨️ Hotkeys

| Shortcut | Action |
|----------|--------|
| `Ctrl+Alt+Space` | Start / Stop recording |
| `Ctrl+Alt+Space` × 2 | Toggle continuous mode |
| `Ctrl+Alt+L` | Switch language (Auto → AR → EN) |
| Right-click tray | Language · Quit |

### Continuous Mode
Double-press `Ctrl+Alt+Space` → dictate non-stop. Every silence auto-transcribes and starts listening again. Move your mouse to exit.

---

## 🛠 Setup Wizard (GUI)

Run the interactive installer:

```
venv\Scripts\python.exe installer.py
```

Guides you through provider selection, API key testing, language, and hotkey customization.

---

## 📁 Project Structure

```
app.py          # Main — wires everything together
recorder.py     # Audio recording (sounddevice, 16kHz mono)
vad.py          # Silero VAD — auto-stop after silence
stt.py          # Groq Whisper + Gemini fallback
hotkeys.py      # Global hotkeys (pynput)
paster.py       # Paste via Win32 SendInput
tray.py         # System tray icon (gray/red blink/orange blink)
sounds.py       # Audio feedback
config.py       # Settings (.env + config.json)
history.py      # Last 500 transcriptions
installer.py    # GUI setup wizard (customtkinter)
```

---

## ⚙️ Configuration

Settings are saved to `%APPDATA%\voice-to-text\config.json`.

| Key | Default | Description |
|-----|---------|-------------|
| `language` | `auto` | `auto` / `ar` / `en` |
| `hotkey_record` | `ctrl+alt+space` | Record hotkey |
| `hotkey_language` | `ctrl+alt+l` | Language switch hotkey |
| `silence_duration` | `2.0` | Seconds of silence before auto-stop |
| `speech_threshold` | `0.5` | VAD sensitivity (0–1) |
| `max_recording_duration` | `120` | Max seconds per recording |

---

## 🔑 Environment Variables

```env
GROQ_API_KEY=       # Groq Whisper API
GEMINI_API_KEY=     # Google Gemini (fallback)
OPENAI_API_KEY=     # OpenAI Whisper (optional)
```

---

## 📋 Requirements

- Windows 10/11
- Python 3.10+
- Microphone

---

## 📄 License

MIT — free to use, modify, and distribute.

---

<p align="center">Made with ❤️ by <a href="https://wsool.ai">wsool.ai</a></p>
