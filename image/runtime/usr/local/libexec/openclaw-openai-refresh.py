#!/usr/bin/env python3
"""Publish one native catalog refresh for all agents before the init hooks."""

import json
import os
import re
import subprocess
import sys


EXPECTED_VERSION = "2026.9.4"
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


def main() -> int:
    result = run_openclaw(["--version"])
    if result is None:
        return 1
    line = result.stdout.strip()
    match = VERSION_LINE.fullmatch(line)
    if match is None or match.group("version") != EXPECTED_VERSION:
        print(f"Catalog refresh requires OpenClaw {EXPECTED_VERSION}; got {line or 'unknown'}")
        return 1
    # Replaced: openclaw models list --provider openai --refresh
    # --provider filters output; it does not publish catalogs to every agent.
    print("Refreshing and publishing model catalogs for all agents", flush=True)
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
