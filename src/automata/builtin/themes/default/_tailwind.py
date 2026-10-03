"""Rebuilding the default theme's Tailwind CSS for the built site."""

import logging
import os
import pathlib
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# the default theme's directory, which holds style.input.css and package.json
THEME_DIRECTORY = pathlib.Path(__file__).parent.resolve()

# where the theme's Node packages are installed: not in the theme's directory,
# which may not be writable (as when automata is installed)
CACHE_DIRECTORY = (
    pathlib.Path(os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache")
    / "automata"
    / "tailwind"
)

# the Node package files, copied to the cache to install them there
_PACKAGE_FILES = ("package.json", "package-lock.json")


def rebuild_css(
    build_directory: pathlib.Path,
    config: dict[str, Any],
    *,
    run: Callable[..., Any] = subprocess.run,
    theme_directory: pathlib.Path = THEME_DIRECTORY,
    cache_directory: pathlib.Path = CACHE_DIRECTORY,
) -> None:
    """Rebuild the site's Tailwind CSS so it includes classes used in its pages.

    The theme ships pre-built CSS, which only contains the Tailwind classes the
    theme itself uses. This runs the Tailwind CLI over the built HTML, so that
    classes used in the course's own pages are included as well.

    Tailwind and its plugins (the theme's ``package.json``) are installed with
    npm into *cache_directory*, the first time and whenever they change. The
    theme's ``style.input.css`` is copied there too, so that its imports
    resolve, and the CLI runs from the build directory, where it looks for
    classes.

    Problems never fail the build: if npm is not installed, installing or the
    CLI fails, or the theme's ``style.input.css`` is missing, a warning is
    logged and the pre-built CSS is kept.

    Parameters
    ----------
    build_directory : pathlib.Path
        The build output directory.
    config : dict
        The theme's resolved configuration. Setting ``rebuild_tailwind`` to
        false disables the rebuild.
    run : Callable
        Runs the commands (default :func:`subprocess.run`). Tests pass a fake.
    theme_directory : pathlib.Path
        The directory containing ``style.input.css`` and ``package.json``.
    cache_directory : pathlib.Path
        Where the packages are installed (in a ``default-theme`` directory).

    """
    if not config.get("rebuild_tailwind", True):
        return

    build_dir = pathlib.Path(build_directory).resolve()
    css_input = theme_directory / "style.input.css"
    if not css_input.exists():
        logger.warning(
            f"Tailwind input file style.input.css not found at {css_input} - "
            f"using pre-built Tailwind CSS."
        )
        return

    workdir = cache_directory / "default-theme"
    try:
        _install(theme_directory, workdir, run)
        shutil.copyfile(css_input, workdir / "style.input.css")
        output = build_dir / "static" / "style.css"
        output.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Rebuilding Tailwind CSS with custom classes...")
        run(
            [
                str(workdir / "node_modules" / ".bin" / "tailwindcss"),
                "-i",
                str(workdir / "style.input.css"),
                "-o",
                str(output),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            # Tailwind looks for classes in the directory it runs in
            cwd=str(build_dir),
        )
        logger.info("Tailwind CSS rebuilt successfully")
    except FileNotFoundError:
        logger.warning(
            "npm not found - using pre-built Tailwind CSS. Install Node.js to "
            "enable automatic Tailwind rebuilds with custom classes."
        )
    except (subprocess.SubprocessError, OSError) as e:
        logger.warning(f"Failed to rebuild Tailwind CSS: {e}. Using pre-built CSS.")


def _install(
    theme_directory: pathlib.Path, workdir: pathlib.Path, run: Callable[..., Any]
) -> None:
    """Install the theme's Node packages into *workdir*, unless the same ones
    already are.

    Raises
    ------
    FileNotFoundError
        If npm is not installed.
    subprocess.SubprocessError
        If installing fails or times out.

    """
    packages = "".join(
        (theme_directory / name).read_text()
        for name in _PACKAGE_FILES
        if (theme_directory / name).is_file()
    )
    # written once installing succeeds: what was installed
    installed = workdir / ".installed"
    if installed.is_file() and installed.read_text() == packages:
        return

    workdir.mkdir(parents=True, exist_ok=True)
    installed.unlink(missing_ok=True)
    for name in _PACKAGE_FILES:
        if (theme_directory / name).is_file():
            shutil.copyfile(theme_directory / name, workdir / name)
    logger.info("Installing Tailwind CSS (once)...")
    run(
        ["npm", "install", "--no-audit", "--no-fund", "--loglevel=error"],
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
        cwd=str(workdir),
    )
    installed.write_text(packages)
