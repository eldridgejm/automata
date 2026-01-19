"""Post-build hook to rebuild Tailwind CSS with user's custom classes."""

import logging
import pathlib
import subprocess

logger = logging.getLogger(__name__)


def _post_generate(
    materials,
    website_config,
    build_directory,
    vars,
    current_time,
):
    """Rebuild Tailwind CSS after site generation to include custom classes.

    This hook runs the Tailwind CLI to regenerate CSS by scanning the built
    HTML files. This ensures any custom Tailwind classes used by the user
    are included in the final CSS.

    If npx is not available, logs a warning and continues with the pre-built CSS.

    The rebuild can be disabled by setting `rebuild_tailwind: false` in the
    vars section of automata.yaml.

    Parameters
    ----------
    materials : Universe[ExportedArtifact]
        The exported materials universe.
    website_config : WebsiteConfig
        The website configuration.
    build_directory : Path
        Path to the build output directory.
    vars : dict
        Variables available for rendering.
    current_time : datetime
        The current build time.

    """
    # Check if rebuild is disabled via vars
    if not vars.get("rebuild_tailwind", True):
        return

    # Get build directory from context
    build_dir = pathlib.Path(build_directory)
    css_output = build_dir / "static" / "style.css"

    # Check if npx is available
    if not _is_npx_available():
        logger.warning(
            "npx not found - using pre-built Tailwind CSS. "
            "Install Node.js to enable automatic Tailwind rebuilds with custom classes."
        )
        return

    # Get theme directory (where style.input.css is located)
    theme_dir = _get_theme_directory()
    if theme_dir is None:
        logger.warning("Could not locate theme directory - skipping Tailwind rebuild")
        return

    css_input = theme_dir / "style.input.css"
    if not css_input.exists():
        logger.warning(f"Tailwind input file not found at {css_input}")
        return

    # Rebuild Tailwind CSS
    try:
        logger.info("Rebuilding Tailwind CSS with custom classes...")
        _rebuild_tailwind(css_input, css_output, build_dir)
        logger.info("Tailwind CSS rebuilt successfully")
    except Exception as e:
        logger.warning(f"Failed to rebuild Tailwind CSS: {e}. Using pre-built CSS.")


def _is_npx_available() -> bool:
    """Check if npx is available on the system.

    Returns
    -------
    bool
        True if npx is available, False otherwise.

    """
    try:
        subprocess.run(
            ["npx", "--version"],
            capture_output=True,
            check=True,
            timeout=5,
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError, TimeoutError):
        return False


def _get_theme_directory() -> pathlib.Path | None:
    """Get the directory containing the default theme.

    Uses __file__ to locate the theme directory at runtime.

    Returns
    -------
    pathlib.Path | None
        The theme directory path, or None if it cannot be determined.

    """
    try:
        # This file is in the hooks/ subdirectory of the theme directory
        return pathlib.Path(__file__).parent.parent.resolve()
    except NameError:
        return None


def _rebuild_tailwind(
    input_css: pathlib.Path,
    output_css: pathlib.Path,
    content_dir: pathlib.Path,
) -> None:
    """Rebuild Tailwind CSS using the CLI.

    Tailwind v4 automatically scans all files in the working directory.
    By setting cwd=content_dir, it will scan the build directory for HTML files.

    Parameters
    ----------
    input_css : pathlib.Path
        Path to style.input.css
    output_css : pathlib.Path
        Path where rebuilt CSS should be written
    content_dir : pathlib.Path
        Directory containing HTML files to scan for classes

    Raises
    ------
    RuntimeError
        If the Tailwind CLI fails to rebuild the CSS.

    """
    # Resolve all paths to absolute paths before changing cwd
    input_css_abs = input_css.resolve()
    output_css_abs = output_css.resolve()
    content_dir_abs = content_dir.resolve()

    # Ensure output directory exists
    output_css_abs.parent.mkdir(parents=True, exist_ok=True)

    # Run Tailwind CLI from the content directory so it scans HTML files there
    result = subprocess.run(
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

    if result.returncode != 0:
        raise RuntimeError(f"Tailwind CLI failed: {result.stderr}")


# Export hooks in the expected format
# Priority 100 means this runs after other hooks (lower priority runs first)
hooks = {
    "post_generate_website": [(100, _post_generate)],
}
