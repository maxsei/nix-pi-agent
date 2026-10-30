{ pkgs }:

let
  entrypoint = pkgs.writeShellScriptBin "cachix-proxy-entrypoint" ''
    set -eu
    export NIX_REMOTE=daemon
    if [ -n "''${CACHIX_AUTH_TOKEN:-}" ] && [ -n "''${CACHIX_CACHE_NAME:-}" ]; then
      ${pkgs.cachix}/bin/cachix authtoken "$CACHIX_AUTH_TOKEN"
      ${pkgs.cachix}/bin/cachix use "$CACHIX_CACHE_NAME"
      ${pkgs.cachix}/bin/cachix watch-store "$CACHIX_CACHE_NAME" &
    fi
    export NIX_SECRET_KEY_FILE=/var/lib/cachix-proxy/cache-priv-key.pem
    mkdir -p /var/lib/cachix-proxy
    if [ ! -f "$NIX_SECRET_KEY_FILE" ]; then
      ${pkgs.nix}/bin/nix-store --generate-binary-cache-key cachix-proxy "$NIX_SECRET_KEY_FILE" /var/lib/cachix-proxy/cache-pub-key.pem
    fi
    exec ${pkgs.nix-serve}/bin/nix-serve --listen 0.0.0.0:5000
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "cachix-proxy";
  tag = "latest";

  contents = with pkgs; [
    cachix
    nix-serve
    nix
    bashInteractive
    coreutils
  ];

  config = {
    Cmd = [ "${entrypoint}/bin/cachix-proxy-entrypoint" ];
    ExposedPorts = {
      "5000/tcp" = { };
    };
  };
}
