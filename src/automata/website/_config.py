import dataclasses
import pathlib


@dataclasses.dataclass
class Config:
    """Configuration for the website."""

    content_directory: pathlib.Path
    build_directory: pathlib.Path

    no_render_suffix: str | None = ".no_render"
