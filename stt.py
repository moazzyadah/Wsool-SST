"""Speech-to-Text — Groq Whisper with Gemini fallback."""

import logging
import base64
import httpx

log = logging.getLogger("vtt")


class GroqSTT:
    """Transcribe audio using Groq Whisper, falls back to Gemini on rate limit."""

    GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
    GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

    def __init__(self, api_key: str, gemini_api_key: str = ""):
        self._api_key = api_key
        self._gemini_api_key = gemini_api_key

    def transcribe(self, wav_bytes: bytes, language: str = "auto") -> str:
        """Transcribe audio — tries Groq first, falls back to Gemini.

        Args:
            wav_bytes: WAV file as bytes.
            language: "ar", "en", or "auto".

        Returns:
            Transcribed text string.
        """
        if not wav_bytes:
            return ""

        try:
            text = self._transcribe_groq(wav_bytes, language)
            log.info("[STT] Provider: Groq")
            return text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and self._gemini_api_key:
                log.warning("[STT] Groq rate limited — switching to Gemini...")
                text = self._transcribe_gemini(wav_bytes, language)
                log.info("[STT] Provider: Gemini")
                return text
            raise

    def _transcribe_groq(self, wav_bytes: bytes, language: str) -> str:
        """Send audio to Groq Whisper API."""
        data = {
            "model": "whisper-large-v3",
            "response_format": "text",
        }
        if language != "auto":
            data["language"] = language

        response = httpx.post(
            self.GROQ_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            data=data,
            files={"file": ("recording.wav", wav_bytes, "audio/wav")},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.text.strip()

    def _transcribe_gemini(self, wav_bytes: bytes, language: str) -> str:
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
            self.GEMINI_URL,
            params={"key": self._gemini_api_key},
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        result = response.json()
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
