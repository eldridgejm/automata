"""Utilities for parsing YAML configuration files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

from ..exceptions import Error


@dataclass
class SourceMap:
    """The line of each keypath in a YAML file, for error messages.

    Keypaths are tuples of keys as strings, with list indices as strings
    (``("navigation", "0", "url")``), as smartconfig reports them.

    Attributes
    ----------
    file : Path | None
        The file the YAML was read from, if known.
    lines : dict[tuple[str, ...], int]
        The 1-based line of each key (for mapping values) or item (for list
        items).
    includes : dict[tuple[str, ...], SourceMap]
        The source maps of files included (with ``__include__``) at each
        keypath, relative to that keypath. Includes nested in included files are
        also listed here, at their full keypath.
    data : Any
        The parsed (unresolved) contents of the file, as written.

    """

    file: Path | None
    lines: dict[tuple[str, ...], int] = field(default_factory=dict)
    includes: dict[tuple[str, ...], "SourceMap"] = field(default_factory=dict)
    data: Any = None

    def value_at(self, keypath: Sequence[Any]) -> "Located":
        """The value at *keypath* as written, following includes."""
        parts = tuple(str(key) for key in keypath)
        prefixes = [p for p in self.includes if parts[: len(p)] == p and p]
        for prefix in sorted(prefixes, key=len, reverse=True):
            located = value_at(self.includes[prefix].data, parts[len(prefix) :])
            if located.found:
                return located
        return value_at(self.data, parts)

    def add_include(self, keypath: Sequence[Any], source_map: "SourceMap") -> None:
        """Record that the file of *source_map* is included at *keypath*."""
        self.includes[tuple(str(key) for key in keypath)] = source_map

    def locate(self, keypath: Sequence[Any]) -> tuple[Path | None, int | None]:
        """The file and line of *keypath*, following includes.

        A keypath inside an included file is found in that file. If it is not
        there, this falls back to the enclosing keys, and so to the line that
        includes the file. The line is None if no part of the keypath is found.

        """
        parts = tuple(str(key) for key in keypath)
        # try the deepest include containing the keypath first, then shallower
        # ones, then this file
        prefixes = [p for p in self.includes if parts[: len(p)] == p and p]
        for prefix in sorted(prefixes, key=len, reverse=True):
            included = self.includes[prefix]
            line = included.line_of(parts[len(prefix) :])
            if line is not None:
                return included.file, line
        return self.file, self.line_of(parts)

    def line_of(self, keypath: Sequence[Any]) -> int | None:
        """The line of *keypath*, or of the closest enclosing key that has one.

        A keypath may not be in the file (e.g. a missing required key), so this
        falls back to the line of its parent, and so on. Returns None if no part
        of the keypath is in the file.

        """
        parts = tuple(str(key) for key in keypath)
        while parts:
            if parts in self.lines:
                return self.lines[parts]
            parts = parts[:-1]
        return None


@dataclass
class Located:
    """The result of looking up a keypath in parsed YAML."""

    found: bool
    value: Any = None
    # whether the value is an item of a list (rather than a mapping's value)
    in_list: bool = False


def value_at(data: Any, keypath: Sequence[Any]) -> Located:
    """The value at *keypath* in parsed YAML *data*, if it is there."""
    located = Located(found=True, value=data)
    for key in keypath:
        container = located.value
        if isinstance(container, dict):
            matches = [k for k in container if str(k) == str(key)]
            if not matches:
                return Located(found=False)
            located = Located(found=True, value=container[matches[0]])
        elif isinstance(container, list) and str(key).isdigit():
            if int(key) >= len(container):
                return Located(found=False)
            located = Located(found=True, value=container[int(key)], in_list=True)
        else:
            return Located(found=False)
    return located


def _record_lines(
    node: Any,
    keypath: tuple[str, ...],
    lines: dict[tuple[str, ...], int],
    offset: int,
    constructor: Any,
) -> None:
    """Record the line of every key and item under *node* in *lines*.

    Keys are recorded as parsed (e.g. ``01`` as ``"1"``), since keypaths in
    errors come from the parsed data.

    """
    if isinstance(node, MappingNode):
        for key_node, value_node in node.value:
            if not isinstance(key_node, ScalarNode):
                continue
            key = constructor.construct_object(key_node)
            child = (*keypath, str(key))
            lines[child] = key_node.start_mark.line + 1 + offset
            _record_lines(value_node, child, lines, offset, constructor)
    elif isinstance(node, SequenceNode):
        for i, item_node in enumerate(node.value):
            child = (*keypath, str(i))
            lines[child] = item_node.start_mark.line + 1 + offset
            _record_lines(item_node, child, lines, offset, constructor)


def parse_yaml_with_source_map(
    yaml_content: str, source: Path | None = None, first_line: int = 1
) -> tuple[Any, SourceMap]:
    """Parse a YAML string, also returning the line of each keypath.

    Parameters are as for :func:`parse_yaml`.

    Returns
    -------
    tuple[Any, SourceMap]
        The parsed YAML data, and the line of each of its keypaths.

    """
    data = parse_yaml(yaml_content, source=source, first_line=first_line)
    # the content parsed, so composing it again cannot fail
    yaml = YAML(typ="safe")
    node = yaml.compose(yaml_content)
    source_map = SourceMap(source, data=data)
    _record_lines(node, (), source_map.lines, first_line - 1, yaml.constructor)
    return data, source_map


def parse_yaml(
    yaml_content: str, source: Path | None = None, first_line: int = 1
) -> Any:
    """Parse a YAML string into a Python object.

    Tags starting with ! are converted to dict-form function calls like
    {"__tag__": value} to support smartconfig-style syntactic sugar.

    Parameters
    ----------
    yaml_content : str
        The YAML content to parse.
    source : Path | None
        The file the content came from, named in error messages.
    first_line : int
        The line of the file on which the content starts (e.g. 2 for page
        frontmatter, which follows a ``---`` line), for error messages.

    Returns
    -------
    Any
        The parsed YAML data (typically a dict, list, or primitive value).

    Raises
    ------
    automata.exceptions.Error
        If the content is not valid YAML. The message gives the source file
        (if known) and the line and column of the problem.

    """

    def generic_constructor(loader: Any, tag_suffix: str, node: Any) -> dict[str, Any]:
        if isinstance(node, ScalarNode):
            value = loader.construct_scalar(node)
        elif isinstance(node, SequenceNode):
            value = loader.construct_sequence(node)
        elif isinstance(node, MappingNode):
            value = loader.construct_mapping(node)
        else:
            raise ValueError(f"Unknown YAML node type: {type(node)!r}")

        return {f"__{tag_suffix}__": value}

    yaml = YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.constructor.add_multi_constructor("!", generic_constructor)
    try:
        return yaml.load(yaml_content)
    except YAMLError as exc:
        raise Error(_describe_yaml_error(exc, source, first_line - 1)) from None


def _describe_yaml_error(exc: YAMLError, source: Path | None, offset: int = 0) -> str:
    """A one-line description of a YAML error, with 1-based line and column."""
    message = "Invalid YAML"
    if source is not None:
        message += f" in {source}"

    if not isinstance(exc, MarkedYAMLError) or exc.problem_mark is None:
        return f"{message}: {exc}"

    mark = exc.problem_mark
    message += (
        f", line {mark.line + 1 + offset}, column {mark.column + 1}: {exc.problem}"
    )
    if exc.context:
        message += f" ({exc.context}"
        if exc.context_mark is not None:
            message += f" starting at line {exc.context_mark.line + 1 + offset}"
        message += ")"
    return message
