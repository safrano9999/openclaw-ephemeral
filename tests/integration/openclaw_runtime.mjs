import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";
import http from "node:http";
import { randomUUID } from "node:crypto";

const installed = process.env.UPGRADE_TARGET_PACKAGE;
// Bundle filenames and export aliases change between releases. Resolve the exact
// named functions exported by the selected installed release; never substitute
// a copied validator or silently accept a missing interface.
const required = new Map([['validateConfigObjectRaw', []], ['resolveDefaultModelForAgent', []], ['createSessionMcpRuntime', []]]);
for (const file of fs.readdirSync(path.join(installed, 'dist'))) {
  if (!file.endsWith('.mjs')) continue;
  const location = path.join(installed, 'dist', file);
  const text = fs.readFileSync(location, 'utf8');
  const exports = text.match(/^export \{([^}]+)\}/m)?.[1];
  for (const entry of exports?.split(',') ?? []) {
    const [name, alias = name] = entry.trim().split(/\s+as\s+/);
    if (required.has(name) && new RegExp(`^function ${name}\\(`, 'm').test(text))
      required.get(name).push([location, alias]);
  }
}
async function releaseFunction(name) {
  const candidates = required.get(name);
  assert.equal(candidates.length, 1, `Expected one exported upstream interface: ${name}`);
  const [file, alias] = candidates[0];
  const value = (await import(pathToFileURL(file).href))[alias];
  assert.equal(typeof value, 'function', `Missing upstream interface: ${name}`);
  return value;
}
const validateConfigObjectRaw = await releaseFunction('validateConfigObjectRaw');
const resolveDefaultModelForAgent = await releaseFunction('resolveDefaultModelForAgent');
const { resolveCodexMcpToolOverridesForAgent } = await import(
  pathToFileURL(path.join(installed, 'dist/plugin-sdk/codex-mcp-projection.js')).href);
const config = JSON.parse(fs.readFileSync(process.env.UPGRADE_CONFIG_FIXTURE));

test("exact installed upstream version without Deterministic", () => {
  assert.equal(fs.existsSync(path.join(installed, "deterministic-build.json")), false);
  for (const directory of [installed]) {
    assert.equal(JSON.parse(fs.readFileSync(path.join(directory, "package.json"))).version,
                 process.env.UPGRADE_TARGET_VERSION);
  }
});

test("upstream accepts generated agent, model, MCP and plugin configuration", () => {
  const result = validateConfigObjectRaw(config);
  assert.equal(result.ok, true, JSON.stringify(result.issues));
});

test("upstream rejects an invalid generated agent roster", () => {
  const broken = structuredClone(config);
  broken.agents.entries = "invalid";
  assert.equal(validateConfigObjectRaw(broken).ok, false);
});

test("both agents inherit the configured default model", () => {
  for (const agentId of ["main", "mtg"]) {
    assert.equal(config.agents.entries[agentId].model, undefined);
    const model = resolveDefaultModelForAgent({cfg: config, agentId, allowManifestNormalization: false});
    assert.deepEqual(model, {provider: "fixture", model: "model-a"});
  }
});

test("upstream applies exact MCP assignments and preserves the shared server", () => {
  for (const [agentId, denied, allowed] of [["main", "mtg", "general"], ["mtg", "general", "mtg"]]) {
    const overrides = resolveCodexMcpToolOverridesForAgent(config, {agentId});
    assert.equal(overrides.mcpServers[denied], false);
    assert.notEqual(overrides.mcpServers[allowed], false);
    assert.notEqual(overrides.mcpServers.shared, false);
  }
});

function help(args) {
  const result = spawnSync(process.execPath, [path.join(installed, "openclaw.mjs"), ...args, "--help"],
                           {env: process.env, encoding: "utf8", timeout: 60000});
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  return result.stdout;
}

test("target cron CLI supports the generator's scheduled command arguments", () => {
  const text = help(["cron", "add"]);
  for (const flag of ["--cron", "--name", "--agent", "--session", "--tz", "--exact",
                      "--command-argv", "--timeout-seconds", "--no-deliver", "--json"]) {
    assert.ok(text.includes(flag), `Missing target cron option: ${flag}`);
  }
});

test("target plugin registry supports generator refresh", () => {
  assert.ok(help(["plugins", "registry"]).includes("--refresh"));
});

test("configured provider models appear without invented dummy routes", () => {
  const catalogConfig = path.join(process.env.HOME, "catalog.json");
  fs.writeFileSync(catalogConfig, JSON.stringify({models: config.models}));
  const result = spawnSync(process.execPath,
    [path.join(installed, "openclaw.mjs"), "models", "list", "--all", "--json"],
    {env: {...process.env, OPENCLAW_CONFIG_PATH: catalogConfig}, encoding: "utf8", timeout: 90000, maxBuffer: 16 * 1024 * 1024});
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const payload = JSON.parse(result.stdout);
  const rows = Array.isArray(payload) ? payload : payload.models;
  assert.ok(rows.length > 0, JSON.stringify(payload));
  const keys = rows.map(row => row.key ?? row.id ?? row.model);
  assert.ok(keys.includes("fixture/model-a") && keys.includes("fixture/model-b"), JSON.stringify(keys));
  assert.ok(rows.every(row => !String(row.key ?? row.id ?? row.model).startsWith("dummy/")));
});

test("native MCP discovers and calls an explicitly configured private server", {timeout: 120000}, async () => {
  const requests = [];
  const server = http.createServer(async (request, response) => {
    if (request.method !== "POST") { response.writeHead(405).end(); return; }
    let body = "";
    for await (const part of request) body += part;
    const rpc = JSON.parse(body);
    requests.push(rpc.method);
    assert.equal(request.headers.authorization, "Bearer fixture-general-secret");
    if (rpc.id === undefined) { response.writeHead(202).end(); return; }
    const results = {
      initialize: {protocolVersion: "2025-03-26", capabilities: {tools: {}},
                   serverInfo: {name: "private-fixture", version: "1.0.0"}},
      "tools/list": {tools: [{name: "fixture_read", description: "Read fixture",
                             inputSchema: {type: "object", properties: {}}}]},
      "tools/call": {content: [{type: "text", text: "private MCP works"}]},
      ping: {},
    };
    response.writeHead(200, {"Content-Type": "application/json"});
    response.end(JSON.stringify({jsonrpc: "2.0", id: rpc.id,
      ...(results[rpc.method] ? {result: results[rpc.method]} :
        {error: {code: -32601, message: "Method not found"}})}));
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const createSessionMcpRuntime = await releaseFunction("createSessionMcpRuntime");
  const cfg = structuredClone(config);
  cfg.mcp.servers = {general: {...cfg.mcp.servers.general,
    url: `http://127.0.0.1:${server.address().port}/mcp`,
    headers: {Authorization: "Bearer fixture-general-secret"}}};
  const sessionId = `ephemeral-compat-${randomUUID()}`;
  let runtime;
  try {
    runtime = createSessionMcpRuntime({cfg, sessionId,
      workspaceDir: path.join(process.env.HOME, "workspace"),
      agentDir: path.join(process.env.HOME, "agents/main")});
    const catalog = await runtime.getCatalog();
    assert.equal(catalog.diagnostics?.length ?? 0, 0, JSON.stringify(catalog.diagnostics));
    assert.ok(catalog.tools.some(tool => tool.serverName === "general" && tool.toolName === "fixture_read"));
    const reply = await runtime.callTool("general", "fixture_read", {});
    assert.notEqual(reply.isError, true);
    assert.equal(reply.content[0].text, "private MCP works");
    assert.ok(requests.includes("initialize") && requests.includes("tools/call"));
  } finally {
    if (runtime) {
      await runtime.dispose();
      await runtime.joinCleanup?.();
    }
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
