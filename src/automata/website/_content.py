"""Loading pages and static content from a content directory."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Page:
    """A page to render, and the file it was read from.

    Parameters
    ----------
    content : str
        The page's text, including any frontmatter.
    source : Path | None
        The file the page was read from, named in error messages and used to
        resolve ``__include__`` in the frontmatter. None for pages that are not
        read from a file (e.g., pages added by extensions).

    """

    content: str
    source: Path | None = None


def load_content_directory(
    content_directory: Path,
    materials_directory: Path,
    no_render_suffix: str | None = ".no_render",
) -> tuple[dict[str, Page], dict[str, str | bytes]]:
    """Load pages and static content from a content directory.

    Walks the content directory (skipping the materials subdirectory) and
    separates files into pages (``.md`` and ``.html``) and static content
    (everything else).

    Parameters
    ----------
    content_directory : Path
        The directory containing pages and static files.
    materials_directory : Path
        The materials subdirectory to skip.
    no_render_suffix : str | None
        Files with this suffix are treated as static content with the suffix
        stripped from the output path.

    Returns
    -------
    tuple[dict[str, Page], dict[str, str | bytes]]
        A tuple of (pages, static_content).

    """
    pages: dict[str, Page] = {}
    static_content: dict[str, str | bytes] = {}

    for dirpath, dirnames, filenames in content_directory.walk(top_down=True):
        dirpath = Path(dirpath)

        # skip the materials directory
        if dirpath == materials_directory:
            dirnames.clear()
            continue

        for filename in filenames:
            file_path = dirpath / filename
            relative = str(file_path.relative_to(content_directory))

            # handle no_render_suffix: treat as static, strip suffix
            if (
                no_render_suffix
                and file_path.suffix.lower() == no_render_suffix
                and len(file_path.suffixes) > 1
            ):
                output_key = str(
                    file_path.relative_to(content_directory).with_suffix("")
                )
                static_content[output_key] = file_path.read_bytes()
            elif file_path.suffix.lower() in (".md", ".html"):
                # pages keys are output paths; .md files become .html
                output_key = str(
                    file_path.relative_to(content_directory).with_suffix(".html")
                )
                pages[output_key] = Page(file_path.read_text(), file_path)
            else:
                static_content[relative] = file_path.read_bytes()

    return pages, static_content
