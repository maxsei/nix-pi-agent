{ pkgs }:

let
  pythonEnv = pkgs.python3.withPackages (ps: [ ps.websockets ]);

  script = pkgs.runCommand "orchestrator-py" { } ''
    mkdir -p $out/bin
    cp ${./orchestrator.py} $out/bin/orchestrator.py
    chmod +x $out/bin/orchestrator.py
  '';

  entrypoint = pkgs.writeShellScriptBin "orchestrator-entrypoint" ''
    exec ${pythonEnv}/bin/python3 ${script}/bin/orchestrator.py
  '';
in
pkgs.dockerTools.buildLayeredImage {
  name = "orchestrator";
  tag = "latest";

  contents = [
    pythonEnv
    pkgs.coreutils
    script
    entrypoint
  ];

  config = {
    Cmd = [ "${entrypoint}/bin/orchestrator-entrypoint" ];
  };
}
