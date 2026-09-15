from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from openclaw_ephemeral.configuration import build_config, configure
from openclaw_ephemeral.environment import ConfigurationError, secret_ref
from openclaw_ephemeral.providers import OpenAIV1Provider


EMBEDDING_ENV = {
    "OPENCLAW_EMBEDDING_NAME": "nous-embeddings",
    "OPENCLAW_EMBEDDING_URL": "https://inference-api.nousresearch.com/v1/",
    "OPENCLAW_EMBEDDING_MODEL": "openai/text-embedding-3-small",
    "OPENCLAW_EMBEDDING_BEARER": "embedding-test-secret",
}
BASE_ENV = {
    "OPENCLAW_CONTROL_UI_ALLOWED_ORIGINS": "http://localhost:18789",
}


class EmbeddingConfigurationTests(unittest.TestCase):
    def build(self, environ=None, providers=()):
        return build_config(
            {**BASE_ENV, **(EMBEDDING_ENV if environ is None else environ)},
            destination=Path("/tmp/embedding-config-test/openclaw.json"),
            openai_v1_providers=providers,
        )

    def test_embeddings_preserve_chat_models_and_default(self):
        chat = OpenAIV1Provider(
            index=1, provider_id="litellm", configured_name="litellm",
            base_url="http://chat.test/v1", key_env="OPENAI_V1_KEY",
            models=("luna",), streaming=True,
        )
        config, primary, _ = self.build({
            **EMBEDDING_ENV, "OPENCLAW_OPENAI_V1_DEFAULT_LLM": "luna",
        }, providers=(chat,))
        self.assertEqual(primary, "litellm/luna")
        self.assertEqual(config["memory"]["search"], {
            "provider": "nous-embeddings",
            "model": "openai/text-embedding-3-small",
        })
        providers = config["models"]["providers"]
        self.assertEqual(set(providers), {"litellm", "nous-embeddings"})
        self.assertEqual(providers["nous-embeddings"], {
            "baseUrl": "https://inference-api.nousresearch.com/v1",
            "api": "openai-completions",
            "models": [{
                "id": "openai/text-embedding-3-small",
                "name": "openai/text-embedding-3-small",
            }],
            "apiKey": secret_ref("OPENCLAW_EMBEDDING_BEARER"),
        })
        self.assertIn("litellm/luna", config["agents"]["defaults"]["models"])
        self.assertFalse(any(
            name.startswith("nous-embeddings/")
            for name in config["agents"]["defaults"]["models"]
        ))
        self.assertNotIn("embedding-test-secret", json.dumps(config))

    def test_first_enabled_group_selects_memory_and_repeated_auth_stays_scoped(self):
        config, _, _ = self.build({
            **EMBEDDING_ENV,
            "OPENCLAW_EMBEDDING_URL": "",
            "OPENCLAW_EMBEDDING_NAME_2": "Local-Embedding",
            "OPENCLAW_EMBEDDING_URL_2": "http://embedding.test:8080/v1",
            "OPENCLAW_EMBEDDING_MODEL_2": "local-model",
            "OPENCLAW_EMBEDDING_NAME_50": "backup-embedding",
            "OPENCLAW_EMBEDDING_URL_50": "https://backup.test/v1",
            "OPENCLAW_EMBEDDING_MODEL_50": "backup-model",
            "OPENCLAW_EMBEDDING_BEARER_50": "backup-secret",
        })
        self.assertEqual(config["memory"]["search"], {
            "provider": "local-embedding", "model": "local-model",
        })
        providers = config["models"]["providers"]
        self.assertEqual(set(providers), {"local-embedding", "backup-embedding"})
        self.assertNotIn("apiKey", providers["local-embedding"])
        self.assertEqual(providers["backup-embedding"]["apiKey"],
                         secret_ref("OPENCLAW_EMBEDDING_BEARER_50"))

    def test_disabled_groups_leave_memory_unconfigured(self):
        for environ in ({}, {**EMBEDDING_ENV, "OPENCLAW_EMBEDDING_URL": " "}):
            with self.subTest(environ=environ):
                config, _, _ = self.build(environ)
                self.assertNotIn("memory", config)
                self.assertNotIn("models", config)

    def test_invalid_enabled_group_is_rejected(self):
        cases = (
            ("NAME", ""), ("NAME", "invalid/name"), ("MODEL", ""),
            ("URL", "file:///tmp/embeddings"),
            ("URL", "https://user:password@embedding.test/v1"),
            ("URL", "https://embedding.test:99999/v1"),
            ("URL", "https://embedding.test/v1?key=secret"),
            ("URL", "https://embedding.test/v1#fragment"),
            ("BEARER", "Bearer token"), ("BEARER", "token\nheader"),
        )
        for field, value in cases:
            with self.subTest(field=field, value=value):
                with self.assertRaises(ConfigurationError):
                    self.build({**EMBEDDING_ENV, f"OPENCLAW_EMBEDDING_{field}": value})

    def test_duplicate_names_cannot_shadow_another_embedding_group(self):
        with self.assertRaisesRegex(ConfigurationError, "Duplicate embedding"):
            self.build({
                **EMBEDDING_ENV,
                "OPENCLAW_EMBEDDING_NAME_2": "NOUS-EMBEDDINGS",
                "OPENCLAW_EMBEDDING_URL_2": "https://other.test/v1",
                "OPENCLAW_EMBEDDING_MODEL_2": "other-model",
            })

    def test_embedding_name_cannot_overwrite_chat_provider(self):
        chat = OpenAIV1Provider(
            index=1, provider_id="nous-embeddings", configured_name="chat",
            base_url="https://chat.test/v1", key_env="OPENAI_V1_KEY",
            models=("chat-model",), streaming=False,
        )
        with self.assertRaisesRegex(ConfigurationError, "differ from chat providers"):
            self.build(providers=(chat,))

    def test_rebuild_restores_embeddings_without_catalog_requests_or_plaintext_token(self):
        with tempfile.TemporaryDirectory() as raw:
            destination = Path(raw) / "openclaw.json"
            environ = {
                **BASE_ENV, **EMBEDDING_ENV,
                "HOME": raw, "OPENCLAW_CONFIG": str(destination),
            }
            opener = Mock(side_effect=AssertionError("Unexpected catalog request"))
            with patch(
                "openclaw_ephemeral.configuration.discover_native_models",
                return_value=((), ()),
            ):
                for _ in range(2):
                    destination.write_text('{"memory":{"search":{"provider":"openai"}}}')
                    result = configure(environ, opener=opener)
                    written = json.loads(destination.read_text())
                    self.assertEqual(written["memory"]["search"]["provider"], "nous-embeddings")
                    self.assertEqual(result.openai_v1_provider_count, 0)
                    self.assertEqual(result.openai_v1_model_count, 0)
                    self.assertNotIn("embedding-test-secret", destination.read_text())
                    self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            opener.assert_not_called()


if __name__ == "__main__":
    unittest.main()
