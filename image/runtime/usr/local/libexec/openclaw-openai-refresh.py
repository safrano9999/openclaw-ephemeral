#!/usr/bin/env python3
"""Publish one native catalog refresh for all agents before the init hooks."""

import json
import re
import subprocess


EXPECTED_VERSION = "2026.9.4"
VERSION_LINE = re.compile(r"^OpenClaw (?P<version>\d+\.\d+\.\d+) \([^\n]+\)$")


def main() -> int:
    result = subprocess.run(
        ["openclaw", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    line = result.stdout.strip()
    match = VERSION_LINE.fullmatch(line)
    if match is None or match.group("version") != EXPECTED_VERSION:
        print(f"Catalog refresh requires OpenClaw {EXPECTED_VERSION}; got {line or 'unknown'}")
        return 1
    # Replaced: openclaw models list --provider openai --refresh
    # --provider filters output; it does not publish catalogs to every agent.
    print("Refreshing and publishing model catalogs for all agents", flush=True)
    result = subprocess.run(
        ["openclaw", "gateway", "call", "ephemeral.models.refresh",
         "--json", "--timeout", "420000"],
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(result.stdout)
    for agent in result["agents"]:
        print(f"Agent {agent['agentId']}: {agent['models']} catalog models", flush=True)
    print(f"Injected catalog acquisitions: {result['injectedCatalogAcquisitions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
