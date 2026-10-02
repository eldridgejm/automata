# the file used to define a collection
COLLECTION_FILE = "collection.yaml"

# the file used to define a publication and its artifacts
PUBLICATION_FILE = "publication.yaml"

# the key of the collection of publications that aren't in a collection
DEFAULT_COLLECTION = "default"

# why a collection can't be named DEFAULT_COLLECTION
DEFAULT_COLLECTION_RESERVED = (
    f'The collection name "{DEFAULT_COLLECTION}" is reserved for publications '
    f"that aren't in a collection."
)
