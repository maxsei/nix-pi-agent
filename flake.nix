{
  description = "pi-agent + orchestrator + cachix-proxy docker-compose stack";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    { nixpkgs, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };

        pi-agent-image = import ./service/pi-agent { inherit pkgs; };
        orchestrator-image = import ./service/orchestrator { inherit pkgs; };
        cachix-proxy-image = import ./service/cachix-proxy { inherit pkgs; };

        composeSpec = {
          services = {
            cachix-proxy = {
              image = "cachix-proxy:latest";
              pull_policy = "never";
              volumes = [
                "/nix/store:/nix/store:ro"
                "/nix/var/nix/db:/nix/var/nix/db"
                "cachix-proxy-keys:/var/lib/cachix-proxy"
              ];
              environment = {
                CACHIX_AUTH_TOKEN = "\${CACHIX_AUTH_TOKEN:-}";
                CACHIX_CACHE_NAME = "\${CACHIX_CACHE_NAME:-}";
              };
              ports = [ "5000:5000" ];
            };

            pi-agent = {
              image = "pi-agent:latest";
              pull_policy = "never";
              depends_on = [ "cachix-proxy" ];
              volumes = [ "./output:/workspace" ];
              expose = [ "8765" ];
              environment = {
                ANTHROPIC_API_KEY = "\${ANTHROPIC_API_KEY}";
              };
            };

            orchestrator = {
              image = "orchestrator:latest";
              pull_policy = "never";
              depends_on = [ "pi-agent" ];
              environment = {
                PI_AGENT_URL = "ws://pi-agent:8765";
              };
            };
          };

          volumes = {
            cachix-proxy-keys = { };
          };
        };

        docker-compose-yaml = (pkgs.formats.yaml { }).generate "docker-compose.yml" composeSpec;

        upScript = pkgs.writeShellScriptBin "up" ''
          set -eu
          ${pkgs.docker}/bin/docker load < ${pi-agent-image}
          ${pkgs.docker}/bin/docker load < ${orchestrator-image}
          ${pkgs.docker}/bin/docker load < ${cachix-proxy-image}
          cp --no-preserve=mode ${docker-compose-yaml} docker-compose.yml
          exec ${pkgs.sops}/bin/sops exec-env secrets.env \
            '${pkgs.docker-compose}/bin/docker-compose -f docker-compose.yml up '"$*"
        '';

        downScript = pkgs.writeShellScriptBin "down" ''
          set -eu
          ${pkgs.docker-compose}/bin/docker-compose -f docker-compose.yml down "$@"
        '';
      in
      {
        packages = {
          default = docker-compose-yaml;
          inherit
            pi-agent-image
            orchestrator-image
            cachix-proxy-image
            docker-compose-yaml
            ;
        };

        apps.up = {
          type = "app";
          program = "${upScript}/bin/up";
        };

        apps.down = {
          type = "app";
          program = "${downScript}/bin/down";
        };
      }
    );
}
