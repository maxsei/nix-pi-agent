{ pkgs }:

let
  script = pkgs.runCommand "orchestrator-py" { } ''
    mkdir -p $out/bin
    cp ${./orchestrator.py} $out/bin/orchestrator.py
    chmod +x $out/bin/orchestrator.py
  '';

  entrypoint = pkgs.writeShellScriptBin "orchestrator-entrypoint" ''
    exec ${pkgs.uv}/bin/uv run --no-project ${script}/bin/orchestrator.py
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "orchestrator";
  tag = "latest";

  contents = [
    pkgs.uv
    pkgs.python3
    pkgs.cacert
    pkgs.coreutils
    script
    entrypoint
  ];

  config = {
    Cmd = [ "${entrypoint}/bin/orchestrator-entrypoint" ];
    ExposedPorts = {
      "8080/tcp" = { };
    };
    Env = [
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    ];
  };
}
