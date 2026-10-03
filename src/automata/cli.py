import datetime
import functools
import json
import pathlib
from collections.abc import Callable
from typing import Any, Optional

import typer

from ._automata import Automata
from ._calendar import Calendar
from ._check import Problem
from ._status import ArtifactStatus, Status
from .config import CONFIGURATION_FILENAME, find_config
from .exceptions import Error
from .materials import serialize
from .util.resolution import local_time

app = typer.Typer()
pipeline = typer.Typer(
    help="Run the pipeline's stages one by one (build runs them all)."
)
app.add_typer(pipeline, name="pipeline")


def _command(*args: Any, group: typer.Typer = app, **kwargs: Any) -> Callable:
    """Like ``app.command`` (or *group*'s), but reports automata errors without
    a traceback.

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

        return group.command(*args, **kwargs)(wrapper)

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


@_command(name="clean", group=pipeline)
def clean():
    """Empty the build directory, keeping top-level dot-entries."""
    _project().clean()
    typer.echo("Build directory cleaned.")


@_command(name="build-materials", group=pipeline)
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


@_command(name="export-materials", group=pipeline)
def export_materials(
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Discover, build, and export materials to the build directory."""
    project = _project()
    discovered = project.discover()
    built = project.build_materials(
        discovered, current_time=_get_current_time(current_time), verbose=verbose
    )
    project.export_materials(built)
    typer.echo("Materials exported.")


@_command(name="render-website", group=pipeline)
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
    """An artifact's state, for people, e.g. "scheduled for 2025-02-01 00:00"."""
    if artifact.state == "released":
        return typer.style("released", fg="green")
    if artifact.state == "scheduled":
        assert artifact.release_time is not None
        return f"scheduled for {_when(artifact.release_time, now)}"
    if artifact.state == "not ready":
        return typer.style("not ready", fg="yellow")
    return typer.style("missing (no recipe, and its file doesn't exist)", fg="yellow")


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
            when = _when(artifact.release_time, now)
            typer.echo(f"  {artifact.key:<{width}}  {when}")
        if len(status.next_releases) > len(shown):
            more = len(status.next_releases) - len(shown)
            typer.echo(f"  and {more} more (see automata status --verbose)")

    if verbose and status.artifacts:
        typer.echo("All artifacts:")
        width = max(len(a.key) for a in status.artifacts)
        for artifact in status.artifacts:
            described = _describe_artifact(artifact, now)
            typer.echo(f"  {artifact.key:<{width}}  {described}")


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
):
    """Show what is released and what is scheduled to be.

    Reports what the materials say; it doesn't look at any build, and builds
    nothing.
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


# calendar =============================================================================


def _parse_date(value: str | None, option: str) -> datetime.date | None:
    if value is None:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        raise Error(
            f'Invalid {option} value: "{value}". Expected a date like 2025-01-06.'
        ) from None


@_command()
def calendar(
    collection: Optional[list[str]] = typer.Option(
        None,
        "--collection",
        "-c",
        help="Show only this collection (may be given more than once).",
    ),
    key: Optional[list[str]] = typer.Option(
        None,
        "--key",
        "-k",
        help=(
            "Show only dates under this metadata key, e.g. 'due'; a glob pattern "
            "(may be given more than once)."
        ),
    ),
    start: Optional[str] = typer.Option(
        None, "--from", help="Show only dates on or after this one (YYYY-MM-DD)."
    ),
    end: Optional[str] = typer.Option(
        None, "--to", help="Show only dates on or before this one (YYYY-MM-DD)."
    ),
    week_start: str = typer.Option(
        "sunday", "--week-start", help="The day weeks start on: sunday or monday."
    ),
    all_weeks: bool = typer.Option(
        False,
        "--all",
        help="Show every week. By default, the calendar starts with the current week.",
    ),
    highlight_today: bool = typer.Option(
        True,
        "--highlight-today/--no-highlight-today",
        help="Highlight today (the default).",
    ),
    html_path: Optional[pathlib.Path] = typer.Option(
        None, "--html", help="Write the calendar as an HTML page to this file."
    ),
    pdf_path: Optional[pathlib.Path] = typer.Option(
        None, "--pdf", help="Write the calendar as a PDF to this file."
    ),
    ics_path: Optional[pathlib.Path] = typer.Option(
        None,
        "--ics",
        help="Write the calendar as an iCalendar file, for calendar apps.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help='Print the calendar as JSON. Errors are printed as JSON: {"error": ...}.',
    ),
    current_time: Optional[str] = _current_time_option,
):
    """Show week by week the dates in the materials' metadata.

    Which dates (e.g. each homework's released and due dates) is configured in
    the calendar section of automata.yaml. Collections have their own colors.
    Prints a table, or writes the calendar as HTML or PDF. Builds nothing.
    """

    def make() -> Calendar:
        return _load_project().calendar(
            collections=collection or None,
            keys=key or None,
            start=_parse_date(start, "--from"),
            end=_parse_date(end, "--to"),
            week_start=week_start,
            all_weeks=all_weeks,
            highlight_today=highlight_today,
            current_time=_current_time_or_error(current_time),
        )

    if json_output:
        try:
            result = make()
        except Error as e:
            typer.echo(json.dumps({"error": str(e)}, indent=2))
            raise typer.Exit(code=1)
        typer.echo(json.dumps(result.to_dict(), indent=2))
        return

    result = make()
    if html_path is not None:
        html_path.write_text(result.to_html())
        typer.echo(f"Wrote {html_path}")
    if pdf_path is not None:
        pages = result.write_pdf(pdf_path)
        typer.echo(f"Wrote {pdf_path} ({_plural(pages, 'page')})")
    if ics_path is not None:
        ics_path.write_text(result.to_ics(), newline="")
        events = sum(len(d.entries) for w in result.weeks for d in w.days)
        typer.echo(f"Wrote {ics_path} ({_plural(events, 'event')})")
    if html_path is None and pdf_path is None and ics_path is None:
        if not result.weeks:
            typer.echo(
                _nothing_to_show(
                    result, collection, key, from_this_week=not all_weeks and not start
                )
            )
        else:
            from rich.console import Console

            Console().print(result.rich_table())


def _nothing_to_show(
    calendar: Calendar,
    collections: list[str] | None,
    keys: list[str] | None,
    from_this_week: bool,
) -> str:
    """Why the calendar is empty: the dates it looked for, and where."""

    def day(d: datetime.date) -> str:
        return f"{d:%a %b} {d.day}, {d.year}"

    what = f"{' or '.join(keys)} dates" if keys else "dates"
    where = f" in {' or '.join(collections)}" if collections else ""
    start, end = calendar.start, calendar.end
    if from_this_week and start is not None:
        when = f" from this week (starting {day(start)}) on"
    # (given both, the calendar shows their weeks, even if empty)
    elif start is not None:
        when = f" on or after {day(start)}"
    elif end is not None:
        when = f" on or before {day(end)}"
    else:
        when = ""
    message = f"Nothing to show: there are no {what}{where}{when}."
    if from_this_week:
        message += " Use --all to include earlier weeks."
    return message


# check ================================================================================


def _plural(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


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
