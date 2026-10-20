import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from openclaw_ephemeral.catalog_publication import PUBLICATION_SOURCE


class CatalogPublicationTests(unittest.TestCase):
    def test_batch_publishes_all_agents_and_releases_cache_on_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            source = PUBLICATION_SOURCE.replace(
                'import { listAgentIds, getPreparedModelCatalogSnapshot } from "openclaw/plugin-sdk/agent-runtime";',
                'const listAgentIds = cfg => Object.keys(cfg.agents.entries); const getPreparedModelCatalogSnapshot = () => {};')
            (root / "publication.mjs").write_text(source)
            (root / "test.mjs").write_text(r'''
import assert from "node:assert/strict";
import { BATCH_CACHE, publishAllCatalogs } from "./publication.mjs";
const config = {agents:{entries:{main:{},goldesel:{},seo:{}}}};
const context = {getRuntimeConfig:()=>config};
let calls = 0;
const publisher = async (cfg, options) => {
  calls++;
  assert.equal(cfg,config);
  assert.equal(options.catalogMode,"live");
  assert.equal(options.agentIds,undefined);
  assert.equal(options.isPublicationCurrent(),true);
  assert.ok(globalThis[BATCH_CACHE] instanceof Map);
  await assert.rejects(publishAllCatalogs(context,publisher),/already running/);
};
const result = await publishAllCatalogs(context,publisher,params=>{
  assert.equal(params.readOnly,false);
  return {entries:[{id:"same-model"}]};
});
assert.equal(calls,1);
assert.deepEqual(result.agents.map(a=>a.agentId),["main","goldesel","seo"]);
assert.equal(globalThis[BATCH_CACHE],undefined);
await assert.rejects(publishAllCatalogs(context,async()=>{throw new Error("test failure")}),/test failure/);
assert.equal(globalThis[BATCH_CACHE],undefined);
''')
            result = subprocess.run(["node", str(root / "test.mjs")], capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_init_script_uses_one_batch_call_and_can_run_again(self):
        path = Path(__file__).resolve().parents[1] / "image/runtime/usr/local/libexec/openclaw-openai-refresh.py"
        spec = importlib.util.spec_from_file_location("catalog_init", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        def run(argv, **kwargs):
            if argv == ["openclaw", "--version"]:
                return subprocess.CompletedProcess(argv, 0, stdout="OpenClaw 2026.9.4 (test)\n")
            self.assertEqual(argv[:4], ["openclaw", "gateway", "call", "ephemeral.models.refresh"])
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps({
                "agents": [{"agentId": "main", "models": 3}],
                "injectedCatalogAcquisitions": 1,
            }))
        runner = Mock(side_effect=run)
        with patch.object(module.subprocess, "run", runner):
            self.assertEqual(module.main(), 0)
            self.assertEqual(module.main(), 0)
        self.assertEqual(runner.call_count, 4)
