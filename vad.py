"""Voice Activity Detection using Silero VAD.

Detects when the user stops speaking (sustained silence)
to auto-stop recording.

Inference runs in a dedicated thread — never in the audio callback.
"""

import time
import threading
import queue
import logging
import torch
import numpy as np

log = logging.getLogger("vtt")


class SilenceDetector:
    """Monitors audio chunks and fires a callback after sustained silence.

    Audio chunks are queued from the recorder callback and processed
    in a separate inference thread to avoid blocking the audio pipeline.

    Usage:
        detector = SilenceDetector(on_silence=my_stop_fn, silence_duration=2.0)
        detector.start()
        # Feed audio chunks from the recorder callback:
        detector.process_chunk(np_array_int16)
        detector.stop()
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
        self._chunk_queue: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=200)
        self._inference_thread: threading.Thread | None = None

        # Load Silero VAD model — pinned version, no remote code execution
        self._model, self._utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            trust_repo=False,
        )

    def start(self):
        """Reset and activate the detector."""
        self._last_speech_time = time.monotonic()
        self._active = True
        self._model.reset_states()

        # Drain any leftover chunks
        while not self._chunk_queue.empty():
            try:
                self._chunk_queue.get_nowait()
            except queue.Empty:
                break

        # Start inference thread
        self._inference_thread = threading.Thread(target=self._inference_loop, daemon=True)
        self._inference_thread.start()

    def stop(self):
        """Deactivate the detector and stop inference thread."""
        self._active = False
        # Signal inference thread to exit
        try:
            self._chunk_queue.put_nowait(None)
        except queue.Full:
            pass

    def process_chunk(self, chunk: np.ndarray):
        """Queue an audio chunk for VAD processing.

        Called from the audio callback — must be fast and non-blocking.

        Args:
            chunk: numpy int16 array, 16kHz mono.
        """
        if not self._active:
            return

        try:
            self._chunk_queue.put_nowait(chunk.copy())
        except queue.Full:
            pass  # Drop chunk rather than block audio callback

    def _inference_loop(self):
        """Process queued audio chunks in a dedicated thread."""
        while self._active:
            try:
                chunk = self._chunk_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if chunk is None:
                break  # Shutdown signal

            self._process_chunk_inference(chunk)

    def _process_chunk_inference(self, chunk: np.ndarray):
        """Run VAD inference on a single chunk (runs in inference thread)."""
        # Convert int16 to float32 [-1, 1] for Silero
        audio_float = chunk.astype(np.float32).flatten() / 32768.0
        tensor = torch.from_numpy(audio_float)

        # Silero VAD expects 512 samples at 16kHz (32ms)
        window_size = 512
        is_speech = False

        for i in range(0, len(tensor), window_size):
            window = tensor[i:i + window_size]
            if len(window) < window_size:
                window = torch.nn.functional.pad(window, (0, window_size - len(window)))
            prob = self._model(window, 16000).item()
            if prob >= self._speech_threshold:
                is_speech = True
                break

        now = time.monotonic()
        if is_speech:
            self._last_speech_time = now
        elif self._last_speech_time and (now - self._last_speech_time) >= self._silence_duration:
            self._active = False
            if self._on_silence is not None:
                threading.Thread(target=self._on_silence, daemon=True).start()
