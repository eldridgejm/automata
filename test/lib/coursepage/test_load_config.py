from textwrap import dedent
import pathlib

from pytest import fixture

import automata.lib.coursepage


@fixture
def write_file(tmpdir):
    tmpdir = pathlib.Path(tmpdir)

    def inner(name, contents):
        path = tmpdir / name
        with path.open("w") as fileobj:
            fileobj.write(contents)
        return path

    return inner


def test_load_config(write_file):
    # given
    config_yaml = dedent(
        """
        foo: !include foo.yaml
        testing:
            bar: !include bar.yaml
        """
    )

    foo_yaml = dedent(
        """
        x: 1
        y: 2
        """
    )

    bar_yaml = dedent(
        """
        - 1
        - 2
        - 3
        """
    )

    path = write_file("config.yaml", config_yaml)
    write_file("foo.yaml", foo_yaml)
    write_file("bar.yaml", bar_yaml)

    # when
    config = automata.lib.coursepage.load_config(path)

    # then
    assert config["foo"]["x"] == 1
    assert config["testing"]["bar"] == [1, 2, 3]
