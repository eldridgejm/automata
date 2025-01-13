{
  description = "Automatically generate course webpages from annotated materials.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/nixos-24.11;

  inputs.dictconfig.url = github:eldridgejm/dictconfig/master;
  inputs.dictconfig.inputs.nixpkgs.follows = "nixpkgs";

  outputs = {
    self,
    nixpkgs,
    dictconfig,
  }: let
    supportedSystems = ["x86_64-linux" "x86_64-darwin" "aarch64-darwin"];
    forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
  in rec {
    automata = forAllSystems (
      system:
        with import nixpkgs {system = "${system}";};
          python3Packages.buildPythonPackage {
            name = "automata";
            src = ./.;
            format = "pyproject";
            propagatedBuildInputs = with python3Packages; [
              pyyaml
              markdown
              jinja2
              dictconfig.outputs.defaultPackage.${system}
            ];
            nativeBuildInputs = with python3Packages; [setuptools wheel pip];
            doCheck = false;
          }
    );

    devShell = forAllSystems (
      system:
        with import nixpkgs {
          system = "${system}";
          allowBroken = true;
        };
          mkShell {
            buildInputs = with python3Packages; [
              pytest
              sphinx
              sphinx_rtd_theme
              black
              ruff
              mypy

              # install gradelib package to 1) make sure it's installable, and
              # 2) to get its dependencies. But below we'll add it to PYTHONPATH
              # so we can develop it in place.
              automata.${system}
            ];

            shellHook = ''
              export PYTHONPATH="$(pwd)/src/:$PYTHONPATH"
            '';
          }
    );

    defaultPackage = forAllSystems (
      system:
        self.automata.${system}
    );
  };
}
