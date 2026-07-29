"""Command-line lifecycle for the ephemeral OpenClaw runtime."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from . import __version__
from .configuration import ConfigurationResult, configure
from .environment import (
    ConfigurationError,
    expand_api_key_aliases,
    integer,
    openclaw_command,
)

TRUSTED_POLICY_SCRIPT = "/usr/local/bin/openclaw-ephemeral-yolo"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openclaw-ephemeral.py",
        description=(
            "Rebuild OpenClaw configuration entirely from the process environment."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "mode",
        choices=("configure", "run", "restart"),
        help=(
            "configure only, configure then exec the gateway, or configure then "
            "restart the managed gateway"
        ),
    )
    return parser


def _report(result: ConfigurationResult, stream: Any) -> None:
    print(f"OpenClaw config rebuilt atomically: {result.path}", file=stream)
    print(f"OpenClaw primary model: {result.primary_model}", file=stream)
    print(
        "OpenClaw models discovered: "
        f"{result.native_model_count} native, "
        f"{result.openai_v1_model_count} across "
        f"{result.openai_v1_provider_count} OpenAI-v1 provider(s)",
        file=stream,
    )
    if result.telegram_configured:
        print("OpenClaw Telegram configured from an environment reference", file=stream)
    if result.note_full_mode:
        print("OpenClaw NOTE full mode enabled", file=stream)
    for warning in result.warnings:
        print(f"Warning: {warning}", file=stream)


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    runner: Callable[..., Any] = subprocess.run,
    execvpe: Callable[..., Any] = os.execvpe,
    opener: Callable[..., Any] | None = None,
    stdout: Any = sys.stdout,
    stderr: Any = sys.stderr,
) -> int:
    """Run one lifecycle mode with injectable process primitives for tests."""

    args = _parser().parse_args(argv)
    injected = dict(os.environ if environ is None else environ)
    try:
        if opener is None:
            result = configure(injected, runner=runner)
        else:
            result = configure(injected, runner=runner, opener=opener)
        _report(result, stdout)

        flush = getattr(stdout, "flush", None)
        if callable(flush):
            flush()
        runtime_env = expand_api_key_aliases(injected)
        runner(
            [TRUSTED_POLICY_SCRIPT],
            check=True,
            env=runtime_env,
        )
        if args.mode == "configure":
            return 0
        command = openclaw_command(runtime_env)
        if args.mode == "run":
            port = integer(
                runtime_env,
                "OPENCLAW_GATEWAY_PORT",
                default=18_789,
                maximum=65_535,
            )
            arguments = [
                *command,
                "gateway",
                "run",
                "--bind",
                "lan",
                "--port",
                str(port),
            ]
            if runtime_env.get("OPENCLAW_GATEWAY_TOKEN", "").strip():
                arguments.extend(("--auth", "token"))
            execvpe(arguments[0], arguments, runtime_env)
            raise RuntimeError("gateway exec unexpectedly returned")

        runner(
            [*command, "gateway", "restart"],
            check=True,
            env=runtime_env,
        )
        return 0
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
