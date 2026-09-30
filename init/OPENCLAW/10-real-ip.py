#!/usr/bin/env python3
"""Apply the optional real-IP setting after older ephemeral generators run."""

import json
import os
import tempfile
from pathlib import Path


def first(*names):
    return next((os.environ[name].strip() for name in names if os.environ.get(name, "").strip()), "")


value = first("OPENCLAW_ALLOW_REAL_IP_FALLBACK").lower()
if not value:
    raise SystemExit(0)
if value not in {"1", "true", "yes", "on", "0", "false", "no", "off"}:
    raise SystemExit("OPENCLAW_ALLOW_REAL_IP_FALLBACK must be a boolean value")
enabled = value in {"1", "true", "yes", "on"}
raw = first("OPENCLAW_CONFIG", "OPENCLAW_CONFIG_PATH")
if not raw:
    state = first("OPENCLAW_STATE_DIR", "OPENCLAW_HOME")
    raw = str(Path(state or str(Path(first("HOME") or "/root") / ".openclaw")) / "openclaw.json")
if raw == "~" or raw.startswith("~/"):
    raw = (first("HOME") or "/root") + raw[1:]
path = Path(raw).resolve()
config = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(config, dict) or not isinstance(config.get("gateway", {}), dict):
    raise SystemExit("OpenClaw configuration and gateway must be JSON objects")
gateway = config.get("gateway", {})
if enabled and gateway.get("allowRealIpFallback") is True:
    raise SystemExit(0)
if not enabled and "allowRealIpFallback" not in gateway:
    raise SystemExit(0)
if enabled:
    gateway["allowRealIpFallback"] = True
else:
    gateway.pop("allowRealIpFallback", None)
config["gateway"] = gateway
with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
    temporary = Path(stream.name)
    try:
        json.dump(config, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
