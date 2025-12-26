import hashlib
import importlib.metadata as metadata
import importlib.resources
import importlib.util
import json
import sys
from dataclasses import dataclass, field
from importlib.resources.abc import Traversable
from typing import TYPE_CHECKING, cast

import jinja2
import smartconfig.exceptions
import smartconfig.types

if TYPE_CHECKING:
    from ._elements import Element


@dataclass
class Theme:
    # dictionary mapping template names to their content
    templates: dict[str, str]

    # dictionary mapping static file names to their content. If the value is a path,
    # the file at that path will be copied to the output. If the value is bytes or
    # a string, that content will be written to the output file.
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)

    # dictionary mapping element names to element functions
    elements: dict[str, Element] = field(default_factory=dict)

    # optional smartconfig schema for theme configuration validation
    schema: smartconfig.types.Schema | None = None

    @classmethod
    def from_directory(
        cls, directory: Traversable, require_templates: bool = True
    ) -> "Theme":
        """Create a Theme instance from a directory.

        The directory must contain a ``templates/`` subdirectory with template
        files (unless ``require_templates`` is False). It may optionally contain
        a ``static/`` subdirectory with static files and an ``elements/``
        subdirectory containing a Python package.

        If the ``elements/`` directory is present, it must contain an
        ``__init__.py`` file that defines an ``elements`` variable. This
        variable must be a dictionary mapping element names to ``Element``
        instances.

        Parameters
        ----------
        directory : Traversable
            The directory containing the theme files.
        require_templates : bool, optional
            If True (default), the directory must contain a ``templates/``
            subdirectory. If False, ``templates/`` is optional.

        Returns
        -------
        Theme
            The created Theme instance.

        Raises
        ------
        ValueError
            If the directory does not exist, if ``require_templates`` is True
            and the ``templates/`` directory is missing, or if the
            ``elements/`` package is invalid (e.g. missing ``__init__.py``
            or valid ``elements`` dictionary).

        """
        if not directory.is_dir():
            raise ValueError("Theme directory does not exist or is not a directory.")

        templates_dir = directory / "templates"
        if require_templates and not templates_dir.is_dir():
            raise ValueError('Theme directory must contain a "templates" directory.')

        static_dir = directory / "static"

        templates: dict[str, str] = {}
        static_files: dict[str, str | bytes | Traversable] = {}
        elements: dict[str, "Element"] = {}

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

        if templates_dir.is_dir():
            _walk(templates_dir, _add_template)
        if static_dir.is_dir():
            _walk(static_dir, _add_static_file)

        elements_dir = directory / "elements"
        if elements_dir.is_dir():
            elements = _load_elements_from_directory(elements_dir)

        # Load schema from schema.json if present
        schema_file = directory / "schema.json"
        schema: smartconfig.types.Schema | None = None

        if schema_file.is_file():
            try:
                schema_content = schema_file.read_text()
                schema = json.loads(schema_content)
                # Validate it's a valid smartconfig schema
                smartconfig.validate_schema(schema)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in schema.json: {e}")
            except smartconfig.exceptions.InvalidSchemaError as e:
                raise ValueError(f"Theme configuration schema is invalid: {e}")

        return cls(
            templates=templates,
            static_files=static_files,
            elements=elements,
            schema=schema,
        )

    @classmethod
    def from_entry_point(cls, entry_point_name: str) -> "Theme":
        """Create a Theme instance from an entry point.

        The entry point should refer to a module that either:
        1. Exports a ``theme`` attribute containing a Theme instance, or
        2. Is a package with ``templates/`` and optionally ``static/`` directories.

        If the module has a ``theme`` attribute, it will be used. Otherwise,
        the module will be treated as a theme package and loaded from its
        ``templates/`` and ``static/`` directories.

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
        entry_point = entry_points.select(group="automata.website.themes")[
            entry_point_name
        ]

        module = entry_point.load()
        if hasattr(module, "theme"):
            return cast(Theme, module.theme)
        else:
            root = importlib.resources.files(module)
            return cls.from_directory(root)

    def create_jinja_environment(self) -> jinja2.Environment:
        return jinja2.Environment(
            loader=jinja2.DictLoader(self.templates),
            undefined=jinja2.StrictUndefined,
            variable_start_string="${",
            variable_end_string="}",
            block_start_string="{%",
            block_end_string="%}",
        )


def _load_elements_from_directory(
    elements_dir: Traversable,
) -> dict[str, "Element"]:
    """Load elements from a directory.

    The directory must be a Python package (containing an ``__init__.py`` file)
    and must define an ``elements`` variable that is a dictionary mapping
    element names to Element instances.

    Parameters
    ----------
    elements_dir : Traversable
        The directory containing the elements package.

    Returns
    -------
    dict[str, Element]
        A dictionary mapping element names to Element instances.

    Raises
    ------
    ValueError
        If the elements package cannot be loaded or does not define a
        valid ``elements`` variable.

    """
    init_file = elements_dir / "__init__.py"
    if not init_file.is_file():
        return {}

    with importlib.resources.as_file(elements_dir) as elements_path:
        digest = hashlib.sha256(str(elements_path).encode("utf-8")).hexdigest()[:12]
        module_name = f"automata.website.theme_elements_{digest}"
        init_path = elements_path / "__init__.py"

        spec = importlib.util.spec_from_file_location(
            module_name,
            init_path,
            submodule_search_locations=[str(elements_path)],
        )
        if spec is None or spec.loader is None:
            raise ValueError(f"Unable to load elements package at {init_path}.")

        module = importlib.util.module_from_spec(spec)

        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception:
            # Clean up sys.modules if loading fails
            sys.modules.pop(module_name, None)
            raise

    if hasattr(module, "elements"):
        elements = module.elements
    else:
        raise ValueError(
            f"Elements package at {init_file} must define an `elements` variable."
        )

    if not isinstance(elements, dict):
        raise ValueError(
            f"Elements package at {init_file} must return a dict of elements."
        )

    return elements
