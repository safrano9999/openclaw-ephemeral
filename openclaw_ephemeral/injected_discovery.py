"""Prepare a native OpenClaw catalog plugin from injected provider pairs."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path

from .environment import floating, state_dir_path
from .filesystem import atomic_write_json
from .catalog_publication import PUBLICATION_SOURCE
from .plugins import OpenClawPlugin
from .providers import OpenAIV1Provider


DISCOVERY_PLUGIN_ID = "ephemeral-openai-v1"

# Public SDK entry point, not a copy of OpenClaw's HTTP/catalog implementation.
# Credentials are resolved by OpenClaw for each provider's own SecretRef.
PLUGIN_SOURCE = r'''
import { readFileSync } from "node:fs";
import { buildOpenAICompatibleLiveProviderCatalog } from "openclaw/plugin-sdk/provider-catalog-live-runtime";
import { fetchWithSsrFGuard } from "openclaw/plugin-sdk/ssrf-runtime";
import { BATCH_CACHE, publishAllCatalogs } from "./publication.mjs";

function discoveryHeaders(name, auth) {
  const raw = (process.env[name] || "").trim();
  const headers = raw ? JSON.parse(raw.replace(/^(['"])(.*)\1$/s, "$2")) : {};
  if (!headers || Array.isArray(headers) || typeof headers !== "object")
    throw new Error("Invalid injected discovery headers");
  for (const [key, value] of Object.entries(headers)) {
    if (!/^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/.test(key)
        || key.toLowerCase() === "authorization"
        || typeof value !== "string" || /[\r\n]/.test(value))
      throw new Error("Invalid injected discovery header");
  }
  return { Accept: "application/json", ...headers,
    Authorization: `Bearer ${auth.discoveryApiKey ?? auth.apiKey}` };
}

function catalogErrorDetails(error) {
  const parts = [];
  for (let cause = error, depth = 0; cause && depth < 4; cause = cause.cause, depth++)
    parts.push(`${cause.code ? `[${cause.code}] ` : ""}${cause.stack || String(cause)}`);
  let message = parts.join("\nCaused by: ");
  for (const [name, raw] of Object.entries(process.env)) {
    if (!/KEY|TOKEN|BEARER|SECRET|PASSWORD|CREDENTIAL/i.test(name) || !raw) continue;
    const value = raw.trim().replace(/^(['"])(.*)\1$/s, "$2");
    if (value.length >= 4) message = message.split(value).join("[REDACTED]");
  }
  return message.replace(/\bBearer\s+\S+/gi, "Bearer [REDACTED]")
    .replace(/([?&](?:api[_-]?key|key|token|access_token|secret)=)[^&#\s]+/gi, "$1[REDACTED]");
}

export function createPlugin(specs, buildCatalog = buildOpenAICompatibleLiveProviderCatalog,
                             fetchGuard = fetchWithSsrFGuard) {
  return {
    id: "ephemeral-openai-v1",
    name: "Injected OpenAI-compatible providers",
    register(api) {
      api.registerGatewayMethod("ephemeral.models.refresh", async ({ context, respond }) => {
        try {
          respond(true, await publishAllCatalogs(context));
        } catch (error) {
          api.logger?.error?.(`[ephemeral-openai-v1] Catalog publication failed: ${catalogErrorDetails(error)}`);
          respond(false, undefined, {
            code: "UNAVAILABLE",
            message: "Model catalog publication failed",
          });
        }
      }, { scope: "operator.admin" });
      for (const spec of specs) {
        const buildProvider = () => ({
          baseUrl: spec.baseUrl,
          api: "openai-completions",
          request: { allowPrivateNetwork: true },
          models: [],
        });
        api.registerProvider({
          id: spec.id,
          label: spec.label,
          envVars: [spec.keyEnv],
          catalog: {
            order: "simple",
            run: ctx => {
              if (ctx.providerIds && !ctx.providerIds.includes(spec.id)) return null;
              const auth = ctx.resolveProviderApiKey(spec.id);
              if (!auth.apiKey) return null;
              const acquire = () => buildCatalog({
                ...auth,
                providerId: spec.id,
                providerConfig: buildProvider(),
                discoveryMode: "strict",
                fetchGuard: args => fetchGuard({ ...args, policy: {
                  ...args.policy, allowPrivateNetwork: true,
                  hostnameAllowlist: [new URL(spec.baseUrl).hostname],
                }}),
                modelDiscovery: {
                  endpointPath: "models",
                  timeoutMs: spec.timeoutMs,
                  buildRequestHeaders: auth => discoveryHeaders(spec.headersEnv, auth),
                },
              });
              const cache = globalThis[BATCH_CACHE];
              if (!cache) return acquire();
              const key = JSON.stringify([spec.id, spec.baseUrl, auth.apiKey,
                auth.discoveryApiKey, auth.profileId, process.env[spec.headersEnv]]);
              if (!cache.has(key)) cache.set(key, acquire());
              return cache.get(key);
            },
          },
          staticCatalog: {
            order: "simple",
            run: async () => ({ provider: buildProvider() }),
          },
        });
      }
    },
  };
}

export default createPlugin(JSON.parse(readFileSync(new URL("./providers.json", import.meta.url), "utf8")));
'''


def prepare_discovery_plugin(
    providers: Sequence[OpenAIV1Provider],
    environ: Mapping[str, str],
    *,
    destination: Path,
) -> OpenClawPlugin | None:
    """Write code and secret-free provider descriptors; never query a provider."""
    selected = [provider for provider in providers if provider.native_discovery]
    root = state_dir_path(environ, destination) / "generated-plugins" / DISCOVERY_PLUGIN_ID
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    timeout_ms = int(floating(environ, "OPENCLAW_DISCOVERY_TIMEOUT", default=35.0) * 1000)
    specs = [{
        "id": provider.provider_id,
        "label": provider.configured_name or provider.provider_id,
        "baseUrl": provider.base_url,
        "keyEnv": provider.key_env,
        "headersEnv": provider.discovery_headers_env,
        "timeoutMs": timeout_ms,
    } for provider in selected]
    manifest = {
        "id": DISCOVERY_PLUGIN_ID,
        "name": "Injected OpenAI-compatible providers",
        "activation": {"onStartup": True},
        "providers": [provider.provider_id for provider in selected],
        "modelCatalog": {"discovery": {
            provider.provider_id: "runtime" for provider in selected
        }},
        "setup": {"providers": [
            {"id": provider.provider_id, "envVars": [provider.key_env]}
            for provider in selected
        ]},
        "configSchema": {"type": "object", "additionalProperties": False, "properties": {}},
    }
    atomic_write_json(root / "providers.json", specs)
    atomic_write_json(root / "openclaw.plugin.json", manifest)
    atomic_write_json(root / "package.json", {
        "name": DISCOVERY_PLUGIN_ID, "version": "1.0.0", "type": "module",
        "openclaw": {"extensions": ["./index.mjs"]},
    })
    for name, source in {"index.mjs": PLUGIN_SOURCE, "publication.mjs": PUBLICATION_SOURCE}.items():
        fd, temporary = tempfile.mkstemp(prefix=".plugin-", dir=root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(source.lstrip())
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, root / name)
        finally:
            Path(temporary).unlink(missing_ok=True)
    return OpenClawPlugin(
        repository="openclaw-ephemeral", plugin_id=DISCOVERY_PLUGIN_ID,
        path=root, manifest=manifest, hook_path=None,
    )
