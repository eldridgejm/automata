import datetime
import pathlib
import shutil

from pytest import fixture

from automata import api


EXAMPLE_CLASS = pathlib.Path(__file__).parent / "../../../example_class"


def example_class(tempdir, date):
    destination = tempdir / "example_class"
    shutil.copytree(EXAMPLE_CLASS, destination)

    builddir = destination / "website" / "_build"
    if builddir.exists():
        shutil.rmtree(builddir)

    builddir.mkdir()

    api.materials.publish(
        str(destination),
        str(destination / "website/_build/published"),
        skip_directories="template",
        now=date,
    )

    return destination


def clean_build(builddir):
    for f in builddir.iterdir():
        if not f.name == "published":
            if f.is_dir():
                shutil.rmtree(f)
            else:
                f.unlink()



@fixture(scope="module")
def publish_on_oct_16(tmp_path_factory):
    tempdir = tmp_path_factory.mktemp("example_16th")
    path = example_class(tempdir, datetime.datetime(2020, 10, 16, 0, 0, 0))
    clean_build(path / "website" / "_build")
    return path


def test_resolve_takes_a_path_and_returns_a_resolved_dictionary(publish_on_oct_16):

    # when
    resolved = api.materials.resolve(publish_on_oct_16 / 'homeworks' / '02-tables' / 'publication.yaml')

    # then
    resolved['artifacts']['homework.txt']['release_time'] == datetime.datetime(2020, 10, 7, 23, 59, 0)
