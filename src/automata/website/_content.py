"""Loading pages and static content from a content directory."""

from dataclasses import dataclass
from pathlib import Path

from ..exceptions import Error


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
    # the file each output path comes from, to find two with the same one
    sources: dict[str, Path] = {}

    for dirpath, dirnames, filenames in content_directory.walk(top_down=True):
        dirpath = Path(dirpath)

        # skip the materials directory
        if dirpath == materials_directory:
            dirnames.clear()
            continue

        for filename in sorted(filenames):
            file_path = dirpath / filename
            relative = file_path.relative_to(content_directory)

            # handle no_render_suffix: treat as static, strip suffix. Only a file
            # with another suffix before it (data.csv.no_render) is a no-render file
            if (
                no_render_suffix
                and file_path.suffix.lower() == no_render_suffix
                and len(file_path.suffixes) > 1
            ):
                output_key = str(relative.with_suffix(""))
                _claim(output_key, file_path, sources)
                static_content[output_key] = file_path.read_bytes()
            elif file_path.suffix.lower() in (".md", ".html"):
                # pages keys are output paths; .md files become .html
                output_key = str(relative.with_suffix(".html"))
                _claim(output_key, file_path, sources)
                pages[output_key] = Page(file_path.read_text(), file_path)
            else:
                _claim(str(relative), file_path, sources)
                static_content[str(relative)] = file_path.read_bytes()

    return pages, static_content


def _claim(output_key: str, file_path: Path, sources: dict[str, Path]) -> None:
    """Record that *file_path* becomes *output_key*, unless another file does."""
    if output_key in sources:
        raise Error(
            f"{sources[output_key]} and {file_path} would both become {output_key} "
            f"in the built site. Rename or remove one of them."
        )
    sources[output_key] = file_path
