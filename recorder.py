"""Audio recorder using sounddevice — records 16kHz mono PCM."""

import io
import wave
import threading
import numpy as np
import sounddevice as sd


class AudioRecorder:
    """Records audio from the default microphone.

    Usage:
        recorder = AudioRecorder()
        recorder.start()
        # ... recording ...
        wav_bytes = recorder.stop()  # returns WAV file as bytes
    """

    SAMPLE_RATE = 16000
    CHANNELS = 1
    DTYPE = "int16"
    BLOCKSIZE = 512  # ~32ms chunks at 16kHz

    def __init__(self, on_audio_chunk=None):
        """
        Args:
            on_audio_chunk: Optional callback(np.ndarray) called for each
                audio chunk. Used by VAD to detect silence.
        """
        self._on_audio_chunk = on_audio_chunk
        self._frames: list[np.ndarray] = []
        self._stream = None
        self._recording = False
        self._lock = threading.Lock()

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start(self):
        """Start recording from the default microphone."""
        with self._lock:
            if self._recording:
                return
            self._frames = []
            self._recording = True
            self._stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype=self.DTYPE,
                blocksize=self.BLOCKSIZE,
                callback=self._audio_callback,
            )
            self._stream.start()

    def stop(self) -> bytes:
        """Stop recording and return WAV file as bytes."""
        with self._lock:
            if not self._recording:
                return b""
            self._recording = False
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            return self._build_wav()

    def _audio_callback(self, indata, frames, time_info, status):
        """Called by sounddevice for each audio chunk."""
        if not self._recording:
            return
        chunk = indata.copy()
        self._frames.append(chunk)
        if self._on_audio_chunk is not None:
            self._on_audio_chunk(chunk)

    def _build_wav(self) -> bytes:
        """Combine recorded frames into a WAV file in memory."""
        if not self._frames:
            return b""
        audio = np.concatenate(self._frames, axis=0)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()
