"""Public API for working with an automata project."""

import datetime
from pathlib import Path

from . import materials
from ._extension import apply_extension
from .config import CONFIGURATION_FILENAME, Config, load_extensions, read_config
from .hooks import Hooks
from .materials import (
    BuiltArtifact,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
    find_parent_collection,
)
from .website import generate as _generate_website


class Automata:
    """A handle to an automata project.

    The constructor reads the project configuration and loads extensions.
    Individual pipeline steps are exposed as stateless methods that take
    input and return output. The :meth:`generate` convenience method runs
    the full pipeline.

    Parameters
    ----------
    path : Path | None
        Path to the project directory (must contain ``automata.yaml``).
        If *None*, uses the current working directory.

    Examples
    --------
    Full pipeline::

        project = Automata()
        project.generate()

    Step by step::

        project = Automata()
        materials = project.discover()
        materials = project.build_materials(materials)
        project.export(materials)
        project.generate_website()

    """

    def __init__(self, path: Path | None = None):
        if path is None:
            path = Path.cwd()
        self.path: Path = path
        self.config: Config = read_config(path / CONFIGURATION_FILENAME)
        self.hooks: Hooks = Hooks()
        for ext in load_extensions(self.config, cwd=path):
            apply_extension(ext, self.hooks)

    # --- full pipeline ---

    def generate(self, current_time: datetime.datetime | None = None) -> None:
        """Run the full pipeline: discover, build, export, and generate website.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The current time for release-time checks and scheduling.
            If *None*, uses the system time.

        """
        current_time = current_time or datetime.datetime.now()
        discovered = self.discover()
        built = self.build_materials(discovered, current_time=current_time)
        self.export(built)
        self.generate_website(current_time=current_time)

    # --- individual steps ---

    def discover(self) -> Universe[UnbuiltArtifact]:
        """Discover materials from the project directory.

        Returns
        -------
        Universe[UnbuiltArtifact]
            The discovered, unbuilt materials universe.

        """
        return materials.discover(self.path, vars=self.config.vars)

    def build_materials(
        self,
        universe: Universe[UnbuiltArtifact],
        current_time: datetime.datetime | None = None,
        **kwargs,
    ) -> Universe[BuiltArtifact]:
        """Build materials by running recipes and checking release times.

        Parameters
        ----------
        universe : Universe[UnbuiltArtifact]
            The discovered materials to build.
        current_time : datetime.datetime | None
            The current time for release-time checks. If *None*, uses the
            system time.
        **kwargs
            Additional keyword arguments passed to :func:`automata.materials.build`
            (e.g., ``ignore_release_time``, ``ignore_ready``).

        Returns
        -------
        Universe[BuiltArtifact]
            The built materials universe.

        """
        current_time = current_time or datetime.datetime.now()
        return materials.build(universe, current_time=current_time, **kwargs)

    def export(
        self, universe: Universe[BuiltArtifact]
    ) -> Universe[ExportedArtifact]:
        """Export built materials to the build directory.

        Writes artifact files and ``materials.json`` to the build directory.

        Parameters
        ----------
        universe : Universe[BuiltArtifact]
            The built materials to export.

        Returns
        -------
        Universe[ExportedArtifact]
            The exported materials universe.

        """
        build_dir = self.path / self.config.website.build_directory
        prefix = self.config.website.materials_directory_name
        materials_output_dir = build_dir / prefix

        exported = materials.export(universe, outdir=build_dir, prefix=prefix)

        materials_json = materials_output_dir / "materials.json"
        materials_json.parent.mkdir(parents=True, exist_ok=True)
        materials_json.write_text(materials.serialize(exported))

        return exported

    def generate_website(
        self, current_time: datetime.datetime | None = None
    ) -> None:
        """Generate the website from exported materials.

        Assumes materials have already been exported via :meth:`export`.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The current time for date-based rendering logic. If *None*,
            uses the system time.

        """
        current_time = current_time or datetime.datetime.now()
        build_dir = self.path / self.config.website.build_directory
        materials_output_dir = build_dir / self.config.website.materials_directory_name

        _generate_website(
            self.config.website,
            materials_output_dir,
            self.config.vars,
            cwd=self.path,
            current_time=current_time,
            hooks=self.hooks,
        )

    def resolve(self, path: Path) -> Publication[UnbuiltArtifact]:
        """Resolve a publication.yaml file.

        Finds the parent collection by searching upward for
        ``collection.yaml``, discovers from there, and extracts the
        specific publication.

        Parameters
        ----------
        path : Path
            Path to the ``publication.yaml`` file.

        Returns
        -------
        Publication[UnbuiltArtifact]
            The resolved publication.

        """
        path = path.resolve()
        pub_dir = path.parent
        collection_dir = find_parent_collection(pub_dir)

        if collection_dir is not None:
            universe = materials.discover(collection_dir, vars=self.config.vars)
            collection = universe.collections["."]
            pub_key = str(pub_dir.relative_to(collection_dir))
            return collection.publications[pub_key]
        else:
            universe = materials.discover(pub_dir, vars=self.config.vars)
            return universe.collections["default"].publications["."]
