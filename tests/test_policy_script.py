from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


POLICY_SCRIPT = (
    Path(__file__).resolve().parents[1] / "container" / "runtime" / "yolo.sh"
)


class TrustedPolicyScriptTests(unittest.TestCase):
    def test_policy_uses_one_approval_sync_and_one_config_patch(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            binary = root / "bin" / "openclaw"
            binary.parent.mkdir()
            binary.write_text(
                """#!/usr/bin/env bash
set -euo pipefail
printf '%s\\n' "$*" >> "$OPENCLAW_FAKE_CALLS"
if [[ "$1 $2" == "config patch" ]]; then
  cat > "$OPENCLAW_FAKE_PATCH"
fi
""",
                encoding="utf-8",
            )
            binary.chmod(0o755)
            calls = root / "calls"
            patch = root / "patch.json"
            environ = dict(os.environ)
            environ.update(
                {
                    "PATH": f"{binary.parent}:{environ['PATH']}",
                    "OPENCLAW_FAKE_CALLS": str(calls),
                    "OPENCLAW_FAKE_PATCH": str(patch),
                }
            )

            subprocess.run(
                ["bash", str(POLICY_SCRIPT)],
                check=True,
                env=environ,
            )

            self.assertEqual(
                calls.read_text(encoding="utf-8").splitlines(),
                ["exec-policy preset yolo", "config patch --stdin"],
            )
            self.assertEqual(
                json.loads(patch.read_text(encoding="utf-8")),
                {
                    "tools": {
                        "exec": {
                            "mode": "full",
                            "security": None,
                            "ask": None,
                        }
                    }
                },
            )


if __name__ == "__main__":
    unittest.main()
