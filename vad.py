"""Voice Activity Detection using Silero VAD.

Detects when the user stops speaking (2 seconds of silence)
to auto-stop recording.
"""

import time
import threading
import torch
import numpy as np


class SilenceDetector:
    """Monitors audio chunks and fires a callback after sustained silence.

    Usage:
        detector = SilenceDetector(on_silence=my_stop_fn, silence_duration=2.0)
        # Feed audio chunks from the recorder:
        detector.process_chunk(np_array_int16)
    """

    def __init__(self, on_silence=None, silence_duration: float = 2.0,
                 speech_threshold: float = 0.5):
        """
        Args:
            on_silence: Callback fired when silence exceeds silence_duration.
            silence_duration: Seconds of silence before triggering stop.
            speech_threshold: Silero VAD probability threshold (0-1).
        """
        self._on_silence = on_silence
        self._silence_duration = silence_duration
        self._speech_threshold = speech_threshold
        self._last_speech_time = None
        self._active = False

        # Load Silero VAD model
        self._model, self._utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=True,
        )

    def start(self):
        """Reset and activate the detector."""
        self._last_speech_time = time.monotonic()
        self._active = True
        self._model.reset_states()

    def stop(self):
        """Deactivate the detector."""
        self._active = False

    def process_chunk(self, chunk: np.ndarray):
        """Process an audio chunk from the recorder.

        Args:
            chunk: numpy int16 array, 16kHz mono.
        """
        if not self._active:
            return

        # Convert int16 to float32 [-1, 1] for Silero
        audio_float = chunk.astype(np.float32).flatten() / 32768.0
        tensor = torch.from_numpy(audio_float)

        # Silero VAD expects 512 samples at 16kHz (32ms)
        # Process in 512-sample windows
        window_size = 512
        is_speech = False

        for i in range(0, len(tensor), window_size):
            window = tensor[i:i + window_size]
            if len(window) < window_size:
                # Pad short windows
                window = torch.nn.functional.pad(window, (0, window_size - len(window)))
            prob = self._model(window, 16000).item()
            if prob >= self._speech_threshold:
                is_speech = True
                break

        now = time.monotonic()
        if is_speech:
            self._last_speech_time = now
        elif (now - self._last_speech_time) >= self._silence_duration:
            self._active = False
            if self._on_silence is not None:
                # Fire callback in a separate thread to avoid deadlock
                # (this runs inside sounddevice's audio callback)
                threading.Thread(target=self._on_silence, daemon=True).start()
