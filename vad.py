"""Voice Activity Detection using Silero VAD (ONNX Runtime).

Detects when the user stops speaking (sustained silence) to auto-stop recording.
Uses ONNX Runtime for inference — no PyTorch dependency, ~30MB vs ~400MB.
Inference runs in a dedicated thread — never in the audio callback.
"""

import sys
import os
import time
import threading
import queue
import logging
import numpy as np

log = logging.getLogger("vtt")


def _get_base_path() -> str:
    """Get the base path — works both as script and frozen .exe."""
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


class SilenceDetector:
    """Monitors audio chunks and fires a callback after sustained silence.

    Audio chunks are queued from the recorder callback and processed
    in a separate inference thread to avoid blocking the audio pipeline.

    Uses Silero VAD via ONNX Runtime for lightweight, fast inference.
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
        self._chunk_queue: queue.Queue = queue.Queue(maxsize=200)
        self._inference_thread = None

        # Load Silero VAD ONNX model
        self._session, self._state, self._sr = self._load_model()

    def _load_model(self):
        """Load the Silero VAD ONNX model."""
        import onnxruntime as ort

        # Try bundled model first (frozen .exe), then pip-installed silero_vad package
        model_path = None

        # 1. Bundled model in .exe
        bundled = os.path.join(_get_base_path(), "silero_vad.onnx")
        if os.path.exists(bundled):
            model_path = bundled
            log.info(f"[VAD] Loading bundled ONNX model: {bundled}")

        # 2. From silero_vad pip package
        if model_path is None:
            try:
                import silero_vad
                pkg_dir = os.path.dirname(silero_vad.__file__)
                pkg_model = os.path.join(pkg_dir, "data", "silero_vad.onnx")
                if os.path.exists(pkg_model):
                    model_path = pkg_model
                    log.info(f"[VAD] Loading model from silero_vad package: {pkg_model}")
            except ImportError:
                pass

        # 3. From project data directory
        if model_path is None:
            local = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "silero_vad.onnx")
            if os.path.exists(local):
                model_path = local
                log.info(f"[VAD] Loading local model: {local}")

        if model_path is None:
            raise FileNotFoundError(
                "Silero VAD ONNX model not found. Install with: pip install silero-vad"
            )

        opts = ort.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = 1
        opts.log_severity_level = 3  # suppress ONNX warnings

        session = ort.InferenceSession(model_path, sess_options=opts)

        # Initial hidden state: (2, 1, 64) for Silero VAD v4/v5
        state = np.zeros((2, 1, 64), dtype=np.float32)
        sr = np.array(16000, dtype=np.int64)

        return session, state, sr

    def _reset_state(self):
        """Reset the ONNX model hidden state."""
        self._state = np.zeros((2, 1, 64), dtype=np.float32)

    def start(self):
        """Reset and activate the detector."""
        self._last_speech_time = time.monotonic()
        self._active = True
        self._reset_state()

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
                break
            self._process_chunk_inference(chunk)

    def _process_chunk_inference(self, chunk: np.ndarray):
        """Run VAD inference on a single chunk (runs in inference thread)."""
        # Convert int16 to float32 [-1, 1]
        audio_float = chunk.astype(np.float32).flatten() / 32768.0

        # Silero VAD expects 512 samples at 16kHz (32ms windows)
        window_size = 512
        is_speech = False

        for i in range(0, len(audio_float), window_size):
            window = audio_float[i:i + window_size]
            if len(window) < window_size:
                # Pad short windows
                window = np.pad(window, (0, window_size - len(window)))

            # ONNX inference: input shape (1, window_size)
            input_data = window.reshape(1, -1).astype(np.float32)

            ort_inputs = {
                "input": input_data,
                "state": self._state,
                "sr": self._sr,
            }

            out, self._state = self._session.run(None, ort_inputs)
            prob = out.item()

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
