import pathlib

from ...lib.materials import read_collection_file, read_publication_file, discover
from ...lib.materials import constants


def resolve(path, vars=None):
    """Return a resolved dictionary from a publication.yaml or collection.yaml file."""
    path = pathlib.Path(path).absolute()

    if vars is None:
        vars = {}

    if path.name == 'collection.yaml':
        return _resolve_collection_file(path, vars)
    elif path.name == 'publication.yaml':
        return _resolve_publication_file(path, vars)
    else:
        raise ValueError('The path is not to a collection.yaml or publication.yaml')


def _resolve_collection_file(path, vars):
    return read_collection_file(path, vars)


def _resolve_publication_file(path, vars):
    # 1. find the collection that the publication belongs to
    collection_dir = _find_parent_collection_root(path.parent)

    if collection_dir is not None:
        publication_schema = read_collection_file(collection_dir / constants.COLLECTION_FILE, vars).publication_schema
        previous_path = _find_previous(path, collection_dir)
        if previous_path is not None:
            previous = _resolve_publication_file(previous_path, vars)
        else:
            previous = None
    else:
        publication_schema = None
        previous = None

    # 2. if the collection is ordered, find all publications within that collection and
    #    the one before the current publication in order to set the "previous" variable

    return read_publication_file(path, publication_schema=publication_schema, vars=vars,
            previous=previous)


def _find_parent_collection_root(dir_path):
    # we are at the root of the filesystem
    if dir_path == dir_path.parent:
        return None

    if (dir_path / constants.COLLECTION_FILE).is_file():
        return dir_path

    return _find_parent_collection_root(dir_path.parent)


def _find_previous(this_publication_path, collection_root):
    all_publications = sorted(pathlib.Path(collection_root).glob('**/publication.yaml'))
    index = all_publications.index(this_publication_path.absolute())
    if index == 0:
        return None
    else:
        return all_publications[index - 1]

