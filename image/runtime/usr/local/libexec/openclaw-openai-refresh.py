#!/usr/bin/env python3
"""Publish one native catalog refresh for all agents before the init hooks."""

import json
import os
import re
import subprocess
import sys


SUPPORTED_VERSIONS = {"2026.9.4", "2026.11.3"}
VERSION_LINE = re.compile(r"^OpenClaw (?P<version>\d+\.\d+\.\d+) \([^\n]+\)$")


def redact(message: str) -> str:
    for name, raw in os.environ.items():
        if re.search(r"KEY|TOKEN|BEARER|SECRET|PASSWORD|CREDENTIAL", name, re.I):
            value = raw.strip().strip("\"'")
            if len(value) >= 4:
                message = message.replace(value, "[REDACTED]")
    message = re.sub(r"\bBearer\s+\S+", "Bearer [REDACTED]", message, flags=re.I)
    return re.sub(r"([?&](?:api[_-]?key|key|token|access_token|secret)=)[^&#\s]+",
                  r"\1[REDACTED]", message, flags=re.I)


def run_openclaw(args: list[str]):
    result = subprocess.run(["openclaw", *args], check=False, capture_output=True, text=True)
    if result.returncode:
        print(f"OpenClaw catalog command failed (exit {result.returncode})", file=sys.stderr, flush=True)
        for output in (result.stdout, result.stderr):
            if output:
                print(redact(output).rstrip(), file=sys.stderr, flush=True)
        return None
    return result


def refresh_native_catalogs() -> int:
    result = run_openclaw(["gateway", "call", "agents.list", "--json", "--timeout", "30000"])
    if result is None:
        return 1
    agents = json.loads(result.stdout)["agents"]
    if not agents:
        raise ValueError("Gateway returned no agents")
    for agent in agents:
        agent_id = agent["id"]
        result = run_openclaw([
            "gateway", "call", "models.list", "--params",
            json.dumps({"agentId": agent_id, "refresh": True, "view": "provider-config"}),
            "--json", "--timeout", "180000",
        ])
        if result is None:
            print(f"Catalog refresh failed for agent {agent_id}", flush=True)
            return 1
        catalog = json.loads(result.stdout)
        failures = [outcome for outcome in catalog.get("providerOutcomes", [])
                    if outcome.get("status") != "ready"]
        if failures or catalog.get("refreshFailed") or catalog.get("pendingProviders"):
            print(redact(f"Agent {agent_id}: provider discovery failed: {failures}"), flush=True)
            return 1
        print(f"Agent {agent_id}: {len(catalog['models'])} catalog models", flush=True)
    return 0


def main() -> int:
    result = run_openclaw(["--version"])
    if result is None:
        return 1
    line = result.stdout.strip()
    match = VERSION_LINE.fullmatch(line)
    if match is None or match.group("version") not in SUPPORTED_VERSIONS:
        print(f"Unsupported OpenClaw catalog refresh version: {line or 'unknown'}")
        return 1
    # Replaced: openclaw models list --provider openai --refresh
    # --provider filters output; it does not publish catalogs to every agent.
    print("Refreshing and publishing model catalogs for all agents", flush=True)
    if match.group("version") == "2026.11.3":
        # Run in the gateway's native ownership context. Importing its internal
        # publisher from a plugin captures host code without worker assets.
        return refresh_native_catalogs()
    result = run_openclaw(["gateway", "call", "ephemeral.models.refresh",
                           "--json", "--timeout", "420000"])
    if result is None:
        return 1
    result = json.loads(result.stdout)
    for agent in result["agents"]:
        print(f"Agent {agent['agentId']}: {agent['models']} catalog models", flush=True)
    print(f"Injected catalog acquisitions: {result['injectedCatalogAcquisitions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
