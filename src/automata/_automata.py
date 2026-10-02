"""Public API for working with an automata project."""

import datetime
import shutil
from pathlib import Path
from typing import cast

from . import materials
from .config import CONFIGURATION_FILENAME, Config, load_extensions, read_config
from .exceptions import Error
from .extensions import Extension, apply_extensions
from .hooks import (
    Hooks,
    PublisherRegistryArgs,
    PublishPostHookArgs,
    PublishPreHookArgs,
    RenderPreHookArgs,
)
from .materials import (
    BuiltArtifact,
    ExportedArtifact,
    Publication,
    UnbuiltArtifact,
    Universe,
    find_parent_collection,
)
from .materials._filter import ArtifactType, Predicate
from .website import render as _website_render


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
    input and return output. The :meth:`build` convenience method runs
    the full pipeline, and :meth:`publish` runs it and then deploys.

    Parameters
    ----------
    path : Path | None
        Path to the project directory (must contain ``automata.yaml``).
        If *None*, uses the current working directory.

    Examples
    --------
    Full pipeline::

        project = Automata()
        project.build()

    Step by step::

        project = Automata()
        project.clean_build_directory()
        materials = project.discover()
        materials = project.build_materials(materials)
        materials = project.export(materials)
        project.render_website(materials)

    """

    def __init__(self, path: Path | None = None):
        if path is None:
            path = Path.cwd()
        config_path = path / CONFIGURATION_FILENAME
        if not config_path.is_file():
            raise Error(
                f"No {CONFIGURATION_FILENAME} found in {path.absolute()}. The project "
                f"directory must contain {CONFIGURATION_FILENAME}."
            )
        self.path: Path = path
        self.config: Config = read_config(config_path)
        self.theme: Extension
        self.extensions: list[Extension]
        self.theme, self.extensions = load_extensions(self.config, cwd=path)
        self.hooks: Hooks = Hooks()
        apply_extensions([self.theme, *self.extensions], self.hooks)

    # --- full pipeline ---

    def build(self, current_time: datetime.datetime | None = None) -> None:
        """Run the full pipeline and produce the site in the build directory.

        Cleans the build directory (if ``website.clean_build_directory`` is
        true), then runs :meth:`discover`, :meth:`build_materials`,
        :meth:`export`, and :meth:`render_website`.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The current time for release-time checks and scheduling.
            If *None*, uses the system time.

        """
        current_time = current_time or datetime.datetime.now()
        if self.config.website.clean_build_directory:
            self.clean_build_directory()
        discovered = self.discover()
        built = self.build_materials(discovered, current_time=current_time)
        exported = self.export(built)
        self.render_website(exported, current_time=current_time)

    def clean_build_directory(self) -> None:
        """Empty the build directory, keeping top-level dot-entries.

        Called by :meth:`build` when ``website.clean_build_directory`` is
        true (the default), so that the build directory holds only what the
        current build produces. Entries whose names start with a dot (such as
        ``.git``) are kept.

        Raises
        ------
        automata.exceptions.Error
            If the build directory is, or contains, the project root or the
            content directory, lies inside the content directory, or contains
            an ``automata.yaml`` file. Nothing is deleted in that case.

        """
        build_dir = (self.path / self.config.website.build_directory).resolve()
        project_dir = self.path.resolve()
        content_dir = (self.path / self.config.website.content_directory).resolve()

        problem = None
        if project_dir.is_relative_to(build_dir):
            problem = "is or contains the project directory"
        elif content_dir.is_relative_to(build_dir):
            problem = "is or contains the content directory"
        elif build_dir.is_relative_to(content_dir):
            problem = "is inside the content directory"
        elif (build_dir / CONFIGURATION_FILENAME).exists():
            problem = f"contains an {CONFIGURATION_FILENAME} file"

        if problem is not None:
            raise Error(
                f'Refusing to clean build_directory "{build_dir}": it {problem}. '
                f"Change website.build_directory, or set "
                f"website.clean_build_directory to false."
            )

        if not build_dir.is_dir():
            return

        for entry in build_dir.iterdir():
            if entry.name.startswith("."):
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry)
            else:
                entry.unlink()

    def publish(
        self,
        target: str | None = None,
        current_time: datetime.datetime | None = None,
    ) -> list[str]:
        """Run the full pipeline and deploy the built site.

        Checks the target and strategy names, calls :meth:`build`, then invokes
        the configured publish strategy (or strategies).

        Parameters
        ----------
        target : str | None
            Name of a specific publish target to run. If *None*, all
            configured targets are run in order.
        current_time : datetime.datetime | None
            The current time for release-time checks and scheduling.
            If *None*, uses the system time.

        Returns
        -------
        list[str]
            The names of the targets published to, in order.

        Raises
        ------
        automata.exceptions.Error
            If no publish configurations are present, a target name is
            unknown, or a strategy is unknown.

        """
        if not self.config.publish:
            raise Error("No 'publish' entries found in automata.yaml.")

        if target is not None:
            if target not in self.config.publish:
                available = ", ".join(sorted(self.config.publish))
                raise Error(
                    f"Unknown publish target: {target!r}. Available: {available}"
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

        # check every strategy before building, so a typo fails fast
        publishers = {}
        for name, entry in targets.items():
            strategy_name = entry["strategy"]
            publisher = registry.publishers.get(strategy_name)
            if publisher is None:
                available = ", ".join(sorted(registry.publishers)) or "(none)"
                raise Error(
                    f"Unknown publish strategy: {strategy_name!r}. "
                    f"Available: {available}"
                )
            publishers[name] = publisher

        self.build(current_time=current_time)

        build_dir = self.path / self.config.website.build_directory

        for name, entry in targets.items():
            strategy_name = entry["strategy"]
            strategy_config = entry.get("config", {})

            self.hooks.on_publish_pre(
                PublishPreHookArgs(build_directory=build_dir, strategy=strategy_name)
            )

            publishers[name](build_dir, strategy_config, self.path)

            self.hooks.on_publish_post(
                PublishPostHookArgs(build_directory=build_dir, strategy=strategy_name)
            )

        return list(targets)

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
                self.config.materials,
                self.path,
                vars=self.config.vars,
                hooks=self.hooks,
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

        Artifacts whose release time is in the future, or that are not ready,
        are left out; the rest have their recipes run.

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

    def filter(
        self,
        universe: Universe[ArtifactType],
        predicate: Predicate,
        remove_empty_nodes: bool = False,
    ) -> Universe[ArtifactType]:
        """Select materials according to a predicate.

        A thin wrapper around :func:`automata.materials.filter` that fires
        this project's ``on_filter_hit`` and ``on_filter_miss`` hooks. Can be
        applied at any stage (discovered, built, or exported materials).

        Parameters
        ----------
        universe : Universe
            The materials to filter.
        predicate : Callable[[str, node], bool]
            Called with each node's key and the node; returns True to keep it.
        remove_empty_nodes : bool
            Whether to remove nodes left with no children. Default: False.

        Returns
        -------
        Universe
            A new universe with the rejected nodes removed.

        """
        return materials.filter(
            universe, predicate, remove_empty_nodes=remove_empty_nodes, hooks=self.hooks
        )

    def export(self, universe: Universe[BuiltArtifact]) -> Universe[ExportedArtifact]:
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

        exported = materials.export(
            universe, outdir=build_dir, prefix=prefix, hooks=self.hooks
        )

        materials_json = self._materials_json_path()
        materials_json.parent.mkdir(parents=True, exist_ok=True)
        materials_json.write_text(materials.serialize(exported))

        return exported

    def load_exported_materials(self) -> Universe[ExportedArtifact]:
        """Load the materials written by a previous :meth:`export`.

        Reads ``materials.json`` from the build directory. Useful for calling
        :meth:`render_website` without re-running the earlier steps::

            project.render_website(project.load_exported_materials())

        Returns
        -------
        Universe[ExportedArtifact]
            The exported materials universe.

        Raises
        ------
        automata.exceptions.Error
            If ``materials.json`` does not exist (materials have not been
            exported, or the build directory was cleaned since), or does not
            contain a universe.

        """
        materials_json = self._materials_json_path()
        if not materials_json.is_file():
            raise Error(
                f'No exported materials found: "{materials_json}" does not exist. '
                f"Run export() first (note that clean_build_directory() removes it)."
            )

        loaded = materials.deserialize(materials_json.read_text())
        if not isinstance(loaded, Universe):
            raise Error(
                f'"{materials_json}" does not contain a universe of materials '
                f"(found a {type(loaded).__name__})."
            )
        return cast(Universe[ExportedArtifact], loaded)

    def _materials_json_path(self) -> Path:
        """Path to the materials.json written by export()."""
        return (
            self.path
            / self.config.website.build_directory
            / self.config.website.materials_directory_name
            / "materials.json"
        )

    def render_website(
        self,
        materials: Universe[ExportedArtifact],
        current_time: datetime.datetime | None = None,
    ) -> None:
        """Render the website from exported materials.

        Loads pages and static content from the content directory and passes
        them to the generation pipeline, along with *materials*. The materials'
        files must already be in the build directory (see :meth:`export`).

        Parameters
        ----------
        materials : Universe[ExportedArtifact]
            The exported materials to render with, as returned by
            :meth:`export` (possibly filtered with :meth:`filter`).
        current_time : datetime.datetime | None
            The current time for date-based rendering logic. If *None*,
            uses the system time.

        """
        current_time = current_time or datetime.datetime.now()
        build_dir = self.path / self.config.website.build_directory
        materials_output_dir = build_dir / self.config.website.materials_directory_name
        content_dir = self.path / self.config.website.content_directory

        self.hooks.on_render_pre(
            RenderPreHookArgs(
                content_directory=content_dir,
                build_directory=build_dir,
            )
        )

        pages, static_content = _load_content_directory(
            content_dir,
            materials_output_dir,
            no_render_suffix=self.config.website.no_render_suffix,
        )

        _website_render(
            build_dir,
            materials_output_dir,
            pages=pages,
            static_content=static_content,
            vars=self.config.vars,
            current_time=current_time,
            hooks=self.hooks,
            base_path=self.config.website.base_path,
            materials_directory_name=self.config.website.materials_directory_name,
            element_configs=self.config.website.elements,
            theme=self.theme,
            extensions=self.extensions,
            materials=materials,
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
