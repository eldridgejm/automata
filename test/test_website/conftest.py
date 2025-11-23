"""Shared fixtures for website tests."""

import json
import pathlib
import shutil
from textwrap import dedent

import pytest

import automata.materials


class SiteBuilder:
    """Helper for constructing website test fixtures."""

    def __init__(self, path: pathlib.Path):
        """Initialize a temporary site with base theme and config."""
        self.path = path
        self.builddir = self.path / "_build"
        self.builddir.mkdir()
        (self.path / "pages").mkdir()
        (self.path / "static").mkdir()

        shutil.copytree(
            pathlib.Path(__file__).parent / "basic_theme", self.path / "theme"
        )

        (self.path / "config.yaml").write_text(
            dedent(
                """
                theme:
                    page_title: "example theme"
                """
            )
        )

    def make_page(self, name: str, content: str) -> None:
        """Create a markdown page under pages/."""
        path = self.path / "pages" / name
        path.write_text(content)

    def make_theme_page(self, name: str, content: str) -> None:
        """Create a theme page under theme/pages/."""
        path = self.path / "theme" / "pages" / name
        path.write_text(content)

    def add_to_config(self, content: str) -> None:
        """Append raw YAML content to config.yaml."""
        with (self.path / "config.yaml").open("a") as fileobj:
            fileobj.write(dedent(content))

    def use_example_published(self, name: str = "basic_published") -> pathlib.Path:
        """Copy a sample published materials directory into _build/published."""
        src = pathlib.Path(__file__).parent / name
        dst = self.builddir / "published"
        shutil.copytree(src, dst)
        return dst

    def use_example_theme(self, name: str) -> pathlib.Path:
        """Replace theme/ with another theme fixture."""
        src = pathlib.Path(__file__).parent / name
        dst = self.path / "theme"
        shutil.copytree(src, dst)
        return dst

    def get_output(self, name: str) -> str:
        """Read rendered output content from _build/."""
        return (self.builddir / name).read_text()

    def write_materials(self, data: dict | automata.materials.Universe) -> pathlib.Path:
        """Write materials.json from a raw dict or Universe."""
        if isinstance(data, automata.materials.Universe):
            serialized = automata.materials.serialize(data)
        else:
            serialized = json.dumps(data)

        dst = self.builddir / "published"
        dst.mkdir(parents=True, exist_ok=True)
        with (dst / "materials.json").open("w") as fileobj:
            fileobj.write(serialized)
        return dst


@pytest.fixture
def site(tmp_path) -> SiteBuilder:
    return SiteBuilder(pathlib.Path(tmp_path))
