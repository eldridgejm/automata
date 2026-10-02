import re
from pathlib import Path
from typing import Any

import smartconfig.exceptions
from smartconfig import Prototype

from automata.exceptions import Error
from automata.util.resolution import describe_config_error, resolve
from automata.util.yaml import parse_yaml_with_source_map


class FrontmatterError(Error):
    """The frontmatter of a page is invalid.

    Attributes
    ----------
    message : str
        The problem, without the page's path.
    line : int | None
        The line of the page with the problem, if known.

    """

    def __init__(self, message: str, line: int | None = None):
        self.message = message
        self.line = line
        super().__init__(message)


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
    data, source_map = parse_yaml_with_source_map(yaml_content, first_line=2)
    if data is None:
        # empty, or only comments
        data = {}
    try:
        return resolve(data, Frontmatter, base_path=base_path, source_map=source_map)
    except smartconfig.exceptions.ResolutionError as e:
        file, line = source_map.locate(e.keypath)
        if file is None:
            # the line is in the page itself
            raise FrontmatterError(
                describe_config_error(e.reason, e.keypath), line
            ) from None
        raise FrontmatterError(
            describe_config_error(e.reason, e.keypath, file=file, line=line)
        ) from None


_FRONTMATTER = re.compile(r"---\n(?P<yaml>(?:.*?\n)??)---(?:\n|\Z)", re.DOTALL)


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
    # the frontmatter is between a first line "---" and the next line "---", which
    # may come right after the first (empty frontmatter) or end the file
    match = _FRONTMATTER.match(content)
    if match is None:
        return None, content
    return match["yaml"], content[match.end() :]


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
