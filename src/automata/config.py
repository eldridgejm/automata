from pathlib import Path
from typing import Any, cast

import smartconfig
import yaml

from .exceptions import Error
from .website import WebsiteConfig


class Config(smartconfig.Prototype):
    """Top-level configuration for automata."""

    # a dictionary of variables to be made available globally, including in website
    # pages and configuration files
    vars: dict[str, Any] = {}

    # configuration for the website
    website: WebsiteConfig


def read_config(path: Path) -> Config:
    """Read the configuration from the given yaml file.

    Parameters
    ----------
    path : Path
        Path to the YAML configuration file.

    Returns
    -------
    Config
        The resolved configuration.

    Raises
    ------
    automata.exceptions.Error
        If the configuration is invalid or does not match the schema.

    """
    # Read the YAML file
    with path.open("r") as f:
        raw_config = yaml.safe_load(f)

    # set up custom functions. For now, there is only "include"
    def include(args: smartconfig.types.FunctionArgs) -> Any:
        """Include another YAML file and return its contents."""
        schema = {"type": "string"}
        include_path = smartconfig.resolve(args.input, schema)
        include_path = cast(str, include_path)

        include_path = path.parent / include_path
        with include_path.open("r") as f:
            return yaml.safe_load(f)

    def md_to_html(args: smartconfig.types.FunctionArgs) -> str:
        """Convert markdown content to HTML."""
        schema = {"type": "string"}
        md_content = smartconfig.resolve(args.input, schema)
        md_content = cast(str, md_content)

        import markdown

        html = markdown.markdown(md_content)
        print(html.strip())
        return html.strip()

    functions = dict(smartconfig.DEFAULT_FUNCTIONS).copy()
    functions["include"] = include
    functions["md_to_html"] = md_to_html

    # Resolve the configuration against the schema
    try:
        return smartconfig.resolve(raw_config, Config, functions=functions)
    except smartconfig.exceptions.Error as e:
        raise Error(f"Invalid configuration: {e}") from e
