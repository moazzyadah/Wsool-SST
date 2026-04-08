"""Main application — wires recorder, VAD, STT, hotkeys, and tray together."""

import sys
import os
import logging
import threading
import time
from pathlib import Path

from config import Config
from recorder import AudioRecorder
from vad import SilenceDetector
from stt import MultiProviderSTT
from hotkeys import HotkeyManager
from paster import paste_text
from tray import TrayIcon
from history import save_transcription


def setup_logging():
    """Log to file when running without console (pythonw.exe)."""
    log_dir = Path(__file__).parent
    log_file = log_dir / "voice-to-text.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return logging.getLogger("vtt")


log = setup_logging()


class VoiceToTextApp:
    """Universal Voice-to-Text application."""

    def __init__(self):
        # Prevent multiple instances
        self._lock_file = self._acquire_lock()

        self._config = Config()
        self._validate_config()

        self._stt = MultiProviderSTT(
            groq_key=self._config.get_api_key(),
            gemini_key=self._config.get_gemini_api_key(),
            openai_key=self._config.get_openai_api_key(),
        )
        self._tray = TrayIcon(
            on_quit=self._quit,
            on_toggle_language=self._on_language_changed,
        )
        self._tray.language = self._config.language

        self._vad = SilenceDetector(
            on_silence=self._on_silence_detected,
            silence_duration=self._config.silence_duration,
            speech_threshold=self._config.speech_threshold,
        )

        self._recorder = AudioRecorder(on_audio_chunk=self._vad.process_chunk)

        self._hotkeys = HotkeyManager()
        self._hotkeys.register(self._config.hotkey_record, self._toggle_recording)
        self._hotkeys.register(self._config.hotkey_language, self._cycle_language)

        self._recording_lock = threading.Lock()
        self._max_timer = None
        self._running = True

        # Continuous mode state
        self._continuous_mode = False
        self._last_hotkey_time = 0.0
        self._double_press_threshold = 0.4  # seconds
        self._mouse_listener = None

    def _acquire_lock(self):
        """Prevent multiple instances from running."""
        lock_path = Path(__file__).parent / ".running.lock"
        try:
            if os.name == "nt":
                import msvcrt
                f = open(lock_path, "w")
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                return f
            else:
                import fcntl
                f = open(lock_path, "w")
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return f
        except (OSError, IOError):
            log.error("Voice-to-Text is already running!")
            sys.exit(0)

    def _validate_config(self):
        """Check that at least one STT provider API key is present."""
        if not self._config.has_any_api_key():
            log.error("No STT API key found. Set GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY in .env file.")
            sys.exit(1)

    def _toggle_recording(self):
        """Called when record hotkey is pressed.

        Single press → record once.
        Double press (within 0.4s) → enter/exit continuous mode.
        """
        now = time.time()
        delta = now - self._last_hotkey_time
        self._last_hotkey_time = now

        if delta < self._double_press_threshold:
            # Double press detected
            if self._continuous_mode:
                self._exit_continuous_mode()
            else:
                self._enter_continuous_mode()
            return

        # Single press
        if self._continuous_mode:
            self._exit_continuous_mode()
            return

        with self._recording_lock:
            if self._recorder.is_recording:
                self._stop_and_transcribe()
            else:
                self._start_recording()

    def _enter_continuous_mode(self):
        """Enter continuous dictation mode."""
        self._continuous_mode = True
        log.info("[MODE] Continuous mode ON — move mouse to exit")
        self._tray.set_state("continuous")
        self._tray.set_tooltip("Wsool STT — Continuous Mode (move mouse to exit)")
        self._start_mouse_exit_listener()
        with self._recording_lock:
            if not self._recorder.is_recording:
                self._start_recording()

    def _exit_continuous_mode(self):
        """Exit continuous dictation mode."""
        self._continuous_mode = False
        log.info("[MODE] Continuous mode OFF")
        self._tray.set_tooltip(None)
        self._stop_mouse_exit_listener()
        with self._recording_lock:
            if self._recorder.is_recording:
                self._stop_and_transcribe()

    def _start_mouse_exit_listener(self):
        """Watch for mouse movement to exit continuous mode."""
        from pynput import mouse as pynput_mouse
        import ctypes

        # Get current mouse position
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        self._mouse_origin = (pt.x, pt.y)
        self._mouse_move_threshold = 80  # pixels

        def on_move(x, y):
            if not self._continuous_mode:
                return False  # stop listener
            ox, oy = self._mouse_origin
            if abs(x - ox) > self._mouse_move_threshold or abs(y - oy) > self._mouse_move_threshold:
                log.info("[MODE] Mouse moved — exiting continuous mode")
                threading.Thread(target=self._exit_continuous_mode, daemon=True).start()
                return False  # stop listener

        self._mouse_listener = pynput_mouse.Listener(on_move=on_move)
        self._mouse_listener.daemon = True
        self._mouse_listener.start()

    def _stop_mouse_exit_listener(self):
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
            self._mouse_listener = None

    def _start_recording(self):
        """Start recording audio."""
        self._tray.set_state("recording")
        self._vad.start()

        try:
            self._recorder.start()
        except Exception as e:
            log.error(f"[MIC] Failed to start microphone: {e}")
            self._vad.stop()
            self._tray.set_state("idle")
            return

        # Safety: max recording duration timer
        max_dur = self._config.max_recording_duration
        self._max_timer = threading.Timer(max_dur, self._on_max_duration)
        self._max_timer.daemon = True
        self._max_timer.start()

        log.info("[REC] Recording started...")

    def _stop_and_transcribe(self):
        """Stop recording and send to STT."""
        if self._max_timer:
            self._max_timer.cancel()
            self._max_timer = None

        self._vad.stop()
        wav_bytes = self._recorder.stop()

        # No beep on stop — text appearing is the signal

        if not wav_bytes or len(wav_bytes) < 1000:
            log.info("[SKIP] Recording too short, ignoring.")
            self._tray.set_state("idle")
            return

        self._tray.set_state("processing")
        log.info("[STT] Transcribing...")
        thread = threading.Thread(target=self._do_transcribe, args=(wav_bytes,), daemon=True)
        thread.start()

    def _do_transcribe(self, wav_bytes: bytes):
        """Run STT and paste result (runs in background thread)."""
        try:
            log.info(f"[STT] Sending {len(wav_bytes)} bytes for transcription...")
            text = self._stt.transcribe(wav_bytes, language=self._tray.language)
            if text:
                log.info(f"[OK] {text}")
                paste_text(text)
                if self._config.save_history:
                    save_transcription(text, self._tray.language, len(wav_bytes))
            else:
                log.info("[EMPTY] No speech detected.")
        except Exception as e:
            log.error(f"[ERROR] Transcription failed: {e}", exc_info=True)
        finally:
            self._tray.set_state("idle")

    def _on_silence_detected(self):
        """Called by VAD when silence exceeds threshold."""
        log.info("[VAD] Silence detected — auto-stopping.")
        with self._recording_lock:
            if self._recorder.is_recording:
                self._stop_and_transcribe()
                if self._continuous_mode:
                    # Restart recording automatically after transcription
                    threading.Timer(0.3, self._continuous_restart).start()

    def _continuous_restart(self):
        """Restart recording in continuous mode after transcription."""
        if not self._continuous_mode:
            return
        with self._recording_lock:
            if not self._recorder.is_recording:
                self._start_recording()
                log.info("[MODE] Continuous — listening again...")

    def _on_max_duration(self):
        """Called when max recording duration is reached."""
        log.info("[MAX] Max duration reached — stopping.")
        with self._recording_lock:
            if self._recorder.is_recording:
                self._stop_and_transcribe()

    def _cycle_language(self):
        """Called when language hotkey is pressed."""
        cycle = ["auto", "ar", "en"]
        current = self._tray.language
        idx = cycle.index(current) if current in cycle else 0
        new_lang = cycle[(idx + 1) % len(cycle)]
        self._tray.language = new_lang
        self._config.language = new_lang
        labels = {"auto": "Auto-detect", "ar": "Arabic عربي", "en": "English"}
        log.info(f"[LANG] Switched to: {labels.get(new_lang, new_lang)}")

    def _on_language_changed(self, language: str):
        """Called when language is changed from tray menu."""
        self._config.language = language
        labels = {"auto": "Auto-detect", "ar": "Arabic عربي", "en": "English"}
        log.info(f"[LANG] Switched to: {labels.get(language, language)}")

    def _quit(self):
        """Graceful shutdown."""
        log.info("[EXIT] Shutting down...")
        self._running = False
        self._hotkeys.stop()
        if self._recorder.is_recording:
            self._recorder.stop()
        self._config.save()
        if self._lock_file:
            self._lock_file.close()

    def run(self):
        """Start the application."""
        log.info("=" * 50)
        log.info("  Voice-to-Text — Universal Dictation Tool")
        log.info("=" * 50)
        log.info(f"  Record:    {self._config.hotkey_record}")
        log.info(f"  Language:  {self._config.hotkey_language}")
        log.info(f"  Provider:  {self._stt.primary_provider} (available: {', '.join(self._stt.available_providers)})")
        log.info(f"  Language:  {self._config.language}")
        log.info(f"  Silence:   {self._config.silence_duration}s auto-stop")
        log.info("=" * 50)

        # Start tray icon
        self._tray.start()

        # Start hotkey listener in background
        self._hotkeys.start_nonblocking()

        # Keep main thread alive
        try:
            while self._running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            self._quit()


def main():
    try:
        app = VoiceToTextApp()
        app.run()
    except Exception as e:
        log.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
