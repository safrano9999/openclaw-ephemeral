"""Gateway-side batch publication for the pinned OpenClaw runtime."""

PUBLICATION_SOURCE = r'''
import { readdir, readFile, realpath } from "node:fs/promises";
import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";
import { listAgentIds, getPreparedModelCatalogSnapshot } from "openclaw/plugin-sdk/agent-runtime";

export const BATCH_CACHE = Symbol.for("openclaw-ephemeral.catalog-publication");

// This lifecycle entry point is internal to the pinned runtime, not a CLI API.
async function loadBatchPublisher() {
  const require = createRequire(await realpath(process.argv[1]));
  const dist = new URL("../", pathToFileURL(require.resolve("openclaw/plugin-sdk/agent-runtime")));
  const pkg = JSON.parse(await readFile(new URL("../package.json", dist), "utf8"));
  if (pkg.version !== "2026.9.4") throw new Error("Unsupported OpenClaw catalog publication version");
  for (const file of (await readdir(dist)).sort()) {
    if (!/^prepared-model-runtime-[^.]+\.mjs$/.test(file)) continue;
    const module = await import(new URL(file, dist).href);
    if (typeof module.refreshPreparedModelRuntimeSnapshots === "function")
      return module.refreshPreparedModelRuntimeSnapshots;
  }
  throw new Error("OpenClaw batch catalog publication is unavailable");
}

export async function publishAllCatalogs(context, publish, read = getPreparedModelCatalogSnapshot) {
  const cfg = context.getRuntimeConfig();
  const cache = new Map();
  const publisher = publish ?? await loadBatchPublisher();
  if (globalThis[BATCH_CACHE]) throw new Error("Catalog publication is already running");
  globalThis[BATCH_CACHE] = cache;
  try {
    await publisher(cfg, {
      gatewayLifecycle: true,
      catalogMode: "live",
      allowGatewaySubagentBinding: true,
      isPublicationCurrent: () => context.getRuntimeConfig() === cfg,
    });
    for (const [key, promise] of cache) {
      const result = await promise;
      if (!result?.outcomes?.some(outcome => outcome.status === "ready"))
        throw new Error(`Discovery failed for injected provider ${JSON.parse(key)[0]}`);
    }
    const agents = listAgentIds(cfg).map(agentId => {
      const snapshot = read({ config: cfg, agentId, readOnly: false });
      if (!snapshot) throw new Error(`Catalog was not published for agent ${agentId}`);
      return { agentId, models: snapshot.entries.length,
        outcomes: snapshot.providerOutcomes ?? [] };
    });
    return { agents, injectedCatalogAcquisitions: cache.size };
  } finally {
    delete globalThis[BATCH_CACHE];
  }
}
'''
