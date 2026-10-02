"""Utilities for parsing YAML configuration files."""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode

from ..exceptions import Error


def parse_yaml(yaml_content: str, source: Path | None = None) -> Any:
    """Parse a YAML string into a Python object.

    Tags starting with ! are converted to dict-form function calls like
    {"__tag__": value} to support smartconfig-style syntactic sugar.

    Parameters
    ----------
    yaml_content : str
        The YAML content to parse.
    source : Path | None
        The file the content came from, named in error messages.

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
        raise Error(_describe_yaml_error(exc, source)) from None


def _describe_yaml_error(exc: YAMLError, source: Path | None) -> str:
    """A one-line description of a YAML error, with 1-based line and column."""
    message = "Invalid YAML"
    if source is not None:
        message += f" in {source}"

    if not isinstance(exc, MarkedYAMLError) or exc.problem_mark is None:
        return f"{message}: {exc}"

    mark = exc.problem_mark
    message += f", line {mark.line + 1}, column {mark.column + 1}: {exc.problem}"
    if exc.context:
        message += f" ({exc.context}"
        if exc.context_mark is not None:
            message += f" starting at line {exc.context_mark.line + 1}"
        message += ")"
    return message
