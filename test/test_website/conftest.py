"""Shared fixtures for website tests."""

import json
import pathlib
import shutil

import pytest

import automata.materials
import automata.website


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
        """Initialize a temporary site.

        Creates the following directory structure:
            path/
            ├── _build/                  # Output directory
            │   └── materials/
            │       └── materials.json   # Empty materials universe
            ├── pages/                   # Markdown pages directory
            ├── static/                  # Static assets directory
            └── theme/                   # Theme directory (copied from basic_theme)

        Parameters
        ----------
        path : pathlib.Path
            Root directory for the test site.

        """
        self.path = path
        self.builddir = self.path / "_build"
        self.builddir.mkdir()
        (self.path / "pages").mkdir()
        (self.path / "static").mkdir()

        # copy the theme into theme/
        shutil.copytree(
            pathlib.Path(__file__).parent / "basic_theme", self.path / "theme"
        )

        # write an empty materials.json to start
        self.write_materials({"collections": {}})

    def make_page(self, name: str, content: str) -> None:
        """Create a markdown page under pages/.

        Parameters
        ----------
        name : str
            Filename of the page (e.g., "index.md").
        content : str
            Markdown content for the page.

        """
        path = self.path / "pages" / name
        path.write_text(content)

    def make_theme_page(self, name: str, content: str) -> None:
        """Create a theme page under theme/pages/.

        Parameters
        ----------
        name : str
            Filename of the theme page.
        content : str
            Page content.

        """
        path = self.path / "theme" / "pages" / name
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
        dst = self.builddir / "materials"
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return dst

    def use_example_theme(self, name: str) -> pathlib.Path:
        """Replace theme/ with another theme fixture.

        Parameters
        ----------
        name : str
            Name of the theme directory in the test fixtures.

        Returns
        -------
        pathlib.Path
            Path to the theme directory.

        """
        src = pathlib.Path(__file__).parent / name
        dst = self.path / "theme"
        shutil.copytree(src, dst)
        return dst

    def get_output(self, name: str) -> str:
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
        return (self.builddir / name).read_text()

    def write_materials(self, data: dict | automata.materials.Universe) -> pathlib.Path:
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

        dst = self.builddir / "materials"
        dst.mkdir(parents=True, exist_ok=True)
        with (dst / "materials.json").open("w") as fileobj:
            fileobj.write(serialized)
        return dst


@pytest.fixture
def site(tmp_path) -> SiteBuilder:
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


@pytest.fixture
def config(site):
    """Provide a basic Config instance for website generation tests.

    Parameters
    ----------
    site : SiteBuilder
        The site builder fixture providing input/output paths.

    Returns
    -------
    automata.website.Config
        A Config object with basic theme configuration and no elements.

    """
    return automata.website.Config._from_dict(
        {
            "input_path": str(site.path),
            "output_path": str(site.builddir),
            "theme": {"name": "basic", "config": {"page_title": "Test Course"}},
            "elements": {},
        }
    )
