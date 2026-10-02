"""Loading pages and static content from a content directory."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

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
    # the file each output path comes from, and a file in each directory of the
    # output, to find two files that would have the same path in the built site
    sources = _Sources()

    for dirpath, dirnames, filenames in content_directory.walk(top_down=True):
        dirpath = Path(dirpath)

        # skip the materials directory
        if dirpath == materials_directory:
            dirnames.clear()
            continue

        for filename in sorted(filenames):
            file_path = dirpath / filename
            relative = file_path.relative_to(content_directory)

            # handle no_render_suffix: treat as static, strip suffix (unless that
            # would leave no name, as for a file named ".no_render")
            if (
                no_render_suffix
                and filename.lower().endswith(no_render_suffix.lower())
                and len(filename) > len(no_render_suffix)
            ):
                output_key = str(relative)[: -len(no_render_suffix)]
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


class _Sources:
    """The content files that become each path of the built site."""

    def __init__(self) -> None:
        # the file each output path comes from
        self.files: dict[str, Path] = {}
        # for each directory of the output, a file that becomes a path inside it
        self.directories: dict[str, Path] = {}


def _claim(output_key: str, file_path: Path, sources: _Sources) -> None:
    """Record that *file_path* becomes *output_key*, unless that conflicts.

    Two files can't become the same path, and a file can't become a path where
    another file's output needs a directory.
    """

    def conflict(file: Path, inside: Path, key: str) -> Error:
        return Error(
            f"{file} would become {key} in the built site, but {inside} would be "
            f"inside a directory with that name. Rename or remove one of them."
        )

    if output_key in sources.files:
        raise Error(
            f"{sources.files[output_key]} and {file_path} would both become "
            f"{output_key} in the built site. Rename or remove one of them."
        )
    if output_key in sources.directories:
        raise conflict(file_path, sources.directories[output_key], output_key)

    parents = [str(parent) for parent in PurePosixPath(output_key).parents][:-1]
    for parent in parents:
        if parent in sources.files:
            raise conflict(sources.files[parent], file_path, parent)

    sources.files[output_key] = file_path
    for parent in parents:
        sources.directories.setdefault(parent, file_path)
