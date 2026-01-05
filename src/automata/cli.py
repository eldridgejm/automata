import datetime
import pathlib
from typing import Optional

import typer

from . import _build
from .config import find_config, read_config
from .materials import read_publication_file, serialize

app = typer.Typer()


def _parse_current_time(value: str) -> datetime.datetime:
    """Parse --current-time argument to datetime.

    Supports two formats:
    - ISO datetime: "2024-09-15T12:00:00"
    - Relative days: "+5" (5 days in future), "-3" (3 days in past)

    Parameters
    ----------
    value : str
        The time value to parse

    Returns
    -------
    datetime.datetime
        The parsed datetime

    Raises
    ------
    ValueError
        If the value cannot be parsed in either format
    """
    # Try parsing as relative days first (e.g., "+5" or "-3")
    try:
        n_days = int(value)
        return datetime.datetime.now() + datetime.timedelta(days=n_days)
    except ValueError:
        pass

    # Try parsing as ISO datetime
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        raise ValueError(
            f'Invalid --current-time value: "{value}". '
            f'Expected ISO datetime (e.g., "2024-09-15T12:00:00") '
            f'or relative days (e.g., "+5" or "-3").'
        )


@app.command()
def build(
    current_time: Optional[str] = typer.Option(
        None,
        "--current-time",
        help=(
            "Override the current time for release time checks and scheduling. "
            "Accepts ISO datetime (e.g., '2024-09-15T12:00:00') or relative days "
            "(e.g., '+5' for 5 days in the future, '-3' for 3 days in the past)."
        ),
    ),
):
    """Build course materials."""
    parsed_time = None
    if current_time is not None:
        try:
            parsed_time = _parse_current_time(current_time)
            typer.echo(f"Running as if it is currently {parsed_time}")
        except ValueError as e:
            typer.echo(f"Error: {e}", err=True)
            raise typer.Exit(code=1)

    _build.build(current_time=parsed_time)


@app.command()
def status():
    """Check status of course materials."""
    print("All good.")


@app.command()
def resolve(
    path: pathlib.Path = typer.Argument(
        ...,
        help="Path to the publication.yaml file to resolve.",
    ),
):
    """Resolve a publication.yaml file and output as JSON.

    This command reads and resolves a publication.yaml file, handling variable
    interpolation from automata.yaml, and outputs the resolved publication as
    JSON to STDOUT.
    """
    # Find the automata.yaml config file by searching upwards
    config_path = find_config(path)
    if config_path is None:
        typer.echo(
            f"Error: Could not find automata.yaml in {path.parent} or any parent "
            "directory.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Read config
    try:
        config = read_config(config_path)
        vars_dict = config.vars
    except Exception as e:
        typer.echo(f"Error reading config file {config_path}: {e}", err=True)
        raise typer.Exit(code=1)

    # Resolve the publication file
    try:
        publication = read_publication_file(path, vars=vars_dict)
    except Exception as e:
        typer.echo(f"Error resolving publication file: {e}", err=True)
        raise typer.Exit(code=1)

    # Serialize to JSON and output to stdout
    try:
        json_output = serialize(publication)
        typer.echo(json_output)
    except Exception as e:
        typer.echo(f"Error serializing publication: {e}", err=True)
        raise typer.Exit(code=1)


def main():
    app()


if __name__ == "__main__":
    main()
