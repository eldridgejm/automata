"""Public API for working with an automata project."""

import datetime
from pathlib import Path

from . import materials
from ._extension import apply_extension
from .config import CONFIGURATION_FILENAME, Config, load_extensions, read_config
from .exceptions import Error
from .hooks import Hooks, PublishPreHookArgs, PublishPostHookArgs, PublisherRegistryArgs
from .materials import (
    BuiltArtifact,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
    find_parent_collection,
)
from .website import generate as _generate_website


def _load_content_directory(
    content_directory: Path,
    materials_directory: Path,
    no_render_suffix: str | None = ".no_render",
) -> tuple[dict[str, str], dict[str, str | bytes]]:
    """Load pages and static content from a content directory.

    Walks the content directory (skipping the materials subdirectory) and
    separates files into pages (``.md`` and ``.html``) and static content
    (everything else).

    Parameters
    ----------
    content_directory : Path
        The directory containing pages and static files.
    materials_directory : Path
        The materials subdirectory to skip.
    no_render_suffix : str | None
        Files with this suffix are treated as static content with the suffix
        stripped from the output path.

    Returns
    -------
    tuple[dict[str, str], dict[str, str | bytes]]
        A tuple of (pages, static_content).

    """
    pages: dict[str, str] = {}
    static_content: dict[str, str | bytes] = {}

    for dirpath, dirnames, filenames in content_directory.walk(top_down=True):
        dirpath = Path(dirpath)

        # skip the materials directory
        if dirpath == materials_directory:
            dirnames.clear()
            continue

        for filename in filenames:
            file_path = dirpath / filename
            relative = str(file_path.relative_to(content_directory))

            # handle no_render_suffix: treat as static, strip suffix
            if (
                no_render_suffix
                and file_path.suffix.lower() == no_render_suffix
                and len(file_path.suffixes) > 1
            ):
                output_key = str(
                    file_path.relative_to(content_directory).with_suffix("")
                )
                static_content[output_key] = file_path.read_bytes()
            elif file_path.suffix.lower() in (".md", ".html"):
                # pages keys are output paths; .md files become .html
                output_key = str(
                    file_path.relative_to(content_directory).with_suffix(".html")
                )
                pages[output_key] = file_path.read_text()
            else:
                static_content[relative] = file_path.read_bytes()

    return pages, static_content


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

    def publish(
        self,
        target: str | None = None,
        current_time: datetime.datetime | None = None,
    ) -> None:
        """Run the full pipeline and deploy the built site.

        Calls :meth:`generate` first, then invokes the configured publish
        strategy (or strategies).

        Parameters
        ----------
        target : str | None
            Name of a specific publish target to run. If *None*, all
            configured targets are run in order.
        current_time : datetime.datetime | None
            The current time for release-time checks and scheduling.
            If *None*, uses the system time.

        Raises
        ------
        automata.exceptions.Error
            If no publish configurations are present, a target name is
            unknown, or a strategy is unknown.

        """
        self.generate(current_time=current_time)

        if not self.config.publish:
            raise Error("No 'publish' entries found in automata.yaml.")

        if target is not None:
            if target not in self.config.publish:
                available = ", ".join(sorted(self.config.publish))
                raise Error(
                    f"Unknown publish target: {target!r}. "
                    f"Available: {available}"
                )
            targets = {target: self.config.publish[target]}
        else:
            targets = self.config.publish

        # Build publisher registry: start with builtins, let extensions add more
        from . import publish as publish_module

        initial = publish_module.registry.all()
        registry = self.hooks.on_register_publishers(
            PublisherRegistryArgs(publishers=initial)
        )

        build_dir = self.path / self.config.website.build_directory

        for name, entry in targets.items():
            strategy_name = entry["strategy"]
            strategy_config = entry.get("config", {})

            publisher = registry.publishers.get(strategy_name)
            if publisher is None:
                available = ", ".join(sorted(registry.publishers)) or "(none)"
                raise Error(
                    f"Unknown publish strategy: {strategy_name!r}. "
                    f"Available: {available}"
                )

            self.hooks.on_publish_pre(
                PublishPreHookArgs(build_directory=build_dir, strategy=strategy_name)
            )

            publisher(build_dir, strategy_config)

            self.hooks.on_publish_post(
                PublishPostHookArgs(build_directory=build_dir, strategy=strategy_name)
            )

    # --- individual steps ---

    def discover(self) -> Universe[UnbuiltArtifact]:
        """Discover materials from the project directory.

        Discovers materials from the filesystem and merges any inline
        materials defined in ``automata.yaml``.

        Returns
        -------
        Universe[UnbuiltArtifact]
            The discovered, unbuilt materials universe.

        """
        universe = materials.discover(
            self.path, vars=self.config.vars, hooks=self.hooks
        )

        if self.config.materials:
            inline = materials.discover_inline(
                self.config.materials, self.path, vars=self.config.vars
            )
            universe = inline.merge(universe)

        return universe

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
        return materials.build(
            universe, current_time=current_time, hooks=self.hooks, **kwargs
        )

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

        exported = materials.export(
            universe, outdir=build_dir, prefix=prefix, hooks=self.hooks
        )

        materials_json = materials_output_dir / "materials.json"
        materials_json.parent.mkdir(parents=True, exist_ok=True)
        materials_json.write_text(materials.serialize(exported))

        return exported

    def generate_website(
        self, current_time: datetime.datetime | None = None
    ) -> None:
        """Generate the website from exported materials.

        Loads pages and static content from the content directory and passes
        them to the generation pipeline. Assumes materials have already been
        exported via :meth:`export`.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The current time for date-based rendering logic. If *None*,
            uses the system time.

        """
        current_time = current_time or datetime.datetime.now()
        build_dir = self.path / self.config.website.build_directory
        materials_output_dir = build_dir / self.config.website.materials_directory_name
        content_dir = self.path / self.config.website.content_directory

        pages, static_content = _load_content_directory(
            content_dir,
            materials_output_dir,
            no_render_suffix=self.config.website.no_render_suffix,
        )

        _generate_website(
            build_dir,
            materials_output_dir,
            pages=pages,
            static_content=static_content,
            vars=self.config.vars,
            current_time=current_time,
            hooks=self.hooks,
            base_path=self.config.website.base_path,
            materials_directory_name=self.config.website.materials_directory_name,
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
