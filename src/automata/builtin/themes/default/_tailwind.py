"""Rebuilding the default theme's Tailwind CSS for the built site."""

import logging
import pathlib
import subprocess
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# the default theme's directory, which holds style.input.css
THEME_DIRECTORY = pathlib.Path(__file__).parent.resolve()


def rebuild_css(
    build_directory: pathlib.Path,
    config: dict[str, Any],
    *,
    run: Callable[..., Any] = subprocess.run,
    theme_directory: pathlib.Path = THEME_DIRECTORY,
) -> None:
    """Rebuild the site's Tailwind CSS so it includes classes used in its pages.

    The theme ships pre-built CSS, which only contains the Tailwind classes the
    theme itself uses. This runs the Tailwind CLI over the built HTML, so that
    classes used in the course's own pages are included as well.

    Problems never fail the build: if npx is not installed, the CLI fails, or
    the theme's ``style.input.css`` is missing, a warning is logged and the
    pre-built CSS is kept.

    Parameters
    ----------
    build_directory : pathlib.Path
        The build output directory.
    config : dict
        The theme's resolved configuration. Setting ``rebuild_tailwind`` to
        false disables the rebuild.
    run : Callable
        Runs the command (default :func:`subprocess.run`). Tests pass a fake.
    theme_directory : pathlib.Path
        The directory containing ``style.input.css``.

    """
    if not config.get("rebuild_tailwind", True):
        return

    build_dir = pathlib.Path(build_directory)
    css_input = theme_directory / "style.input.css"
    if not css_input.exists():
        logger.warning(
            f"Tailwind input file style.input.css not found at {css_input} - "
            f"using pre-built Tailwind CSS."
        )
        return

    try:
        logger.info("Rebuilding Tailwind CSS with custom classes...")
        _rebuild_tailwind(css_input, build_dir / "static" / "style.css", build_dir, run)
        logger.info("Tailwind CSS rebuilt successfully")
    except FileNotFoundError:
        logger.warning(
            "npx not found - using pre-built Tailwind CSS. "
            "Install Node.js to enable automatic Tailwind rebuilds with custom classes."
        )
    except subprocess.SubprocessError as e:
        logger.warning(f"Failed to rebuild Tailwind CSS: {e}. Using pre-built CSS.")


def _rebuild_tailwind(
    input_css: pathlib.Path,
    output_css: pathlib.Path,
    content_dir: pathlib.Path,
    run: Callable[..., Any],
) -> None:
    """Run the Tailwind CLI to rebuild *output_css* from *input_css*.

    Tailwind v4 scans all files in its working directory for class names, so
    it runs from *content_dir*, the build directory.

    Raises
    ------
    FileNotFoundError
        If npx is not installed.
    subprocess.SubprocessError
        If the CLI fails or times out.

    """
    # resolve paths before changing the working directory
    input_css_abs = input_css.resolve()
    output_css_abs = output_css.resolve()
    content_dir_abs = content_dir.resolve()

    output_css_abs.parent.mkdir(parents=True, exist_ok=True)

    run(
        [
            "npx",
            "@tailwindcss/cli",
            "-i",
            str(input_css_abs),
            "-o",
            str(output_css_abs),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
        cwd=str(content_dir_abs),
    )
