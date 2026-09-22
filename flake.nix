{
  description = "Python package for automating the publication of course materials.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/21.11;

  inputs.dictconfig.url = github:eldridgejm/dictconfig/master;
  inputs.dictconfig.inputs.nixpkgs.follows = "nixpkgs";

  outputs = { self, nixpkgs, dictconfig }:
    let
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
    in
      {
        automata = forAllSystems (system:
          with import nixpkgs { system = "${system}"; };

            python3Packages.buildPythonPackage {
              name = "automata";
              src = ./.;
              pyproject = true;
              build-system = [ python3Packages.setuptools ];
              propagatedBuildInputs = with python3Packages; [ 
                pyyaml
                markdown
                jinja2
                dictconfig.outputs.defaultPackage.${system}
              ];
              nativeBuildInputs = (with python3Packages; [ pytest black ipython sphinx lxml ]) ++ [ (python3Packages.sphinx-rtd-theme or python3Packages.sphinx_rtd_theme) ];
              doCheck = false;
            }

          );

        defaultPackage = forAllSystems (system:
            self.automata.${system}
          );
      };

}
