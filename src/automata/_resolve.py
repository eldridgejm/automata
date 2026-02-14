"""High-level function for resolving publication files.

Not to be confused with the lower-level resolve() functions for resolving arbitrary
configurations.

"""

import pathlib

from .config import find_config, read_config
from .materials import (
    Publication,
    UnbuiltArtifact,
    read_publication_file,
)


def resolve(path: pathlib.Path) -> Publication[UnbuiltArtifact]:
    """Resolve a publication.yaml file.

    This high-level function finds the automata.yaml config file, extracts
    variables, and resolves the publication file with all context.

    The publication's parent collection (if any) and previous publication
    (for ordered collections) are discovered automatically.

    Parameters
    ----------
    path : pathlib.Path
        Path to the publication.yaml file.

    Returns
    -------
    Publication[UnbuiltArtifact]
        The resolved publication with all artifacts as UnbuiltArtifact objects.

    Raises
    ------
    FileNotFoundError
        If the automata.yaml config file cannot be found.
    Exception
        If there are errors reading the config or resolving the publication.

    """
    # Resolve to absolute path immediately to ensure consistent path operations
    path = path.resolve()

    # Find the automata.yaml config file by searching upwards
    config_path = find_config(path)
    if config_path is None:
        raise FileNotFoundError(
            f"Could not find automata.yaml in {path.parent} or any parent directory."
        )

    # Read config and extract variables
    config = read_config(config_path)
    vars_dict = config.vars

    # Resolve the publication file - collection and previous are found automatically
    return read_publication_file(path, vars=vars_dict)
