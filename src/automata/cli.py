import datetime
import functools
import json
import pathlib
from collections.abc import Callable
from typing import Any, Optional

import typer

from ._automata import Automata
from ._check import Problem
from ._status import ArtifactStatus, Status
from .config import CONFIGURATION_FILENAME, find_config
from .exceptions import Error
from .materials import serialize
from .util.resolution import local_time

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
        return local_time(datetime.datetime.fromisoformat(value))
    except ValueError:
        raise ValueError(
            f'Invalid --current-time value: "{value}". '
            f'Expected ISO datetime (e.g., "2024-09-15T12:00:00") '
            f'or relative days (e.g., "+5" or "-3").'
        )


def _current_time_or_error(current_time: str | None) -> datetime.datetime | None:
    """Parse the --current-time option, raising Error if it's invalid.

    Says which time is used, on stderr (so that it doesn't mix with output such
    as JSON).
    """
    if current_time is None:
        return None
    try:
        parsed = _parse_current_time(current_time)
    except ValueError as e:
        raise Error(str(e)) from None
    typer.echo(f"Running as if it is currently {parsed}", err=True)
    return parsed


def _get_current_time(current_time: str | None) -> datetime.datetime | None:
    """Parse the --current-time option, exiting on error."""
    try:
        return _current_time_or_error(current_time)
    except Error as e:
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


_verbose_option = typer.Option(
    False,
    "--verbose",
    "-v",
    help=(
        "Show each recipe's output as it runs. By default it is captured, and "
        "the end of it is shown only if the recipe fails."
    ),
)


def _find_project_root() -> pathlib.Path | None:
    """The nearest directory, at or above the cwd, containing automata.yaml."""
    config_path = find_config(pathlib.Path.cwd())
    return None if config_path is None else config_path.parent


def _load_project() -> Automata:
    """Load the project enclosing the current directory, raising Error if it can't.

    Searches upward from the current directory for automata.yaml, and says
    (on stderr) which project is used when it is not the current directory.
    """
    root = _find_project_root()
    if root is None:
        raise Error(
            f"No {CONFIGURATION_FILENAME} found in {pathlib.Path.cwd()} or any "
            f"parent directory."
        )

    if root != pathlib.Path.cwd():
        typer.echo(f"Using project at {root}", err=True)

    return Automata(root)


def _project() -> Automata:
    """Load the project enclosing the current directory, exiting on error."""
    try:
        return _load_project()
    except Error as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@_command()
def build(
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Run the full pipeline and produce the site in the build directory."""
    _project().build(current_time=_get_current_time(current_time), verbose=verbose)


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
    verbose: bool = _verbose_option,
):
    """Run the full pipeline and deploy the built site."""
    project = _project()
    published = project.publish(
        target=target, current_time=_get_current_time(current_time), verbose=verbose
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
def build_materials(
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Discover and build materials (run recipes, check release times)."""
    project = _project()
    discovered = project.discover()
    project.build_materials(
        discovered, current_time=_get_current_time(current_time), verbose=verbose
    )
    typer.echo("Materials built.")


@_command()
def export(
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Discover, build, and export materials to the build directory."""
    project = _project()
    discovered = project.discover()
    built = project.build_materials(
        discovered, current_time=_get_current_time(current_time), verbose=verbose
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


# status ===============================================================================


def _relative(when: datetime.datetime, now: datetime.datetime) -> str:
    """*when* relative to *now*, e.g. "in 3 days" or "2 hours ago"."""
    seconds = (when - now).total_seconds()
    amount = abs(seconds)
    for unit, size in [("day", 86400), ("hour", 3600), ("minute", 60)]:
        if amount >= size:
            n = int(amount // size)
            text = f"{n} {unit}{'s' if n != 1 else ''}"
            break
    else:
        text = "less than a minute"
    return f"in {text}" if seconds >= 0 else f"{text} ago"


def _when(when: datetime.datetime, now: datetime.datetime) -> str:
    return f"{when:%Y-%m-%d %H:%M} ({_relative(when, now)})"


def _describe_artifact(artifact: ArtifactStatus, now: datetime.datetime) -> str:
    """An artifact's state, for people, e.g. "released, not on the site"."""
    if artifact.state == "released":
        site = "on the site" if artifact.on_site else "not on the site"
        return typer.style(
            f"released, {site}", fg="yellow" if artifact.out_of_date else "green"
        )
    if artifact.state == "scheduled":
        assert artifact.release_time is not None
        text = f"scheduled for {_when(artifact.release_time, now)}"
    elif artifact.state == "not ready":
        text = "not ready"
    else:
        text = "missing (no recipe, and its file doesn't exist)"
    if artifact.on_site:
        return typer.style(f"{text}, but on the site", fg="yellow")
    return text


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _print_status(status: Status, verbose: bool) -> None:
    now = status.current_time
    counts = ", ".join(f"{n} {state}" for state, n in status.counts.items())
    typer.echo(f"Artifacts: {counts or 'none'}")

    if status.next_releases:
        typer.echo("Next releases:")
        shown = status.next_releases[:5]
        width = max(len(a.key) for a in shown)
        for artifact in shown:
            assert artifact.release_time is not None
            typer.echo(
                f"  {artifact.key:<{width}}  {_when(artifact.release_time, now)}"
            )
        if len(status.next_releases) > len(shown):
            more = len(status.next_releases) - len(shown)
            typer.echo(f"  and {more} more (see automata status --verbose)")

    built = "never" if status.last_built is None else _when(status.last_built, now)
    out_of_date = status.out_of_date
    if not out_of_date:
        typer.echo(f"Last build: {built}. " + typer.style("Up to date.", fg="green"))
    else:
        is_are = "is" if len(out_of_date) == 1 else "are"
        typer.echo(
            f"Last build: {built}. "
            + typer.style(
                f"{_plural(len(out_of_date), 'artifact')} {is_are} out of date: run "
                f"automata build.",
                fg="yellow",
            )
        )
        if not verbose:
            for artifact in out_of_date[:5]:
                typer.echo(f"  {artifact.key}: {_describe_artifact(artifact, now)}")
            if len(out_of_date) > 5:
                typer.echo(f"  and {len(out_of_date) - 5} more")

    if verbose and status.artifacts:
        typer.echo("All artifacts:")
        width = max(len(a.key) for a in status.artifacts)
        for artifact in status.artifacts:
            typer.echo(
                f"  {artifact.key:<{width}}  {_describe_artifact(artifact, now)}"
            )


@_command()
def status(
    current_time: Optional[str] = _current_time_option,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="List every artifact and its state."
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=(
            "Print the full status as JSON, for programs. Errors are printed as "
            'JSON too: {"error": "..."}.'
        ),
    ),
    exit_code: bool = typer.Option(
        False,
        "--exit-code",
        help="Exit with status 2 if the site is out of date (errors exit with 1).",
    ),
):
    """Show what is released and scheduled, and whether the site is up to date.

    Builds nothing: reads the materials and the last build's materials.json.
    """
    if json_output:
        try:
            result = _load_project().status(
                current_time=_current_time_or_error(current_time)
            )
        except Error as e:
            typer.echo(json.dumps({"error": str(e)}, indent=2))
            raise typer.Exit(code=1)
        typer.echo(json.dumps(result.to_dict(), indent=2))
    else:
        result = _project().status(current_time=_get_current_time(current_time))
        _print_status(result, verbose)

    if exit_code and result.out_of_date:
        raise typer.Exit(code=2)


# check ================================================================================


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line for line in text.splitlines())


@app.command()
def check(
    current_time: Optional[str] = _current_time_option,
    json_output: bool = typer.Option(
        False, "--json", help='Print the problems as JSON: {"problems": [...]}.'
    ),
):
    """Check the project for problems, without building anything.

    Reports every problem found (in the configuration, materials, pages,
    templates, element configuration, and publish targets), and exits with
    status 1 if there are any.
    """
    try:
        project = _load_project()
        problems = project.check(current_time=_current_time_or_error(current_time))
    except Error as e:
        problems = [Problem("configuration", str(e))]

    if json_output:
        typer.echo(json.dumps({"problems": [p.to_dict() for p in problems]}, indent=2))
    elif not problems:
        typer.echo(typer.style("No problems found.", fg="green"))
    else:
        for area in dict.fromkeys(p.area for p in problems):
            typer.echo(typer.style(f"{area}:", bold=True))
            for problem in problems:
                if problem.area == area:
                    typer.echo(_indent(problem.message, "  "))
        typer.echo(typer.style(f"{_plural(len(problems), 'problem')} found.", fg="red"))

    if problems:
        raise typer.Exit(code=1)


def main():
    app()


if __name__ == "__main__":
    main()
