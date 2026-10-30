#!/usr/bin/env python3
"""Connects to the pi-agent's WebSocket RPC bridge to generate index.html."""
import asyncio
import json
import os
import sys

import websockets

PI_AGENT_URL = os.environ.get("PI_AGENT_URL", "ws://pi-agent:8765")
TASK = (
    "Create a plain index.html page at /workspace/index.html that is a "
    "brochure page for a digital advertising agency. Use only plain HTML/CSS "
    "(inline or a single <style> block in the <head>), no build tooling, no "
    "external frameworks or CDNs. Include a hero section, a services section, "
    "an about/why-us section, and a contact/footer section."
)


async def connect_with_retry(url: str, timeout: float = 60.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            return await websockets.connect(url, open_timeout=5)
        except OSError:
            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError(f"could not connect to {url} in time")
            await asyncio.sleep(1)


async def main() -> int:
    ws = await connect_with_retry(PI_AGENT_URL)
    async with ws:
        await ws.send(json.dumps({"id": "task-1", "type": "prompt", "message": TASK}))

        done = False
        async for line in ws:
            print(line, flush=True)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            state = event.get("state") or event.get("status")
            if event.get("type") in ("result", "idle") or state == "idle":
                done = True
                break

    if not done:
        print("warning: did not observe an explicit completion event", file=sys.stderr)

    print("done. check ./output/index.html on the host")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
