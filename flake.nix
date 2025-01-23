{
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
  inputs.flake-parts.url = "github:hercules-ci/flake-parts";

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
        };
        devShells.default = python.env;
        formatter = pkgs.alejandra;
      };
    };
}
