from collections import deque


def _yaml_io(cls):

    def load(self):
        pass

    def dump(self):
        pass

    cls.load = load
    cls.dump = dump


@_yaml_io
class CollectionFile:

    def __init__(self, path):
        self.path = path


@_yaml_io
class PublicationFile:

    def __init__(self, path, collection_file=None):
        self.path = path
        self.collection_file = collection_file


def find_collection_files():
    """
    Returns
    -------
    List[CollectionFile]
    """

def find_publication_files():
    """
    Returns
    -------
    List[PublicationFile]
    """


def _is_collection(path):
    """Determine if the path is a collection."""
    return (path / COLLECTION_FILE).is_file()


def _is_publication(path):
    """Determine if the path is a publication."""
    return (path / PUBLICATION_FILE).is_file()


def find_definition_files(root, skip_directories):
    if skip_directories is None:
        skip_directories = set()

    queue = deque([(root, None)])

    collections = []
    publications = {}

    while queue:
        current_path, parent_collection = queue.pop()

        if _is_collection(current_path):
            if parent_collection is not None:
                raise DiscoveryError(f"Nested collection found.", current_path)

            collection = CollectionFile(current_path/ COLLECTION_FILE)
            collections.append(collection)
            parent_collection = collection

        if _is_publication(current_path):
            publication = PublicationFile(current_path / PUBLICATION_FILE, parent_collection)
            publications.append(publication)

        for subpath in current_path.iterdir():
            if subpath.is_dir():
                if subpath.name in skip_directories:
                    continue
                queue.append((subpath, parent_collection))

    return collections, publications
