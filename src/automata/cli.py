import datetime
import functools
import pathlib
from collections.abc import Callable
from typing import Any, Optional

import typer

from ._automata import Automata
from .config import CONFIGURATION_FILENAME, find_config
from .exceptions import Error
from .materials import serialize

app = typer.Typer()


def _command(*args: Any, **kwargs: Any) -> Callable:
    """Like ``app.command``, but reports automata errors without a traceback.

    An :class:`automata.exceptions.Error` raised by the command is printed as
    one ``Error: ...`` line, and the command exits with status 1.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*fn_args: Any, **fn_kwargs: Any) -> Any:
            try:
                return fn(*fn_args, **fn_kwargs)
            except Error as e:
                typer.echo(f"Error: {e}", err=True)
                raise typer.Exit(code=1)

        return app.command(*args, **kwargs)(wrapper)

    return decorator


def _parse_current_time(value: str) -> datetime.datetime:
    """Parse --current-time argument to datetime.

    Supports two formats:
    - ISO datetime: "2024-09-15T12:00:00"
    - Relative days: "+5" (5 days in future), "-3" (3 days in past)
    """
    try:
        n_days = int(value)
        return datetime.datetime.now() + datetime.timedelta(days=n_days)
    except ValueError:
        pass

    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f'Invalid --current-time value: "{value}". '
            f'Expected ISO datetime (e.g., "2024-09-15T12:00:00") '
            f'or relative days (e.g., "+5" or "-3").'
        )


def _get_current_time(current_time: str | None) -> datetime.datetime | None:
    """Parse the --current-time option, exiting on error."""
    if current_time is None:
        return None
    try:
        parsed = _parse_current_time(current_time)
        typer.echo(f"Running as if it is currently {parsed}")
        return parsed
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


_current_time_option = typer.Option(
    None,
    "--current-time",
    help=(
        "Override the current time for release time checks and scheduling. "
        "Accepts ISO datetime (e.g., '2024-09-15T12:00:00') or relative days "
        "(e.g., '+5' for 5 days in the future, '-3' for 3 days in the past)."
    ),
)


def _find_project_root() -> pathlib.Path | None:
    """The nearest directory, at or above the cwd, containing automata.yaml."""
    config_path = find_config(pathlib.Path.cwd())
    return None if config_path is None else config_path.parent


def _project() -> Automata:
    """Load the project enclosing the current directory, exiting on error.

    Searches upward from the current directory for automata.yaml, and says
    which project is used when it is not the current directory.
    """
    root = _find_project_root()
    if root is None:
        typer.echo(
            f"Error: No {CONFIGURATION_FILENAME} found in {pathlib.Path.cwd()} or "
            f"any parent directory.",
            err=True,
        )
        raise typer.Exit(code=1)

    if root != pathlib.Path.cwd():
        typer.echo(f"Using project at {root}", err=True)

    try:
        return Automata(root)
    except Error as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@_command()
def build(current_time: Optional[str] = _current_time_option):
    """Run the full pipeline and produce the site in the build directory."""
    _project().build(current_time=_get_current_time(current_time))


def _complete_publish_targets(incomplete: str) -> list[str]:
    """Return matching publish target names for shell tab-completion."""
    try:
        root = _find_project_root()
        if root is None:
            return []
        project = Automata(root)
        return [name for name in project.config.publish if name.startswith(incomplete)]
    except Exception:
        return []


@_command()
def publish(
    target: Optional[str] = typer.Argument(
        None,
        help="Publish target name. Defaults to all configured targets.",
        autocompletion=_complete_publish_targets,
    ),
    current_time: Optional[str] = _current_time_option,
):
    """Run the full pipeline and deploy the built site."""
    project = _project()
    published = project.publish(
        target=target, current_time=_get_current_time(current_time)
    )

    for name in published:
        typer.echo(f"Published to {name}.")


@_command()
def discover():
    """Discover materials and print a summary."""
    project = _project()
    universe = project.discover()
    for name, collection in universe.collections.items():
        n = len(collection.publications)
        typer.echo(f"{name}: {n} publication(s)")


@_command(name="clean-build-directory")
def clean_build_directory():
    """Empty the build directory, keeping top-level dot-entries."""
    _project().clean_build_directory()
    typer.echo("Build directory cleaned.")


@_command(name="build-materials")
def build_materials(current_time: Optional[str] = _current_time_option):
    """Discover and build materials (run recipes, check release times)."""
    project = _project()
    discovered = project.discover()
    project.build_materials(discovered, current_time=_get_current_time(current_time))
    typer.echo("Materials built.")


@_command()
def export(current_time: Optional[str] = _current_time_option):
    """Discover, build, and export materials to the build directory."""
    project = _project()
    discovered = project.discover()
    built = project.build_materials(
        discovered, current_time=_get_current_time(current_time)
    )
    project.export(built)
    typer.echo("Materials exported.")


@_command(name="render-website")
def render_website(current_time: Optional[str] = _current_time_option):
    """Render the website from previously exported materials."""
    project = _project()
    materials = project.load_exported_materials()
    project.render_website(materials, current_time=_get_current_time(current_time))
    typer.echo("Website rendered.")


@_command()
def resolve(
    path: pathlib.Path = typer.Argument(
        ...,
        help="Path to the publication.yaml file to resolve.",
    ),
):
    """Resolve a publication.yaml file and output as JSON."""
    project = _project()
    try:
        publication = project.resolve(path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"Error resolving publication file: {e}", err=True)
        raise typer.Exit(code=1)

    try:
        typer.echo(serialize(publication))
    except Exception as e:
        typer.echo(f"Error serializing publication: {e}", err=True)
        raise typer.Exit(code=1)


@_command()
def status():
    """Check status of course materials."""
    print("All good.")


def main():
    app()


if __name__ == "__main__":
    main()
