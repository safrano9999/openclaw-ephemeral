#!/usr/bin/env python3
"""Refresh the OpenAI model catalog only for the pinned OpenClaw runtime."""

import re
import subprocess
from pathlib import Path


EXPECTED_VERSION = "2026.9.4"
MARKER = Path("/run/openclaw-ephemeral-openai-refresh.done")
VERSION_LINE = re.compile(r"^OpenClaw (?P<version>\d+\.\d+\.\d+) \([^\n]+\)$")


def main() -> int:
    if MARKER.exists():
        print("OpenAI model refresh skipped: already completed for this boot")
        return 0
    result = subprocess.run(
        ["openclaw", "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    line = result.stdout.strip()
    match = VERSION_LINE.fullmatch(line)
    if match is None or match.group("version") != EXPECTED_VERSION:
        print(f"OpenAI model refresh skipped: expected OpenClaw {EXPECTED_VERSION}, got {line or 'unknown'}")
        return 0
    print(f"OpenAI model refresh: OpenClaw {EXPECTED_VERSION}")
    subprocess.run(
        ["openclaw", "models", "list", "--provider", "openai", "--refresh"],
        check=True,
    )
    MARKER.touch()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
