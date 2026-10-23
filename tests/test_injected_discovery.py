"""Deferred catalogs use native discovery without leaking or sharing credentials."""
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from openclaw_ephemeral.configuration import configure
from openclaw_ephemeral.injected_discovery import (
    DISCOVERY_PLUGIN_ID, PLUGIN_SOURCE, prepare_discovery_plugin,
)
from openclaw_ephemeral.providers import (
    discover_openai_v1_providers, select_openai_v1_default,
)


def pairs():
    return {
        "OPENAI_V1_PROVIDER": "alpha",
        "OPENAI_V1_URL": "https://alpha.example/v1",
        "OPENAI_V1_KEY": "alpha-test-secret",
        "OPENAI_V1_MODELS": "do-not-seed",
        "OPENAI_V1_PROVIDER_03": "beta",
        "OPENAI_V1_URL_03": "https://beta.example",
        "OPENAI_V1_PORT_03": "8443",
        "OPENAI_V1_KEY_03": "beta-test-secret",
        "OPENAI_V1_DISCOVERY_HEADERS_03": '{"X-Region":"eu"}',
    }


class InjectedDiscoveryTests(unittest.TestCase):
    def test_deferred_pairs_do_not_fetch_or_seed_models(self):
        opener = Mock(side_effect=AssertionError("Bootstrap must not fetch models"))
        providers, warnings = discover_openai_v1_providers(pairs(), opener=opener, defer_discovery=True)
        opener.assert_not_called()
        self.assertEqual(warnings, ())
        self.assertEqual([p.provider_id for p in providers], ["alpha", "beta"])
        self.assertTrue(all(p.native_discovery and p.models == () for p in providers))
        self.assertEqual(providers[1].base_url, "https://beta.example:8443/v1")
        self.assertEqual(providers[1].key_env, "OPENAI_V1_KEY_03")
        self.assertEqual(providers[1].discovery_headers_env, "OPENAI_V1_DISCOVERY_HEADERS_03")
        primary, selected = select_openai_v1_default(providers, "beta/explicit-default")
        self.assertEqual(primary, "beta/explicit-default")
        self.assertEqual(selected, providers)

    def test_all_provider_names_use_native_discovery_and_external_callers_are_unchanged(self):
        env = pairs()
        env.update(OPENAI_V1_PROVIDER_2="litellm-free",
                   OPENAI_V1_URL_2="https://proxy.example/v1",
                   OPENAI_V1_KEY_2="proxy-test-secret")
        env.update(OPENAI_V1_PROVIDER_4="litellm",
                   OPENAI_V1_URL_4="https://proxy.example/v1",
                   OPENAI_V1_KEY_4="different-proxy-test-secret")
        urls = []

        def opener(request, **kwargs):
            urls.append(request.full_url)
            return SimpleNamespace(read=lambda _: b'{"data":[{"id":"live"}]}')

        providers, _ = discover_openai_v1_providers(env, opener=opener, defer_discovery=True)
        self.assertEqual(urls, [])
        self.assertTrue(all(p.native_discovery for p in providers))
        self.assertEqual(providers[1].models, ())
        urls.clear()
        eager, _ = discover_openai_v1_providers(env, opener=opener)
        self.assertEqual(len(urls), 4)
        self.assertTrue(all(not p.native_discovery for p in eager))

    def test_configure_registers_plugin_without_model_names_or_resolved_keys(self):
        with tempfile.TemporaryDirectory() as raw:
            env = {**pairs(), "HOME": raw, "OPENCLAW_CONFIG": raw + "/openclaw.json",
                   "OPENCLAW_TELEGRAMTOKEN": "telegram-test-secret",
                   "OPENCLAW_TELEGRAM_CHAT_ID": "123",
                   "OPENCLAW_TELEGRAM_AGENT": "seo"}
            runner = Mock(return_value=SimpleNamespace(returncode=0, stdout="{}", stderr=""))
            with patch("openclaw_ephemeral.configuration.discover_native_models", return_value=((), ())):
                result = configure(env, runner=runner, opener=Mock(side_effect=AssertionError("network")))
                first = result.path.read_bytes()
                configure(env, runner=runner, opener=Mock(side_effect=AssertionError("network")))
            self.assertEqual(first, result.path.read_bytes())
            config = json.loads(first)
            for name, key in [("alpha", "OPENAI_V1_KEY"), ("beta", "OPENAI_V1_KEY_03")]:
                provider = config["models"]["providers"][name]
                self.assertEqual(provider["models"], [])
                self.assertEqual(provider["apiKey"]["id"], key)
            self.assertEqual(config["agents"]["defaults"]["modelPolicy"], {"allow": []})
            for agent in config["agents"]["entries"].values():
                self.assertNotIn("modelPolicy", agent)
            entry = config["plugins"]["entries"][DISCOVERY_PLUGIN_ID]
            self.assertTrue(entry["enabled"])
            plugin_root = Path(config["plugins"]["load"]["paths"][-1])
            manifest = json.loads((plugin_root / "openclaw.plugin.json").read_text())
            self.assertEqual(manifest["providers"], ["alpha", "beta"])
            self.assertEqual(manifest["modelCatalog"]["discovery"], {"alpha": "runtime", "beta": "runtime"})
            for p in [result.path, *plugin_root.iterdir()]:
                if p.is_file():
                    text = p.read_text()
                    for secret in ["alpha-test-secret", "beta-test-secret", "do-not-seed", "telegram-test-secret"]:
                        self.assertNotIn(secret, text)
            self.assertTrue(all(call.args[0][-3:] == ["plugins", "registry", "--refresh"]
                                for call in runner.call_args_list))

    def test_descriptors_follow_changed_pairs_without_retaining_removed_providers(self):
        with tempfile.TemporaryDirectory() as raw:
            env = pairs()
            providers, _ = discover_openai_v1_providers(env, defer_discovery=True)
            plugin = prepare_discovery_plugin(providers, {"HOME": raw}, destination=Path(raw) / "openclaw.json")
            prepare_discovery_plugin(providers[:1], {"HOME": raw}, destination=Path(raw) / "openclaw.json")
            self.assertEqual(len(json.loads((plugin.path / "providers.json").read_text())), 1)

    def test_javascript_registers_independent_native_catalogs(self):
        # The SDK itself is owned by OpenClaw. This exercises our adapter with
        # a recording SDK boundary and no gateway, network, or real credentials.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = PLUGIN_SOURCE.replace(
                'import { buildOpenAICompatibleLiveProviderCatalog } from "openclaw/plugin-sdk/provider-catalog-live-runtime";',
                'const buildOpenAICompatibleLiveProviderCatalog = () => { throw new Error("Unexpected SDK call"); };')
            source = source.replace(
                'import { fetchWithSsrFGuard } from "openclaw/plugin-sdk/ssrf-runtime";',
                'const fetchWithSsrFGuard = () => { throw new Error("Unexpected network call"); };')
            source = source.replace(
                'import { BATCH_CACHE, publishAllCatalogs } from "./publication.mjs";',
                'const BATCH_CACHE = Symbol.for("openclaw-ephemeral.catalog-publication"); const publishAllCatalogs = context => context.publish();')
            (root / "index.mjs").write_text(source)
            (root / "providers.json").write_text("[]")
            (root / "test.mjs").write_text(r'''
import assert from "node:assert/strict";
import { createPlugin } from "./index.mjs";
const specs = [
  {id:"alpha",label:"Alpha",baseUrl:"https://a.example/v1",keyEnv:"KEY_A",headersEnv:"HEAD_A",timeoutMs:35000},
  {id:"beta",label:"Beta",baseUrl:"https://b.example/v1",keyEnv:"KEY_B",headersEnv:"HEAD_B",timeoutMs:35000},
];
const registered = [];
const calls = [];
const sdk = async args => {
  calls.push(args);
  const headers = args.modelDiscovery.buildRequestHeaders(args);
  await args.fetchGuard({url:args.providerConfig.baseUrl+"/models"});
  return {provider:{...args.providerConfig, models:[{id:args.providerId+"-live"}]}, headers};
};
const requests = [];
const errors = [];
let refresh;
createPlugin(specs, sdk, async args => requests.push(args)).register({
  logger: {error: message => errors.push(message)},
  registerProvider: p => registered.push(p),
  registerGatewayMethod: (name, handler, options) => {
    assert.equal(name, "ephemeral.models.refresh");
    assert.equal(options.scope, "operator.admin");
    refresh = handler;
  },
});
const replies = [];
await refresh({context:{publish:async () => ({agents:["main","seo"]})},
  respond:(...args)=>replies.push(args)});
assert.deepEqual(replies, [[true,{agents:["main","seo"]}]]);
process.env.DIAGNOSTIC_TEST_KEY = '"private-log-secret"';
await refresh({context:{publish:async () => {throw new Error("private details private-log-secret Bearer other-token https://example.test/?token=query-token",
  {cause:Object.assign(new Error("network connection failed"),{code:"ECONNREFUSED"})});}},
  respond:(...args)=>replies.push(args)});
assert.deepEqual(replies[1], [false,undefined,{
  code:"UNAVAILABLE",message:"Model catalog publication failed"}]);
assert.equal(errors.length,1);
assert.match(errors[0],/private details/);
assert.match(errors[0],/ECONNREFUSED/);
assert.match(errors[0],/network connection failed/);
for (const secret of ["private-log-secret","other-token","query-token"]) assert.ok(!errors[0].includes(secret));
assert.deepEqual(registered.map(p=>p.envVars), [["KEY_A"],["KEY_B"]]);
const ctx = {resolveProviderApiKey: id => ({apiKey:id+"-test-key"})};
process.env.HEAD_B = '{"X-Region":"eu"}';
const a = await registered[0].catalog.run(ctx);
const b = await registered[1].catalog.run(ctx);
assert.equal(a.headers.Authorization,"Bearer alpha-test-key");
assert.equal(b.headers.Authorization,"Bearer beta-test-key");
assert.equal(b.headers["X-Region"],"eu");
assert.equal(a.provider.baseUrl,"https://a.example/v1");
assert.equal(b.provider.baseUrl,"https://b.example/v1");
assert.equal(calls[0].discoveryMode,"strict");
assert.equal(calls[0].modelDiscovery.endpointPath,"models");
assert.deepEqual(calls[0].providerConfig.models,[]);
assert.deepEqual(requests.map(r=>r.policy), [
  {allowPrivateNetwork:true,hostnameAllowlist:["a.example"]},
  {allowPrivateNetwork:true,hostnameAllowlist:["b.example"]},
]);
assert.equal(await registered[0].catalog.run({...ctx,providerIds:["beta"]}),null);
assert.equal(calls.length,2);
globalThis[Symbol.for("openclaw-ephemeral.catalog-publication")] = new Map();
await registered[0].catalog.run(ctx);
await registered[0].catalog.run(ctx);
assert.equal(calls.length,3);
await registered[0].catalog.run({resolveProviderApiKey: () => ({apiKey:"another-account"})});
assert.equal(calls.length,4);
delete globalThis[Symbol.for("openclaw-ephemeral.catalog-publication")];
assert.deepEqual((await registered[0].staticCatalog.run()).provider.models,[]);
process.env.HEAD_B = '{"authorization":"wrong"}';
await assert.rejects(registered[1].catalog.run(ctx),/Invalid injected discovery header/);
''')
            result = subprocess.run(["node", str(root / "test.mjs")], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)
