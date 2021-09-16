{
  description = "Python package for automating the publication of course materials.";

  inputs.nixpkgs.url = github:NixOS/nixpkgs/20.03;

  outputs = { self, nixpkgs }: 
    let
      supportedSystems = [ "x86_64-linux" "x86_64-darwin" ];
      forAllSystems = f: nixpkgs.lib.genAttrs supportedSystems (system: f system);
    in
      {
        automata = forAllSystems (system:
          with import nixpkgs { system = "${system}"; };

            python3Packages.buildPythonPackage {
              name = "automata";
              src = ./.;
              propagatedBuildInputs = with python3Packages; [ pyyaml cerberus jinja2 ];
              nativeBuildInputs = with python3Packages; [ pytest black ipython sphinx sphinx_rtd_theme ];
            }

          );

        defaultPackage = forAllSystems (system:
            self.automata.${system}
          );
      };

}
