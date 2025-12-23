import smartconfig


class Config(smartconfig.Prototype):
    """Configuration for the website."""

    # path to the directory containing the pages and materials
    content_directory: str

    # name of the subdirectory within the content directory that contains
    # the materials to be included in the website
    materials_directory_name: str = "materials"

    # path to the output directory where the website will be built
    build_directory: str

    # suffix indicating that a file should not be rendered. If None, all files
    # will be rendered.
    no_render_suffix: str | None = ".no_render"

    # base path for the website (e.g., "/" or "/course/")
    base_path: str = "/"
