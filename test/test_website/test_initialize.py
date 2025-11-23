"""Tests for site generator initialization."""

import pathlib

from pytest import fixture

import automata.website


@fixture
def output_directory(tmpdir):
    output_path = pathlib.Path(tmpdir) / "output"
    output_path.mkdir()
    return output_path


def test_initializes_coursepage(output_directory):
    automata.website.initialize(output_directory / "website")

    assert (output_directory / "website").exists()
    assert (output_directory / "website" / "theme" / "base.html").exists()
    assert (output_directory / "website" / "config.yaml").exists()
    assert (output_directory / "website" / "pages").is_dir()
