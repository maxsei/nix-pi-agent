{ pkgs }:

let
  pythonEnv = pkgs.python3.withPackages (ps: [ ps.websockets ]);

  bridge = pkgs.runCommand "pi-ws-bridge-py" { } ''
    mkdir -p $out/bin
    cp ${./pi_ws_bridge.py} $out/bin/pi_ws_bridge.py
  '';

  entrypoint = pkgs.writeShellScriptBin "pi-agent-entrypoint" ''
    exec ${pythonEnv}/bin/python3 ${bridge}/bin/pi_ws_bridge.py
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "pi-agent";
  tag = "latest";

  contents = [
    pkgs.pi-coding-agent
    pkgs.nix
    pkgs.bashInteractive
    pkgs.coreutils
    pkgs.cacert
    pkgs.gitMinimal
    pythonEnv
    entrypoint
  ];

  config = {
    Cmd = [ "${entrypoint}/bin/pi-agent-entrypoint" ];
    WorkingDir = "/workspace";
    ExposedPorts = {
      "8765/tcp" = { };
    };
    Env = [
      "NIX_CONFIG=experimental-features = nix-command flakes\nextra-substituters = http://cachix-proxy:5000\nextra-trusted-public-keys = cachix-proxy:0000000000000000000000000000000000000000000=\n"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
      "PI_SYSTEM_PROMPT_EXTRA=You may install any additional tools you need using nix (e.g. `nix shell nixpkgs#<pkg>` or `nix profile install nixpkgs#<pkg>`). Do not use apt/apk/pip install for system tools; this image is Nix-only."
    ];
  };
}
