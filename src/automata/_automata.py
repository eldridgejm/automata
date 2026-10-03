"""Public API for working with an automata project."""

import datetime
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from . import constants, materials
from ._calendar import Calendar, make_calendar
from ._check import Problem, run_checks
from ._status import Status, make_status
from .config import (
    CONFIGURATION_FILENAME,
    Config,
    course_variables,
    load_extensions,
    read_config_with_source_map,
)
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
from .util.yaml import SourceMap
from .website import load_content_directory
from .website import render as _website_render


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
        self.config: Config
        # the line of each keypath in automata.yaml (and the files it includes),
        # for errors found after the configuration is read
        self.source_map: SourceMap
        self.config, self.source_map = read_config_with_source_map(config_path)
        self.theme: Extension
        self.extensions: list[Extension]
        self.theme, self.extensions = load_extensions(
            self.config, cwd=path, source_map=self.source_map
        )
        self.hooks: Hooks = Hooks()
        apply_extensions([self.theme, *self.extensions], self.hooks)

    # --- full pipeline ---

    def build(
        self, current_time: datetime.datetime | None = None, verbose: bool = False
    ) -> None:
        """Run the full pipeline and produce the site in the build directory.

        Cleans the build directory (if ``website.clean_build_directory`` is
        true), then runs :meth:`discover`, :meth:`build_materials`,
        :meth:`export`, and :meth:`render_website`.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The current time for release-time checks and scheduling.
            If *None*, uses the system time.
        verbose : bool
            If true, recipes' output goes to the terminal as they run, rather
            than being captured (and shown only if a recipe fails).

        """
        current_time = current_time or datetime.datetime.now()
        if self.config.website.clean_build_directory:
            self.clean_build_directory()
        discovered = self.discover()
        built = self.build_materials(
            discovered, current_time=current_time, verbose=verbose
        )
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
            content directory; lies outside the project or inside the content
            directory; contains an ``automata.yaml`` file or course materials
            (a ``collection.yaml`` or ``publication.yaml``); or is, contains, or
            lies inside a directory extension. Nothing is deleted in that case.

        """
        build_dir = (self.path / self.config.website.build_directory).resolve()
        project_dir = self.path.resolve()
        content_dir = (self.path / self.config.website.content_directory).resolve()

        problem = None
        if project_dir.is_relative_to(build_dir):
            problem = "is or contains the project directory"
        elif not build_dir.is_relative_to(project_dir):
            problem = "is outside the project directory"
        elif content_dir.is_relative_to(build_dir):
            problem = "is or contains the content directory"
        elif build_dir.is_relative_to(content_dir):
            problem = "is inside the content directory"
        elif (build_dir / CONFIGURATION_FILENAME).exists():
            problem = f"contains an {CONFIGURATION_FILENAME} file"
        elif any(
            build_dir.is_relative_to(extension) or extension.is_relative_to(build_dir)
            for extension in self._extension_directories()
        ):
            problem = "is, contains, or is inside an extension directory"
        elif _holds_materials(build_dir):
            problem = (
                f"contains course materials (a {constants.COLLECTION_FILE} or "
                f"{constants.PUBLICATION_FILE} file)"
            )

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
        verbose: bool = False,
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

        for name, entry in self.config.publish.items():
            _check_publish_target(name, entry)

        if target is not None:
            if target not in self.config.publish:
                available = ", ".join(sorted(self.config.publish))
                raise Error(
                    f"Unknown publish target: {target!r}. Available: {available}"
                )
            targets = {target: self.config.publish[target]}
        else:
            targets = self.config.publish

        # check every strategy before building, so a typo fails fast
        registry_publishers = self._publishers()
        publishers = {}
        for name, entry in targets.items():
            strategy_name = entry["strategy"]
            publisher = registry_publishers.get(strategy_name)
            if publisher is None:
                available = ", ".join(sorted(registry_publishers)) or "(none)"
                raise Error(
                    f"Unknown publish strategy: {strategy_name!r}. "
                    f"Available: {available}"
                )
            publishers[name] = publisher

        self.build(current_time=current_time, verbose=verbose)

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
        materials defined in ``automata.yaml``. The build directory and
        directories whose names start with a dot (``.git``, ``.venv``) are
        skipped.

        Returns
        -------
        Universe[UnbuiltArtifact]
            The discovered, unbuilt materials universe.

        """
        return self._discover(hooks=self.hooks)

    def _discover(
        self, hooks: Hooks | None, errors: list[Error] | None = None
    ) -> Universe[UnbuiltArtifact]:
        """Discover materials (see :meth:`discover`).

        *hooks* may be None, to run no discovery hooks (as :meth:`status` and
        :meth:`check` don't). If *errors* is given, an error in a collection is
        appended to it, and the collection left out, rather than raised.
        """
        # the build directory holds copies of materials (and, without cleaning,
        # stale ones), and hidden directories (.git, .venv) hold none
        build_dir = (self.path / self.config.website.build_directory).resolve()

        def skip(directory: Path) -> bool:
            return directory.name.startswith(".") or directory.resolve() == build_dir

        universe = materials.discover(
            self.path,
            skip=skip,
            vars=self.config.vars,
            course=course_variables(self.config.course),
            hooks=hooks,
            errors=errors,
        )

        if self.config.materials:
            inline = materials.discover_inline(
                self.config.materials,
                self.path,
                vars=self.config.vars,
                course=course_variables(self.config.course),
                hooks=hooks,
                source_map=self.source_map,
                errors=errors,
            )
            for key in sorted(inline.collections.keys() & universe.collections.keys()):
                error = Error(
                    f'Collection "{key}" is defined both under materials in '
                    f"{CONFIGURATION_FILENAME} and as the directory "
                    f"{self.path / key}. Rename one of them."
                )
                if errors is None:
                    raise error
                errors.append(error)
                del inline.collections[key]
            universe = inline.merge(universe)

        return universe

    def status(self, current_time: datetime.datetime | None = None) -> Status:
        """The status of the materials: what is released and what is scheduled.

        Reports what the materials say, as of *current_time*; it doesn't look at
        any build (the site may be built and deployed elsewhere). Builds nothing
        and runs no recipes or hooks.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The time to give the status for. If *None*, uses the system time.

        Returns
        -------
        Status
            Each artifact's state, the counts of each state, and the next
            releases.

        Raises
        ------
        automata.exceptions.Error
            If the materials can't be discovered.

        """
        return make_status(
            self._discover(hooks=None), current_time or datetime.datetime.now()
        )

    def calendar(
        self,
        collections: Sequence[str] | None = None,
        keys: Sequence[str] | None = None,
        start: datetime.date | None = None,
        end: datetime.date | None = None,
        week_start: str = "sunday",
        all_weeks: bool = False,
        highlight_today: bool = True,
        current_time: datetime.datetime | None = None,
    ) -> Calendar:
        """A week-by-week calendar of the dates in the materials' metadata.

        The ``calendar`` section of ``automata.yaml`` says, for each collection,
        which metadata keys' dates to show (e.g. ``released`` and ``due``), with
        optional labels and colors. Builds nothing and runs no recipes or hooks.

        Parameters
        ----------
        collections : Sequence[str] | None
            Show only these collections (from the configuration). If None, all
            are shown.
        keys : Sequence[str] | None
            Show only dates under metadata keys matching one of these glob
            patterns (e.g. ``"due"``). If None, all configured keys are shown.
        start, end : datetime.date | None
            Show only dates on or after *start* and on or before *end*. By
            default, *start* is the first day of the current week.
        week_start : str
            The day weeks start on: ``"sunday"`` (the default) or ``"monday"``.
        all_weeks : bool
            Show every week, not just the current one and later ones.
        highlight_today : bool
            Whether the renderings highlight today.
        current_time : datetime.datetime | None
            The time that decides which dates are past. If *None*, uses the
            system time.

        Returns
        -------
        Calendar
            The weeks, with each day's entries. It renders with
            ``rich_table()``, ``to_html()``, and ``write_pdf(path)``.

        Raises
        ------
        automata.exceptions.Error
            If the ``calendar`` section is missing or invalid, or the materials
            can't be discovered.

        """
        return make_calendar(
            self._discover(hooks=None),
            self.config.calendar,
            current_time or datetime.datetime.now(),
            vars=self.config.vars,
            collections=collections,
            keys=keys,
            start=start,
            end=end,
            week_start=week_start,
            all_weeks=all_weeks,
            highlight_today=highlight_today,
            course=course_variables(self.config.course),
            config_path=self.path / CONFIGURATION_FILENAME,
            source_map=self.source_map,
        )

    def check(self, current_time: datetime.datetime | None = None) -> list[Problem]:
        """Check the project for problems, without building anything.

        Each check runs on its own, so every problem is found at once:

        - the collections and publications (each collection separately), and
          released artifacts without a recipe whose file doesn't exist;
        - each page's frontmatter and template syntax;
        - the syntax of the theme's and extensions' templates;
        - ``website.elements``: unknown elements, and configurations that don't
          match their element's schema, whether or not a page uses them;
        - the publish targets and their strategies.

        Runs no recipes or hooks, and writes nothing.

        Parameters
        ----------
        current_time : datetime.datetime | None
            The time to check releases against. If *None*, uses the system time.

        Returns
        -------
        list[Problem]
            The problems found; empty if there are none.

        """
        return run_checks(self, current_time or datetime.datetime.now())

    def _publishers(self) -> dict[str, Any]:
        """The publish strategies: the built-in ones, and those extensions add."""
        from . import publish as publish_module

        registry = self.hooks.on_register_publishers(
            PublisherRegistryArgs(publishers=publish_module.registry.all())
        )
        return registry.publishers

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
                f"Export the materials first (automata export, or Automata.export in "
                f"Python); cleaning the build directory removes them."
            )

        loaded = materials.deserialize(materials_json.read_text())
        if not isinstance(loaded, Universe):
            raise Error(
                f'"{materials_json}" does not contain a universe of materials '
                f"(found a {type(loaded).__name__})."
            )
        return cast(Universe[ExportedArtifact], loaded)

    def _extension_directories(self) -> list[Path]:
        """The directories of the theme and extensions loaded from paths."""
        specs = [self.config.website.theme, *self.config.extensions]
        names = [spec.get("use") if isinstance(spec, dict) else spec for spec in specs]
        return [
            (self.path / name).resolve()
            for name in names
            if isinstance(name, str) and ("/" in name or "\\" in name)
        ]

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

        if not content_dir.is_dir():
            raise Error(
                f'website.content_directory "{self.config.website.content_directory}" '
                f"does not exist ({content_dir})."
            )

        pages, static_content = load_content_directory(
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
            course=course_variables(self.config.course),
            current_time=current_time,
            hooks=self.hooks,
            base_path=self.config.website.base_path,
            materials_directory_name=self.config.website.materials_directory_name,
            element_configs=self.config.website.elements,
            config_source_map=self.source_map,
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
            universe = materials.discover(
                collection_dir,
                vars=self.config.vars,
                course=course_variables(self.config.course),
            )
            collection = universe.collections["."]
            pub_key = str(pub_dir.relative_to(collection_dir))
            return collection.publications[pub_key]
        else:
            universe = materials.discover(
                pub_dir,
                vars=self.config.vars,
                course=course_variables(self.config.course),
            )
            return universe.collections["default"].publications["."]


def _holds_materials(directory: Path) -> bool:
    """Whether *directory* contains a collection.yaml or publication.yaml."""
    if not directory.is_dir():
        return False
    return any(
        path.is_file()
        for name in (constants.COLLECTION_FILE, constants.PUBLICATION_FILE)
        for path in directory.rglob(name)
    )


def _check_publish_target(name: str, entry: Any) -> None:
    """Check the shape of one publish target, naming it in any error."""
    where = f"publish.{name}"
    if not isinstance(entry, dict):
        raise Error(
            f'{where} must be a mapping with "strategy" and "config" keys, not '
            f"{entry!r}."
        )
    for key in entry:
        if key not in ("strategy", "config"):
            raise Error(
                f'{where} has unknown key "{key}" (expected "strategy" and "config").'
            )
    if not isinstance(entry.get("strategy"), str):
        raise Error(f'{where} must have a "strategy" (e.g. gh-pages or rsync).')
    if not isinstance(entry.get("config", {}), dict):
        raise Error(f"{where}.config must be a mapping.")
