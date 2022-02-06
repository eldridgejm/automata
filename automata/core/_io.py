from .exceptions import DiscoveryError

import yaml

import dictconfig


def read_collection_file(path, vars=None):
    """Read a :class:`Collection` from a yaml file.

    See the documentation for a description of the format of the file.

    Parameters
    ----------
    path : pathlib.Path
        Path to the collection file.
    vars : Optional[dict]
        A dictionary of variables available during interpolation.

    Returns
    -------
    Collection
        The collection object with no attached publications.

    """
    if vars is None:
        vars = {}

    with path.open() as fileobj:
        raw_contents = yaml.load(fileobj, Loader=yaml.Loader)

    try:
        resolved = _resolve_collection_file(raw_contents, {"vars": vars}, path)
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    return resolved


def _collection_file_schema():
    """The dictconfig schema describing a valid collection file."""
    return {
        "type": "dict",
        "required_keys": {
            "publication_schema": {
                "type": "dict",
                "required_keys": {
                    "required_artifacts": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                    }
                },
                "optional_keys": {
                    "optional_artifacts": {
                        "type": "list",
                        "element_schema": {"type": "string"},
                        "default": [],
                    },
                    "metadata_schema": {
                        "type": "dict",
                        "extra_keys_schema": {"type": "any"},
                        "default": None,
                        "nullable": True,
                    },
                    "allow_unspecified_artifacts": {
                        "type": "boolean",
                        "default": False,
                    },
                    "is_ordered": {"type": "boolean", "default": False},
                },
            }
        },
    }


def _resolve_collection_file(raw_contents, external_variables, path):
    """Resolves (interpolates and parses) the raw collection file contents.

    Parameters
    ----------
    raw_contents : dict
        The raw dictionary loaded from the publication file.
    external_variables : Optional[dict]
        A dictionary of external_variables passed to dictconfig and used during
        interpolation. These are accessible under ${vars}.
    path : pathlib.Path
        The path to the collection file being read. Used to format error messages.

    Returns
    -------
    dict
        The resolved dictionary.

    Raises
    ------
    DiscoveryError
        If the collection file is invalid.

    """
    schema = _collection_file_schema()

    try:
        resolved = dictconfig.resolve(
            raw_contents, schema, external_variables=external_variables
        )
    except dictconfig.exceptions.ResolutionError as exc:
        raise DiscoveryError(str(exc), path)

    _validate_metadata_schema(resolved["publication_schema"]["metadata_schema"], path)

    return resolved


def _validate_metadata_schema(metadata_schema, path):
    if metadata_schema is None:
        return

    try:
        dictconfig.validate_schema({"type": "dict", **metadata_schema})
    except dictconfig.exceptions.InvalidSchemaError as exc:
        raise DiscoveryError(exc, path)
