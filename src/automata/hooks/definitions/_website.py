"""Hook definitions for website generation operations.

This module contains hook classes for:
- pre_generate_website: Called before website generation
- post_generate_website: Called after website generation
"""

from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .._base import ScriptableHookMixin, WebsiteContent, hook_point

if TYPE_CHECKING:
    import datetime

    from ..._config import WebsiteConfig
    from ...materials import ExportedArtifact, Universe


@hook_point("pre_generate_website")
class PreGenerateWebsiteHook:
    """Hook called before website generation.

    Hooks form a pipeline: each hook receives the website content (content,
    assets, static_files) and returns potentially modified content. The output
    of one hook becomes the input to the next.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(
        self,
        website_content: WebsiteContent,
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: "datetime.datetime",
    ) -> WebsiteContent:
        """Called before website generation.

        Parameters
        ----------
        website_content : WebsiteContent
            The current website content (content, assets, static_files).
            Modify and return to affect the generated website.
        materials : Universe[ExportedArtifact]
            The exported materials universe.
        website_config : WebsiteConfig
            The website configuration.
        build_directory : Path
            Path to the build output directory.
        vars : dict[str, Any]
            Variables available for rendering.
        current_time : datetime.datetime
            The current build time.

        Returns
        -------
        WebsiteContent
            The (potentially modified) website content to pass to the next
            hook or to the generator.

        """
        ...


@hook_point("post_generate_website")
class PostGenerateWebsiteHook(ScriptableHookMixin):
    """Hook called after website generation.

    This hook is scriptable - it can be implemented as a shell script.

    Attributes
    ----------
    priority : int
        Execution priority (lower runs first).

    """

    priority: int

    @abstractmethod
    def __call__(
        self,
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: "datetime.datetime",
    ) -> None:
        """Called after website generation.

        Parameters
        ----------
        materials : Universe[ExportedArtifact]
            The exported materials universe.
        website_config : WebsiteConfig
            The website configuration.
        build_directory : Path
            Path to the build output directory.
        vars : dict[str, Any]
            Variables available for rendering.
        current_time : datetime.datetime
            The current build time.

        """
        ...

    @staticmethod
    def serialize_args(
        materials: "Universe[ExportedArtifact]",
        website_config: "WebsiteConfig",
        build_directory: Path,
        vars: dict[str, Any],
        current_time: "datetime.datetime",
    ) -> dict:
        """Serialize arguments for script execution.

        Parameters
        ----------
        materials : Universe[ExportedArtifact]
            The exported materials universe.
        website_config : WebsiteConfig
            The website configuration.
        build_directory : Path
            Path to the build output directory.
        vars : dict[str, Any]
            Variables available for rendering.
        current_time : datetime.datetime
            The current build time.

        Returns
        -------
        dict
            JSON-serializable dictionary of arguments.

        """
        from ... import materials as materials_module

        return {
            "materials": materials_module.serialize(materials),
            "config": {
                "content_directory": str(website_config.content_directory),
                "build_directory": str(website_config.build_directory),
                "materials_directory_name": website_config.materials_directory_name,
                "base_path": website_config.base_path,
            },
            "build_directory": str(build_directory),
            "vars": vars,
            "current_time": current_time.isoformat(),
        }
