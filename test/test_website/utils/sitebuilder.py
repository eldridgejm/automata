import json
import pathlib

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

    def load_content(
        self, no_render_suffix: str | None = ".no_render"
    ) -> tuple[dict[str, str], dict[str, str | bytes]]:
        """Load pages and static content from the content directory.

        Parameters
        ----------
        no_render_suffix : str | None
            Files with this suffix are treated as static content with the
            suffix stripped from the output path.

        Returns
        -------
        tuple[dict[str, str], dict[str, str | bytes]]
            (pages, static_content) suitable for passing to render().

        """
        pages: dict[str, str] = {}
        static_content: dict[str, str | bytes] = {}

        for dirpath, dirnames, filenames in self.content_directory.walk(top_down=True):
            dirpath = pathlib.Path(dirpath)

            if dirpath == self.materials_directory:
                dirnames.clear()
                continue

            for filename in filenames:
                file_path = dirpath / filename
                relative = file_path.relative_to(self.content_directory)

                if (
                    no_render_suffix
                    and file_path.suffix.lower() == no_render_suffix
                    and len(file_path.suffixes) > 1
                ):
                    static_content[str(relative.with_suffix(""))] = (
                        file_path.read_bytes()
                    )
                elif file_path.suffix.lower() in (".md", ".html"):
                    # pages keys are output paths; .md files become .html
                    output_key = str(relative.with_suffix(".html"))
                    pages[output_key] = file_path.read_text()
                else:
                    static_content[str(relative)] = file_path.read_bytes()

        return pages, static_content

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
