from typing import Any

import yaml
from smartconfig import Prototype, resolve


class Frontmatter(Prototype):
    """Frontmatter for a website page."""

    # a dictionary of variables that can be used during rendering. these can be
    # any serializable values.
    vars: dict[str, Any] = {}

    # the template that will be used to render the page
    template: str = "base.html"


def _parse_yaml_frontmatter(
    yaml_content: str,
) -> Frontmatter:
    """Parses the given YAML content into a Frontmatter object.

    Parameters
    ----------
    yaml_content : str
        The YAML content to parse.

    Returns
    -------
    Frontmatter
        The parsed frontmatter.

    """
    data = yaml.safe_load(yaml_content) or {}
    return resolve(data, Frontmatter)


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
) -> tuple[Frontmatter, str]:
    """Reads the frontmatter from the given content.

    Returns both the frontmatter and the content without the frontmatter.

    Parameters
    ----------
    content : str
        The content to read the frontmatter from.

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
    frontmatter = _parse_yaml_frontmatter(yaml_content)

    return frontmatter, remaining_content
