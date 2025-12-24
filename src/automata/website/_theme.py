import importlib.metadata as metadata
import importlib.resources
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from types import ModuleType


@dataclass
class Theme:
    # dictionary mapping template names to their content
    templates: dict[str, str]

    # dictionary mapping static file names to their content. If the value is a path,
    # the file at that path will be copied to the output. If the value is bytes or
    # a string, that content will be written to the output file.
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)

    @classmethod
    def from_package(cls, module: ModuleType) -> "Theme":
        """Create a Theme instance from a theme package.

        The module must contain a ``templates`` subpackage. If a ``static``
        subpackage exists, its files will be included as static files.

        Parameters
        ----------
        module : module
            The theme package module.

        Returns
        -------
        Theme
            The created Theme instance.

        """
        root = importlib.resources.files(module)
        return cls.from_directory(root)

    @classmethod
    def from_directory(cls, directory: Traversable) -> "Theme":
        """Create a Theme instance from a directory.

        The directory must contain a `templates` subdirectory with template files
        and a `static` subdirectory with static files.

        Parameters
        ----------
        directory : Traversable
            The directory containing the theme files.

        Returns
        -------
        Theme
            The created Theme instance.

        """
        if not directory.is_dir():
            raise ValueError("Theme directory does not exist or is not a directory.")

        templates_dir = directory / "templates"
        if not templates_dir.is_dir():
            raise ValueError('Theme directory must contain a "templates" directory.')

        static_dir = directory / "static"

        templates: dict[str, str] = {}
        static_files: dict[str, str | bytes | Traversable] = {}

        def _is_hidden(parts: list[str]) -> bool:
            return any(part.startswith(".") for part in parts)

        def _walk(
            node: Traversable, on_file, rel_parts: list[str] | None = None
        ) -> None:
            """Walk a directory tree, passing file keys and entries to a handler.

            Parameters
            ----------
            node : Traversable
                Directory to walk.
            on_file : Callable[[str, Traversable], None]
                Callback invoked for each file with its key and entry.
            rel_parts : list[str] | None
                Path components accumulated so far, relative to the root.

            """
            if rel_parts is None:
                rel_parts = []

            for entry in node.iterdir():
                entry_parts = rel_parts + [entry.name]
                if _is_hidden(entry_parts):
                    continue
                if entry.is_dir():
                    _walk(entry, on_file, entry_parts)
                else:
                    key = "/".join(entry_parts)
                    on_file(key, entry)

        def _add_template(key: str, entry: Traversable) -> None:
            templates[key] = entry.read_text()

        def _add_static_file(key: str, entry: Traversable) -> None:
            static_files[key] = entry

        _walk(templates_dir, _add_template)
        if static_dir.is_dir():
            _walk(static_dir, _add_static_file)

        return cls(templates=templates, static_files=static_files)

    @classmethod
    def from_entry_point(cls, entry_point_name: str) -> "Theme":
        """Create a Theme instance from an entry point.

        Parameters
        ----------
        entry_point_name : str
            The name of the entry point.

        Returns
        -------
        Theme
            The created Theme instance.

        """
        entry_points = metadata.entry_points()
        entry_point = entry_points.select(group="automata.website.theme")[
            entry_point_name
        ]

        module = entry_point.load()
        return cls.from_package(module)
