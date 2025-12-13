import smartconfig


class Config(smartconfig.Prototype):
    """Configuration for the website."""

    content_directory: str
    materials_directory_name: str = "materials"
    build_directory: str

    no_render_suffix: str | None = ".no_render"
