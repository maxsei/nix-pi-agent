# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "starlette",
#   "uvicorn",
#   "websockets",
#   "datastar-py",
# ]
# ///
"""Web UI for driving the pi-agent over its WebSocket RPC bridge.

Serves a single page (Datastar-powered) where a user types a prompt and
watches the agent's streamed output live.
"""
import asyncio
import json
import os

import uvicorn
import websockets
from datastar_py import ServerSentEventGenerator as SSE
from datastar_py.starlette import DatastarResponse, read_signals
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Route

PI_AGENT_URL = os.environ.get("PI_AGENT_URL", "ws://pi-agent:8765")
HOST = os.environ.get("ORCHESTRATOR_HOST", "0.0.0.0")
PORT = int(os.environ.get("ORCHESTRATOR_PORT", "8080"))

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>pi-agent orchestrator</title>
<script type="module" src="https://cdn.jsdelivr.net/gh/starfederation/datastar@v1.0.0-RC.7/bundles/datastar.js"></script>
<style>
  body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem; }
  textarea { width: 100%; height: 6rem; font: inherit; }
  button { margin-top: 0.5rem; padding: 0.5rem 1rem; margin-right: 0.5rem; }
  #log { white-space: pre-wrap; background: #111; color: #0f0; padding: 1rem; margin-top: 1rem;
         min-height: 10rem; max-height: 60vh; overflow-y: auto; font-family: monospace; }
</style>
</head>
<body data-signals="{prompt: '', running: false}">
  <h1>pi-agent orchestrator</h1>
  <textarea data-bind="prompt" placeholder="Describe what you want the agent to build..."></textarea>
  <br>
  <button data-on:click="@post('/run')" data-attr="{disabled: $running}">Run</button>
  <button data-on:click="@post('/stop')" data-attr="{disabled: !$running}">Stop</button>
  <div id="log"></div>
</body>
</html>
"""


async def index(request: Request) -> HTMLResponse:
    return HTMLResponse(PAGE)


async def connect_with_retry(url: str, timeout: float = 60.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            return await websockets.connect(url, open_timeout=5)
        except OSError:
            if asyncio.get_event_loop().time() > deadline:
                raise RuntimeError(f"could not connect to {url} in time")
            await asyncio.sleep(1)


active_ws: websockets.WebSocketClientProtocol | None = None


async def run_events(prompt: str):
    global active_ws

    if active_ws is not None:
        yield SSE.patch_elements('<div id="log">agent is already running</div>')
        return

    yield SSE.patch_signals({"running": True})
    if not prompt:
        yield SSE.patch_elements('<div id="log">(empty prompt, nothing to do)</div>')
        yield SSE.patch_signals({"running": False})
        return

    yield SSE.patch_elements(f'<div id="log">connecting to pi-agent...\n</div>')

    log_lines: list[str] = []

    def render_log() -> str:
        escaped = "\n".join(log_lines)
        return f'<div id="log">{escaped}</div>'

    try:
        ws = await connect_with_retry(PI_AGENT_URL)
        active_ws = ws
        async with ws:
            await ws.send(json.dumps({
                "id": "task-1",
                "type": "prompt",
                "message": prompt,
            }))

            async for line in ws:
                log_lines.append(line)
                yield SSE.patch_elements(render_log())
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "agent_settled":
                    break
    except websockets.ConnectionClosed:
        log_lines.append("stopped")
        yield SSE.patch_elements(render_log())
    except Exception as exc:
        log_lines.append(f"error: {exc}")
        yield SSE.patch_elements(render_log())
    finally:
        active_ws = None

    yield SSE.patch_signals({"running": False})


async def run_route(request: Request):
    signals = await read_signals(request) or {}
    prompt = (signals.get("prompt") or "").strip()
    return DatastarResponse(run_events(prompt))


async def stop_route(request: Request):
    if active_ws is not None:
        await active_ws.send(json.dumps({"id": "stop-1", "type": "abort"}))
    return DatastarResponse(iter(()))


app = Starlette(routes=[
    Route("/", index),
    Route("/run", run_route, methods=["POST"]),
    Route("/stop", stop_route, methods=["POST"]),
])


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
