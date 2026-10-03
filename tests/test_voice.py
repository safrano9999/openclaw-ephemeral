import json
from pathlib import Path
import tempfile
import unittest

from openclaw_ephemeral.environment import ConfigurationError
from openclaw_ephemeral.plugins import OpenClawPlugin, register_openclaw_plugins
from openclaw_ephemeral.voice import voice_settings


class VoiceSettingsTests(unittest.TestCase):
    def test_presets_do_not_invent_a_server_or_gateway_endpoint(self):
        settings = voice_settings("speaches", {})
        self.assertNotIn("baseUrl", settings)
        self.assertEqual(settings, {
            "sttModel": "Systran/faster-whisper-small",
            "ttsModel": "speaches-ai/piper-de_DE-thorsten-high",
            "ttsVoice": "thorsten", "responseFormat": "mp3",
        })
        self.assertEqual(voice_settings("mai-transcribe", {}), {
            "region": "eastus", "model": "MAI-Transcribe-2",
            "apiVersion": "2025-10-15", "maxFileSize": 26214400,
        })

    def test_all_ten_injected_values_have_their_intended_effect(self):
        env = {
            "SPEACHES_BASE_URL": "https://speech.example.test:8001/v1/",
            "SPEACHES_STT_MODEL": "custom/stt", "SPEACHES_TTS_MODEL": "custom/tts",
            "SPEACHES_TTS_VOICE": "custom-voice", "SPEACHES_TTS_RESPONSE_FORMAT": "wav",
            "MAI_TRANSCRIBE_REGION": "westus", "MAI_TRANSCRIBE_MODEL": "chosen-model",
            "MAI_TRANSCRIBE_API_VERSION": "2025-10-15-preview",
            "MAI_TRANSCRIBE_MAX_FILE_SIZE": "123456", "MAI_TRANSCRIBE_API_KEY": "private-test-bearer",
            "OPENCLAW_GATEWAY_PORT": "12345",
        }
        self.assertEqual(voice_settings("speaches", env), {
            "baseUrl": "https://speech.example.test:8001/v1", "sttModel": "custom/stt",
            "ttsModel": "custom/tts", "ttsVoice": "custom-voice", "responseFormat": "wav",
        })
        mai = voice_settings("mai-transcribe", env)
        self.assertEqual(mai, {"region": "westus", "model": "chosen-model",
                              "apiVersion": "2025-10-15-preview", "maxFileSize": 123456,
                              "apiKey": "${MAI_TRANSCRIBE_API_KEY}"})
        self.assertNotIn("private-test-bearer", json.dumps(mai))

    def test_invalid_inputs_fail_without_echoing_a_secret_url(self):
        for value in ("https://user:secret@example.org/v1", "file:///x", "https://x:70000/v1",
                      "https://x/v1?token=secret", "https://x/v1#secret"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as error:
                voice_settings("speaches", {"SPEACHES_BASE_URL": value})
            self.assertNotIn("secret", str(error.exception))
        for name, value in (("MAI_TRANSCRIBE_MAX_FILE_SIZE", "0"),
                            ("MAI_TRANSCRIBE_REGION", "x.attacker.invalid"),
                            ("MAI_TRANSCRIBE_API_VERSION", "bad&x=1")):
            with self.subTest(name=name), self.assertRaises(ConfigurationError):
                voice_settings("mai-transcribe", {name: value})

    def test_plugin_registration_keeps_private_config_file_and_init_settings(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            config_file = root / "config.conf"
            config_file.write_text('{"private":"preserve"}')
            properties = {key: {} for key in ("configPath", "region", "model", "apiVersion", "maxFileSize", "apiKey")}
            plugin = OpenClawPlugin("voice", "mai-transcribe", root,
                                    {"configSchema": {"properties": properties}}, None)
            config = {"tools": {"media": {"audio": {"models": ["init-choice"]}}}}
            register_openclaw_plugins(config, [plugin], environ={"MAI_TRANSCRIBE_REGION": "westus"},
                                      destination=root / "openclaw.json")
            entry = config["plugins"]["entries"]["mai-transcribe"]["config"]
            self.assertEqual(entry["region"], "westus")
            self.assertEqual(entry["configPath"], str(config_file))
            self.assertEqual(config_file.read_text(), '{"private":"preserve"}')
            self.assertEqual(config["tools"]["media"]["audio"]["models"], ["init-choice"])

    def test_unrelated_plugins_have_no_voice_settings(self):
        self.assertEqual(voice_settings("azure-speech", {"MAI_TRANSCRIBE_MAX_FILE_SIZE": "invalid"}), {})


if __name__ == "__main__":
    unittest.main()
