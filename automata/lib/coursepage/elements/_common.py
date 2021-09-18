def is_something_missing(publication, requirements):
    for artifact in requirements["artifacts"]:
        if artifact not in publication.artifacts:
            return True
    for metadata in requirements["non_null_metadata"]:
        if metadata not in publication.metadata or publication.metadata[metadata] is None:
            return True
    for metadata in requirements["metadata"]:
        if metadata not in publication.metadata:
            return True
    return False
