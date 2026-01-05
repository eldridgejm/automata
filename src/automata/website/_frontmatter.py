from pathlib import Path
from typing import Any

from smartconfig import Prototype

from automata.util.resolution import resolve
from automata.util.yaml import parse_yaml


class Frontmatter(Prototype):
    """Frontmatter for a website page."""

    # a dictionary of variables that can be used during rendering. these can be
    # any serializable values.
    vars: dict[str, Any] = {}

    # the template that will be used to render the page
    template: str = "page.html"


def _parse_yaml_frontmatter(
    yaml_content: str,
    base_path: Path | None = None,
) -> Frontmatter:
    """Parses the given YAML content into a Frontmatter object.

    Parameters
    ----------
    yaml_content : str
        The YAML content to parse.
    base_path : Path | None
        The base directory for resolving relative paths in __include__ directives.
        If None, the include function will not be available. Default: None.

    Returns
    -------
    Frontmatter
        The parsed frontmatter.

    """
    data = parse_yaml(yaml_content)
    return resolve(data, Frontmatter, base_path=base_path)


def _find_and_extract_frontmatter_yaml(content: str) -> tuple[str | None, str]:
    """Finds and extracts the frontmatter block from content.

    Parameters
    ----------
    content : str
        The content to search for frontmatter.

    Returns
    -------
    str | None
        The YAML content between delimiters, or None if not found.
    str
        The remaining content after removing frontmatter.

    """
    # Check if content starts with frontmatter delimiter
    if not content.startswith("---\n"):
        return None, content

    # Find the closing delimiter
    # Start searching after the opening "---\n" (4 characters)
    closing_delimiter = "\n---\n"
    closing_index = content.find(closing_delimiter, 4)

    if closing_index == -1:
        # No closing delimiter found - treat as no frontmatter
        return None, content

    # Extract YAML content between delimiters
    # Start at position 4 (after "---\n") and end at closing_index
    yaml_content = content[4:closing_index]

    # Remove the frontmatter from the content
    # Skip past the closing delimiter (closing_index + len("\n---\n"))
    remaining_content = content[closing_index + 5 :]

    return yaml_content, remaining_content


def read_frontmatter(
    content: str,
    base_path: Path | None = None,
) -> tuple[Frontmatter, str]:
    """Reads the frontmatter from the given content.

    Returns both the frontmatter and the content without the frontmatter.

    Parameters
    ----------
    content : str
        The content to read the frontmatter from.
    base_path : Path | None
        The base directory for resolving relative paths in __include__ directives.
        If None, the include function will not be available. Default: None.

    Returns
    -------
    Frontmatter
        The frontmatter read from the content.
    str
        The content without the frontmatter.

    """
    yaml_content, remaining_content = _find_and_extract_frontmatter_yaml(content)

    if yaml_content is None:
        # No frontmatter found
        return Frontmatter(vars={}), remaining_content

    # Parse the YAML into a Frontmatter object
    frontmatter = _parse_yaml_frontmatter(yaml_content, base_path=base_path)

    return frontmatter, remaining_content
