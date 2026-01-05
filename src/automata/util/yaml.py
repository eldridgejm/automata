"""Utilities for parsing YAML configuration files."""

from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.nodes import MappingNode, ScalarNode, SequenceNode


def parse_yaml(yaml_content: str) -> Any:
    """Parse a YAML string into a Python object.

    Tags starting with ! are converted to dict-form function calls like
    {"__tag__": value} to support smartconfig-style syntactic sugar.

    Parameters
    ----------
    yaml_content : str
        The YAML content to parse.

    Returns
    -------
    Any
        The parsed YAML data (typically a dict, list, or primitive value).

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
    return yaml.load(yaml_content)
