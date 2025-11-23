"""Shared fixtures for website tests."""

import json
import pathlib
import shutil
from textwrap import dedent

import pytest


class SiteBuilder:
    """Helper for constructing website test fixtures."""

    def __init__(self, path: pathlib.Path):
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
        path = self.path / "pages" / name
        path.write_text(content)

    def make_theme_page(self, name: str, content: str) -> None:
        path = self.path / "theme" / "pages" / name
        path.write_text(content)

    def add_to_config(self, content: str) -> None:
        with (self.path / "config.yaml").open("a") as fileobj:
            fileobj.write(dedent(content))

    def use_example_published(self, name: str = "basic_published") -> pathlib.Path:
        src = pathlib.Path(__file__).parent / name
        dst = self.builddir / "published"
        shutil.copytree(src, dst)
        return dst

    def use_example_theme(self, name: str) -> pathlib.Path:
        src = pathlib.Path(__file__).parent / name
        dst = self.path / "theme"
        shutil.copytree(src, dst)
        return dst

    def write_materials(self, data: dict) -> pathlib.Path:
        dst = self.builddir / "published"
        dst.mkdir(parents=True, exist_ok=True)
        with (dst / "materials.json").open("w") as fileobj:
            json.dump(data, fileobj)
        return dst

    def get_output(self, name: str) -> str:
        return (self.builddir / name).read_text()


@pytest.fixture
def site(tmp_path) -> SiteBuilder:
    return SiteBuilder(pathlib.Path(tmp_path))
