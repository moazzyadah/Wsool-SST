"""Audio feedback — beep sounds for start/stop recording."""

import struct
import wave
import io
import tempfile
import os
import threading

# Try playsound3, fallback to winsound on Windows
_play_fn = None


def _init_player():
    """Initialize the audio player — try playsound3, then winsound."""
    global _play_fn
    if _play_fn is not None:
        return

    try:
        from playsound3 import playsound
        _play_fn = playsound
        return
    except ImportError:
        pass

    try:
        import winsound
        _play_fn = lambda path: winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return
    except ImportError:
        pass

    # No audio available — silent fallback
    _play_fn = lambda path: None


def _generate_beep_wav(frequency: int, duration_ms: int, volume: float = 0.5) -> str:
    """Generate a beep WAV file and return its path.

    Args:
        frequency: Tone frequency in Hz.
        duration_ms: Duration in milliseconds.
        volume: 0.0 to 1.0.

    Returns:
        Path to temporary WAV file.
    """
    sample_rate = 16000
    n_samples = int(sample_rate * duration_ms / 1000)
    amplitude = int(32767 * volume)

    samples = []
    import math
    for i in range(n_samples):
        t = i / sample_rate
        value = int(amplitude * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", value))

    raw = b"".join(samples)
    tmp = os.path.join(tempfile.gettempdir(), f"vtt_beep_{frequency}_{duration_ms}.wav")

    with wave.open(tmp, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)

    return tmp


# Pre-generate beep file paths (created on first use)
_start_beep_path = None
_stop_beep_path = None


def _play_async(path: str):
    """Play audio file in a background thread to avoid blocking."""
    threading.Thread(target=_play_fn, args=(path,), daemon=True).start()


def beep_start():
    """Play a short high beep to indicate recording started."""
    global _start_beep_path
    _init_player()
    if _start_beep_path is None:
        _start_beep_path = _generate_beep_wav(880, 150, 0.4)  # A5, short
    _play_async(_start_beep_path)


def beep_stop():
    """Play a low double-beep to indicate recording stopped."""
    global _stop_beep_path
    _init_player()
    if _stop_beep_path is None:
        _stop_beep_path = _generate_beep_wav(440, 200, 0.3)  # A4, slightly longer
    _play_async(_stop_beep_path)
