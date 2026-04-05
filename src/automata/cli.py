import datetime
import pathlib
from typing import Optional

import typer

from ._automata import Automata
from .materials import serialize

app = typer.Typer()


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


@app.command()
def generate(current_time: Optional[str] = _current_time_option):
    """Run the full pipeline: discover, build, export, and generate website."""
    Automata().generate(current_time=_get_current_time(current_time))


@app.command()
def discover():
    """Discover materials and print a summary."""
    project = Automata()
    universe = project.discover()
    for name, collection in universe.collections.items():
        n = len(collection.publications)
        typer.echo(f"{name}: {n} publication(s)")


@app.command(name="build-materials")
def build_materials(current_time: Optional[str] = _current_time_option):
    """Discover and build materials (run recipes)."""
    project = Automata()
    discovered = project.discover()
    project.build_materials(discovered, current_time=_get_current_time(current_time))
    typer.echo("Materials built.")


@app.command()
def export(current_time: Optional[str] = _current_time_option):
    """Discover, build, and export materials to the build directory."""
    project = Automata()
    discovered = project.discover()
    built = project.build_materials(
        discovered, current_time=_get_current_time(current_time)
    )
    project.export(built)
    typer.echo("Materials exported.")


@app.command()
def resolve(
    path: pathlib.Path = typer.Argument(
        ...,
        help="Path to the publication.yaml file to resolve.",
    ),
):
    """Resolve a publication.yaml file and output as JSON."""
    try:
        project = Automata()
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


@app.command()
def status():
    """Check status of course materials."""
    print("All good.")


def main():
    app()


if __name__ == "__main__":
    main()
