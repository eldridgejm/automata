"""Shared fixtures for website tests."""

import json
import pathlib
import shutil

import pytest

import automata.materials


class SiteBuilder:
    """Helper for constructing website test fixtures.

    Provides a convenient interface for setting up temporary website structures
    with pages, themes, and materials for testing the website generation pipeline.

    Attributes
    ----------
    path : pathlib.Path
        Root directory of the test site.
    builddir : pathlib.Path
        Build output directory (_build/).

    """

    def __init__(self, path: pathlib.Path):
        """Initialize a temporary site in the given path.

        Parameters
        ----------
        path : pathlib.Path
            Root directory for the test site.

        """
        self.content_path = path / "content"
        self.content_path.mkdir(parents=True)

        self.output_path = path / "_build"
        self.output_path.mkdir()

        self.materials_path = self.output_path / "materials"

        # write an empty materials.json to start
        self.write_materials_json({"collections": {}})

    def make_page(self, filepath: str, content: str) -> None:
        """Create a markdown page under content/.

        Parameters
        ----------
        name : str
            Filename of the page (e.g., "index.md").
        content : str
            Markdown content for the page.

        """
        path = self.content_path / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def use_example_materials(self, name: str = "basic_published") -> pathlib.Path:
        """Copy a sample published materials directory into _build/materials.

        Parameters
        ----------
        name : str, optional
            Name of the example materials directory in the test fixtures.
            Default is "basic_published".

        Returns
        -------
        pathlib.Path
            Path to the copied materials directory (_build/materials).

        """
        src = pathlib.Path(__file__).parent / name
        dst = self.output_path / "materials"
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return dst

    def get_output(self, filepath: str) -> str:
        """Read rendered output content from _build/.

        Parameters
        ----------
        name : str
            Filename in the build directory (e.g., "index.html").

        Returns
        -------
        str
            Contents of the output file.

        """
        return (self.output_path / filepath).read_text()

    def write_materials_json(
        self, data: dict | automata.materials.Universe
    ) -> pathlib.Path:
        """Write materials.json from a raw dict or Universe.

        Parameters
        ----------
        data : dict or automata.materials.Universe
            Either a raw dictionary representing materials data or a Universe
            object to serialize.

        Returns
        -------
        pathlib.Path
            Path to the materials directory (_build/materials).

        """
        if isinstance(data, automata.materials.Universe):
            serialized = automata.materials.serialize(data)
        else:
            serialized = json.dumps(data)

        dst = self.output_path / "materials"
        dst.mkdir(parents=True, exist_ok=True)
        with (dst / "materials.json").open("w") as fileobj:
            fileobj.write(serialized)
        return dst


@pytest.fixture
def tmpsite(tmp_path) -> SiteBuilder:
    """Provide a SiteBuilder instance in a temporary directory.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest's temporary directory fixture.

    Returns
    -------
    SiteBuilder
        A SiteBuilder instance configured in the temporary directory.

    """
    return SiteBuilder(pathlib.Path(tmp_path))
