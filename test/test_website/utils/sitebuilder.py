import json
import pathlib
from typing import cast

import automata.materials
from automata.materials import ExportedArtifact, ExportedMaterials, Universe
from automata.website import WebsiteContent


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
        self.content_directory = path / "content"
        self.content_directory.mkdir(parents=True)

        self.build_directory = path / "_build"
        self.build_directory.mkdir()

        self.materials_directory = self.content_directory / "materials"

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
        path = self.content_directory / filepath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

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
        return (self.build_directory / filepath).read_text()

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

        self.materials_directory.mkdir(parents=True, exist_ok=True)
        with (self.materials_directory / "materials.json").open("w") as fileobj:
            fileobj.write(serialized)
        return self.materials_directory

    @property
    def content(self) -> WebsiteContent:
        """Construct a WebsiteContent from the current materials directory."""
        materials_json_path = self.materials_directory / "materials.json"
        loaded = cast(
            Universe[ExportedArtifact],
            automata.materials.deserialize(materials_json_path.read_text()),
        )
        return WebsiteContent(
            materials=ExportedMaterials(root=self.materials_directory, universe=loaded)
        )
