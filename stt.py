"""Speech-to-Text — multi-provider with automatic fallback.

Supported providers: Groq Whisper, Google Gemini, OpenAI Whisper.
Falls back through available providers on any error.
"""

import logging
import base64
import httpx

log = logging.getLogger("vtt")


class MultiProviderSTT:
    """Transcribe audio using multiple providers with automatic fallback.

    Provider priority: Groq → Gemini → OpenAI (only uses providers with valid keys).
    Falls back on ANY error (rate limits, network failures, 5xx, timeouts).
    """

    GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions"

    def __init__(self, groq_key: str = "", gemini_key: str = "", openai_key: str = ""):
        self._providers = []
        if groq_key:
            self._providers.append(("Groq", lambda wav, lang: self._transcribe_groq(wav, lang, groq_key)))
        if gemini_key:
            self._providers.append(("Gemini", lambda wav, lang: self._transcribe_gemini(wav, lang, gemini_key)))
        if openai_key:
            self._providers.append(("OpenAI", lambda wav, lang: self._transcribe_openai(wav, lang, openai_key)))

    @property
    def available_providers(self) -> list[str]:
        return [name for name, _ in self._providers]

    @property
    def primary_provider(self) -> str:
        return self._providers[0][0] if self._providers else "None"

    def transcribe(self, wav_bytes: bytes, language: str = "auto") -> str:
        """Transcribe audio — tries each available provider in order.

        Args:
            wav_bytes: WAV file as bytes.
            language: "ar", "en", or "auto".

        Returns:
            Transcribed text string.

        Raises:
            RuntimeError: If all providers fail.
        """
        if not wav_bytes:
            return ""

        if not self._providers:
            raise RuntimeError("No STT providers configured. Set at least one API key in .env")

        last_error = None
        for name, transcribe_fn in self._providers:
            try:
                text = transcribe_fn(wav_bytes, language)
                log.info(f"[STT] Provider: {name}")
                return text
            except Exception as e:
                log.warning(f"[STT] {name} failed: {e} — trying next provider...")
                last_error = e

        raise RuntimeError(f"All STT providers failed. Last error: {last_error}")

    @staticmethod
    def _transcribe_groq(wav_bytes: bytes, language: str, api_key: str) -> str:
        """Send audio to Groq Whisper API."""
        data = {
            "model": "whisper-large-v3",
            "response_format": "text",
        }
        if language != "auto":
            data["language"] = language

        response = httpx.post(
            MultiProviderSTT.GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files={"file": ("recording.wav", wav_bytes, "audio/wav")},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.text.strip()

    @staticmethod
    def _transcribe_gemini(wav_bytes: bytes, language: str, api_key: str) -> str:
        """Send audio to Gemini 2.0 Flash API."""
        audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")

        lang_hint = ""
        if language == "ar":
            lang_hint = " Respond in Arabic."
        elif language == "en":
            lang_hint = " Respond in English."

        payload = {
            "contents": [{
                "parts": [
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": audio_b64,
                        }
                    },
                    {
                        "text": f"Transcribe the speech in this audio exactly as spoken, no explanations.{lang_hint}"
                    }
                ]
            }]
        }

        response = httpx.post(
            MultiProviderSTT.GEMINI_URL,
            params={"key": api_key},
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()

    @staticmethod
    def _transcribe_openai(wav_bytes: bytes, language: str, api_key: str) -> str:
        """Send audio to OpenAI Whisper API."""
        data = {
            "model": "whisper-1",
            "response_format": "text",
        }
        if language != "auto":
            data["language"] = language

        response = httpx.post(
            MultiProviderSTT.OPENAI_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            data=data,
            files={"file": ("recording.wav", wav_bytes, "audio/wav")},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.text.strip()
