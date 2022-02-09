import pathlib
from itertools import chain

from pytest import fixture, raises

from automata import find_definition_files, DiscoveryError


@fixture
def root(tmpdir):
    return pathlib.Path(tmpdir)


def all_collections(found_files):
    return [c for c, _ in found_files]


def all_publications(found_files):
    return list(chain(*(pubs for _, pubs in found_files)))


@fixture
def make_file(root):
    """Make a file in the temporary directory, creating any parent dirs necessary."""

    def fixture(filepath):
        filepath = root / filepath
        parent = filepath.parent
        parent.mkdir(parents=True, exist_ok=True)
        filepath.touch(exist_ok=True)

    return fixture


def test_simple_example(make_file, root):
    make_file('homeworks/collection.yaml')
    make_file('homeworks/01-intro/publication.yaml')
    make_file('homeworks/02-something/publication.yaml')
    make_file('labs/collection.yaml')
    make_file('labs/01-foo/publication.yaml')
    make_file('labs/02-bar/publication.yaml')
    found = find_definition_files(root)

    assert len(all_collections(found)) == 2
    assert len(all_publications(found)) == 4

    assert all_publications(found)[0].parent_collection_file == all_collections(found)[0]


def test_results_in_dfs_alphabetical_order(make_file, root):
    make_file('homeworks/collection.yaml')
    make_file('homeworks/01-intro/publication.yaml')
    make_file('homeworks/01-intro/subpub/publication.yaml')
    make_file('homeworks/01-intro/alpha/publication.yaml')
    make_file('homeworks/02-something/publication.yaml')
    make_file('homeworks/03-baz/publication.yaml')
    make_file('labs/collection.yaml')
    make_file('labs/01-foo/publication.yaml')
    make_file('labs/02-bar/publication.yaml')

    found = find_definition_files(root)

    pubs = all_publications(found)

    assert pubs[0].path.parent == root / 'homeworks' / '01-intro'
    assert pubs[1].path.parent == root / 'homeworks' / '01-intro' / 'alpha'
    assert pubs[2].path.parent == root / 'homeworks' / '01-intro' / 'subpub'
    assert pubs[3].path.parent == root / 'homeworks' / '02-something'
    assert pubs[4].path.parent == root / 'homeworks' / '03-baz'
    assert pubs[5].path.parent == root / 'labs' / '01-foo'

def test_publications_in_same_directory_as_collection_have_it_as_parent(make_file, root):
    make_file('homeworks/collection.yaml')
    make_file('homeworks/publication.yaml')

    found = find_definition_files(root)
    assert all_publications(found)[0].parent_collection_file == all_collections(found)[0]


def test_singleton_publications_have_none_as_parent_collection(make_file, root):
    make_file('textbook/publication.yaml')

    found = find_definition_files(root)
    assert len(all_collections(found)) == 1
    assert all_publications(found)[0].parent_collection_file is None


def test_skips_directories_based_on_name(make_file, root):
    make_file('forbidden/publication.yaml')
    make_file('homeworks/forbidden/publication.yaml')
    make_file('homeworks/collection.yaml')
    make_file('homeworks/01-intro/publication.yaml')
    make_file('homeworks/02-something/publication.yaml')
    make_file('homeworks/03-baz/publication.yaml')
    make_file('homeworks/04-something/forbidden/publication.yaml')

    found = find_definition_files(root,
            skip_directories=['forbidden'])

    assert len(all_publications(found)) == 3
    assert 'forbidden' not in [pf.path.parent.name for pf in all_publications(found)]


def test_nested_collection_raises(make_file, root):
    make_file('homeworks/collection.yaml')
    make_file('homeworks/01-intro/publication.yaml')
    make_file('homeworks/01-intro/collection.yaml')

    with raises(DiscoveryError):
        find_definition_files(root)
