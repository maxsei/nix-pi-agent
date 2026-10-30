# CLAUDE.md

Stack: `pi-agent` (WebSocket bridge around the `pi` CLI's stdio RPC mode) +
`orchestrator` (Starlette/Datastar web UI) + `cachix-proxy` (local binary
cache for Nix builds), composed via `docker-compose`, built with Nix.

## cachix-proxy / Nix store mounting

- Mounting only `/nix/store` read-only into the container breaks Nix: any
  Nix command (even read-only ones like `nix-serve`) tries to remount the
  store writable to take a lock, failing with
  `error: remounting "/nix/store" writable: Operation not permitted`.
- Do NOT fix this with `cap_add: SYS_ADMIN` or `privileged: true` — that's a
  real container-escape risk and was explicitly rejected.
- Setting `NIX_STATE_DIR` elsewhere does NOT fix it — `nix-serve` still opens
  a local store at `/nix/store` and hits the same remount check.
- The working fix (current `service/cachix-proxy/default.nix`): bind-mount
  the whole host `/nix` dir (not just `/nix/store`) `:ro`, and set
  `NIX_REMOTE=daemon` so Nix talks to the host's nix-daemon socket
  (`/nix/var/nix/daemon-socket/socket`) instead of managing the store
  itself. Requires the host to run Nix in multi-user/daemon mode.

## `pi` CLI RPC protocol (used by `service/pi-agent/pi_ws_bridge.py`)

- `pi --mode rpc` is stdio JSONL only — there's no native network RPC, which
  is why the WebSocket bridge exists.
- The real completion/terminal event is
  `{"type": "agent_settled", "aborted": bool}`. There is no `"result"` or
  `"idle"` event type — don't check for those.
- `prompt`'s immediate ack is `{"type":"response","command":"prompt",...}`
  — that's just an ack, not a completion signal.
- To stop a run, send `{"type": "abort"}` over the live WebSocket (keeps the
  session alive, yields a proper `agent_settled {aborted: true}`). Closing
  the socket outright kills the subprocess via the bridge's `finally` block
  — a cruder, different behavior.
- `PI_SYSTEM_PROMPT_EXTRA` is baked in at subprocess-spawn time via
  `--append-system-prompt`, not per-message — passing it per-message was
  tried and reverted.
- `PI_MODEL` (default `sonnet`) is passed straight through as `--model`;
  this hasn't been independently verified against the exact model-string
  format the installed `pi` version expects.

## Secrets

- Plain `sops` CLI + `.sops.yaml` + `secrets.env` (age-encrypted dotenv),
  not sops-nix — sops-nix was rejected as overkill for a portable
  docker-compose stack with no systemd activation step.
- Age key already exists at `~/.config/sops/age/keys.txt` (default sops
  lookup path) — don't create a new one.
- Never read `secrets.env` directly, it's ciphertext. Decrypt via
  `sops exec-env secrets.env '<cmd>'`, which injects plaintext straight into
  the child process env; docker-compose's `${VAR}` substitution picks it up
  from there. (An earlier `env_file:` pointing at the encrypted file, and a
  separate `exec-file` temp-file approach, were both tried and dropped.)

## Nix/Docker build flow

- Images build via `nix build .#<name>-image` then must be `docker load`ed —
  `docker-compose up` alone cannot build from Nix.
- `nix run .#up` wraps this: loads all three images, regenerates
  `docker-compose.yml` from the Nix-defined compose spec, then runs
  `sops exec-env secrets.env 'docker-compose up ...'`.
- Image tags are content-addressed, derived from each image derivation's
  real `imageName`/`imageTag` — not hardcoded `:latest` in the Nix logic
  (avoids stale-tag bugs). All three services use `pull_policy: never`, so
  images only ever come from local `docker load`.

## Orchestrator frontend

- Python (Starlette + `datastar-py`), run via `uv run` with PEP 723 inline
  script dependencies — deliberately not nix-packaged, to avoid needing
  `datastar-py`/`starlette`/`uvicorn`/`websockets` in nixpkgs.
- The repo's "datastar" skill covers Go/gomponents-datastar and does not
  apply to this Python integration.
