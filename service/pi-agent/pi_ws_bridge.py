#!/usr/bin/env python3
"""WebSocket front-end for pi's stdio RPC mode.

Each WebSocket connection spawns a fresh `pi --mode rpc` subprocess and
relays JSONL lines between the socket and the subprocess's stdin/stdout.
"""
import asyncio
import os
import sys

import websockets

SYSTEM_PROMPT_EXTRA = os.environ.get(
    "PI_SYSTEM_PROMPT_EXTRA",
    "You may install any additional tools you need using nix "
    "(e.g. `nix shell nixpkgs#<pkg>` or `nix profile install nixpkgs#<pkg>`). "
    "Do not use apt/apk/pip install for system tools; this image is Nix-only. "
    "Any artifacts you generate must be written into the /workspace directory.",
)
HOST = os.environ.get("PI_WS_HOST", "0.0.0.0")
PORT = int(os.environ.get("PI_WS_PORT", "8765"))
PI_MODEL = os.environ.get("PI_MODEL", "sonnet")


async def pump_stdout(proc: asyncio.subprocess.Process, ws) -> None:
    assert proc.stdout
    async for raw_line in proc.stdout:
        line = raw_line.decode(errors="replace").rstrip("\n")
        if line:
            await ws.send(line)


async def handler(ws) -> None:
    proc = await asyncio.create_subprocess_exec(
        "pi", "--mode", "rpc", "--no-session", "--approve",
        "--model", PI_MODEL,
        "--append-system-prompt", SYSTEM_PROMPT_EXTRA,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=sys.stderr,
    )
    assert proc.stdin

    pump_task = asyncio.create_task(pump_stdout(proc, ws))
    try:
        async for message in ws:
            proc.stdin.write(message.encode() + b"\n")
            await proc.stdin.drain()
    finally:
        pump_task.cancel()
        if proc.returncode is None:
            proc.terminate()
        await proc.wait()


async def main() -> None:
    async with websockets.serve(handler, HOST, PORT):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
