"""Provides serialize() and deserialize() for textual representation of materials trees."""

import dataclasses
import datetime
import json

from ._types import Artifact, Publication, Collection, Universe


def serialize(node) -> str:
    """Serialize the universe/collection/publication/artifact to JSON.

    Parameters
    ----------
    node : Union[Universe, Collection, Publication, Artifact]
        The thing to serialize as JSON.

    Returns
    -------
    str
        The object serialized as JSON.

    """

    def object_serializer(o):
        """Generic serializer for unknown objects."""
        return str(o)

    if isinstance(node, Artifact):
        dct = dataclasses.asdict(node)
    else:
        dct = node._deep_asdict()

    return json.dumps(dct, default=object_serializer, indent=4)


def _convert_to_time(s: str) -> datetime.date | datetime.datetime:
    """Convert a string to a date or datetime object.

    Parameters
    ----------
    s : str
        The string to convert. See below for the expected format.

    Returns
    -------
    datetime.date | datetime.datetime
        The converted date or datetime object.

    Notes
    -----

    The string must be in ISO 8601 format. The function will attempt to convert
    the string to a date object first, and then to a datetime object if that
    fails. If both fail, a ValueError is raised.

    """
    converters = [datetime.date.fromisoformat, datetime.datetime.fromisoformat]
    for converter in converters:
        try:
            return converter(s)
        except ValueError:
            continue
    else:
        raise ValueError("Not a time.")


def deserialize(s) -> Universe | Collection | Publication | Artifact:
    """Reconstruct a universe/collection/publication/artifact from JSON.

    Parameters
    ----------
    s : str
        The JSON to deserialize.

    Returns
    -------
    Universe/Collection/Publication/Artifact
        The reconstructed object; its type is inferred from the string.

    """

    # we need to pass a hook to json.loads in order to automatically convert
    # datestring to date/datetime objects
    def hook(pairs):
        """Hook for json.loads to convert date/time-like values."""
        d = {}
        for k, v in pairs:
            if isinstance(v, str):
                try:
                    d[k] = _convert_to_time(v)
                except ValueError:
                    d[k] = v
            else:
                d[k] = v
        return d

    dct = json.loads(s, object_pairs_hook=hook)

    # infer what we're reconstructing
    if "collections" in dct:
        type_ = Universe
    elif "publications" in dct:
        type_ = Collection
    elif "artifacts" in dct:
        type_ = Publication
    else:
        return _artifact_from_dict(dct)

    return type_._deep_fromdict(dct)
