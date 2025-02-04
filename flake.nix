{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-parts.url = "github:hercules-ci/flake-parts";
  inputs.nartool.url = "github:markuskowa/nartool";
  inputs.nartool.inputs.nixpkgs.follows = "nixpkgs";

  outputs = inputs @ {
    self,
    nixpkgs,
    flake-parts,
    ...
  }:
    flake-parts.lib.mkFlake {inherit inputs;} {
      systems = ["x86_64-linux" "aarch64-linux" "aarch64-darwin" "x86_64-darwin"];
      perSystem = {
        pkgs,
        config,
        ...
      }: let
        python =
          pkgs.python3.withPackages
          (ps:
            with ps; [
              pygit2
              boto3
              boto3-stubs
              ipython
              (
                buildPythonPackage rec {
                  name = "nartool";
                  version = "0.0.2";

                  format = "pyproject";

                  src = inputs.nartool;
                  nativeBuildInputs = [setuptools];
                  propagatedBuildInputs = [requests];
                }
              )
            ]);
      in {
        packages = rec {
          default = nix-repo-builder;
          nix-repo-builder = pkgs.writeShellApplication {
            name = "nix-repo-builder";
            runtimeInputs = [
              python
            ];
            text = ''
              ${./.}/nix-repo-builder.py
            '';
          };
          nix-s3-garbage-collector = pkgs.writeShellApplication {
            name = "nix-s3-garbage-collector";
            runtimeInputs = [
              python
            ];
            text = ''
              ${./.}/nix-s3-garbage-collector.py
            '';
          };
        };
        devShells.default = python.env;
        formatter = pkgs.alejandra;
      };
    };
}
