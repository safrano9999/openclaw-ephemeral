"""Voice plugin settings, independent of deployment-specific init hooks."""

from collections.abc import Mapping
import re
from urllib.parse import urlsplit

from .environment import ConfigurationError, clean, integer


def voice_settings(plugin_id: str, environ: Mapping[str, str]) -> dict:
    """Return settings only for an installed plugin, without resolving secrets."""
    def value(name, default=""):
        raw = clean(environ.get(name)) or default
        if any(ord(char) < 32 for char in raw):
            raise ConfigurationError(name + " must not contain control characters")
        return raw

    if plugin_id == "speaches":
        url = value("SPEACHES_BASE_URL").rstrip("/")
        if url:
            try:
                parsed = urlsplit(url)
                valid = (parsed.scheme in {"http", "https"} and parsed.hostname
                         and (parsed.port is None or 1 <= parsed.port <= 65535)
                         and not parsed.username and not parsed.password
                         and not parsed.query and not parsed.fragment)
            except ValueError:
                valid = False
            if not valid:
                raise ConfigurationError("SPEACHES_BASE_URL must be an HTTP(S) API base URL")
        result = {
            "sttModel": value("SPEACHES_STT_MODEL", "Systran/faster-whisper-small"),
            "ttsModel": value("SPEACHES_TTS_MODEL", "speaches-ai/piper-de_DE-thorsten-high"),
            "ttsVoice": value("SPEACHES_TTS_VOICE", "thorsten"),
            "responseFormat": value("SPEACHES_TTS_RESPONSE_FORMAT", "mp3"),
        }
        if result["responseFormat"] not in {"mp3", "opus", "ogg", "aac", "flac", "wav", "pcm"}:
            raise ConfigurationError("Unsupported SPEACHES_TTS_RESPONSE_FORMAT")
        if url:
            result["baseUrl"] = url
        return result
    if plugin_id == "mai-transcribe":
        region = value("MAI_TRANSCRIBE_REGION", "eastus")
        if not re.fullmatch(r"[a-z0-9-]+", region):
            raise ConfigurationError("MAI_TRANSCRIBE_REGION must be an Azure region name")
        version = value("MAI_TRANSCRIBE_API_VERSION", "2025-10-15")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:-preview)?", version):
            raise ConfigurationError("Invalid MAI_TRANSCRIBE_API_VERSION")
        result = {
            "region": region,
            "model": value("MAI_TRANSCRIBE_MODEL", "MAI-Transcribe-2"),
            "apiVersion": version,
            "maxFileSize": integer(environ, "MAI_TRANSCRIBE_MAX_FILE_SIZE", default=26214400),
        }
        if clean(environ.get("MAI_TRANSCRIBE_API_KEY")):
            # The plugin's schema uses a string; OpenClaw resolves env templates
            # in memory. Never write the bearer into ephemeral JSON.
            result["apiKey"] = "${MAI_TRANSCRIBE_API_KEY}"
        return result
    return {}
