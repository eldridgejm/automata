import contextlib
import datetime
import functools
import inspect
import json
import pathlib
import re
import sys
import time
from collections.abc import Callable, Iterator
from typing import Any, Optional

import typer
from rich.markup import escape

from ._automata import Automata
from ._calendar import Calendar
from ._check import Problem
from ._init import create_project
from ._status import Status
from .config import CONFIGURATION_FILENAME, find_config
from .exceptions import Error
from .extensions import ScriptCommand
from .extensions._apply import all_extensions
from .materials import serialize
from .util.resolution import local_time

# without a command, each prints its help
app = typer.Typer(no_args_is_help=True)
pipeline = typer.Typer(
    no_args_is_help=True,
    help="Run the pipeline's stages one by one (build runs them all).",
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
                _error(str(e))
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
    _say(f"[yellow]Running as if it is currently[/] [bold]{parsed}[/]", err=True)
    return parsed


def _get_current_time(current_time: str | None) -> datetime.datetime | None:
    """Parse the --current-time option, exiting on error."""
    try:
        return _current_time_or_error(current_time)
    except Error as e:
        _error(str(e))
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


# the project main() loaded (to find its extensions' commands), which the
# commands reuse rather than loading it again
_startup_project: Automata | None = None


def _load_project() -> Automata:
    """Load the project enclosing the current directory, raising Error if it can't.

    Searches upward from the current directory for automata.yaml (unless
    main() already loaded the project), and says (on stderr) which project is
    used when it is not the current directory.
    """
    if _startup_project is not None:
        if _startup_project.path != pathlib.Path.cwd():
            typer.echo(f"Using project at {_startup_project.path}", err=True)
        return _startup_project

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
        _error(str(e))
        raise typer.Exit(code=1)


def _error(message: str) -> None:
    """Print an error *message* on stderr, after a red "Error:"."""
    _say(f"[bold red]Error:[/] {escape(message)}", err=True)


def _say(markup: str, err: bool = False) -> None:
    """Print *markup* (rich's), styled on a terminal, and plain otherwise."""
    from rich.console import Console

    Console(stderr=err, highlight=False).print(markup, soft_wrap=True)


def _relative_path(path: pathlib.Path) -> str:
    """*path*, relative to the current directory if it is inside it."""
    path = path.resolve()
    try:
        return str(path.relative_to(pathlib.Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _counted(n: int, noun: str) -> str:
    """*n* (in bold) *noun*, pluralized: as markup."""
    return f"[bold]{n}[/] {noun}" + ("" if n == 1 else "s")


class _BuildProgress:
    """Reports a build's progress, as its hooks fire: what was discovered,
    each recipe as it runs, what was built (and skipped), and when the site is
    done.

    Lines are printed (as rich markup) with *echo*. If given, *status* shows
    what is happening now: a transient line on the terminal (with a spinner),
    cleared with None. If *verbose*, each recipe is named with *echo* instead,
    before its output.
    """

    def __init__(
        self,
        project: Automata,
        echo: Callable[[str], None] = _say,
        status: Callable[[str | None], None] | None = None,
        verbose: bool = False,
        current_time: datetime.datetime | None = None,
    ):
        self.echo, self.status, self.verbose = echo, status, verbose
        # the time the build is for (to say how far off releases are)
        self.now = current_time or datetime.datetime.now()
        self.build_directory = project.config.website.build_directory
        self.start = time.monotonic()
        self.collections = self.publications = 0
        self.built = self.by_recipe = 0
        self.skipped = {"not released yet": 0, "not ready": 0, "missing": 0}
        self.recipe: str | None = None
        self._reported: set[str] = set()

        hooks = project.hooks
        hooks.on_discover_collection.register()(lambda args: self._count("collections"))
        hooks.on_discover_publication.register()(
            lambda args: self._count("publications")
        )
        hooks.on_build_materials_node.register()(lambda args: self._discovered())
        hooks.on_build_artifact_recipe.register()(self._recipe)
        hooks.on_build_artifact_success.register()(lambda args: self._built())
        for hook, reason in [
            (hooks.on_build_artifact_too_soon, "not released yet"),
            (hooks.on_build_artifact_not_ready, "not ready"),
            (hooks.on_build_artifact_missing, "missing"),
        ]:
            hook.register()(self._skipper(reason))
        hooks.on_export_node.register()(lambda args: self._exporting())
        hooks.on_render_pre.register()(lambda args: self._rendering())
        hooks.on_render_post.register()(lambda args: self._done())
        self._show("Discovering materials…")

    def _show(self, markup: str | None) -> None:
        if self.status is not None:
            self.status(markup)

    def _count(self, name: str) -> None:
        setattr(self, name, getattr(self, name) + 1)

    def _skipper(self, reason: str) -> Callable[[Any], None]:
        """Counts an artifact skipped for *reason* (and, if verbose, says
        which)."""

        def skip(args: Any) -> None:
            self.skipped[reason] += 1
            why = reason
            if reason == "not released yet" and args.release_time:
                release = local_time(datetime.datetime.fromisoformat(args.release_time))
                relative = _relative(release, self.now)
                why += f" (releases {release:%a %Y-%m-%d %H:%M}, {relative})"
            if self.verbose:
                self._discovered()
                path = escape(_relative_path(args.workdir / args.path))
                self.echo(f"[bold yellow]○[/] Skipped [cyan]{path}[/]: [dim]{why}[/]")

        return skip

    def _once(self, what: str) -> bool:
        """Whether *what* hasn't been reported yet (and now is)."""
        if what in self._reported:
            return False
        self._reported.add(what)
        return True

    def _discovered(self) -> None:
        if self._once("discovered"):
            self.echo(
                f"[bold cyan]→[/] Discovered {_counted(self.collections, 'collection')}"
                f", {_counted(self.publications, 'publication')}."
            )
            self._show("Building materials…")

    def _recipe(self, args: Any) -> None:
        self._discovered()
        self.by_recipe += 1
        self.recipe = escape(_relative_path(args.workdir / args.path))
        if self.verbose:
            # the recipe, the directory it runs in, and its command, before
            # its output
            self.echo(f"[bold blue]▶[/] Running the recipe for [cyan]{self.recipe}[/]")
            workdir = escape(_relative_path(args.workdir))
            self.echo(f"  [dim]in working directory: {workdir}[/]")
            self.echo(f"  [dim]$ {escape(args.recipe)}[/]")
        self._building()

    def _built(self) -> None:
        self.built += 1
        self._building()

    def _building(self) -> None:
        running = ""
        if self.recipe is not None:
            running = f" · running the recipe for [cyan]{self.recipe}[/]"
        self._show(f"Building materials… [dim]{self.built} built[/]{running}")

    def _materials(self) -> None:
        self._discovered()
        if not self._once("materials"):
            return
        recipes = ""
        if self.by_recipe:
            noun = "its recipe" if self.by_recipe == 1 else "their recipes"
            recipes = f" [dim]({self.by_recipe} by {noun})[/]"
        self.echo(
            f"[bold green]✓[/] Built {_counted(self.built, 'artifact')}{recipes}."
        )
        skipped = {reason: n for reason, n in self.skipped.items() if n}
        if skipped:
            reasons = ", ".join(f"{n} {reason}" for reason, n in skipped.items())
            total = _counted(sum(skipped.values()), "artifact")
            self.echo(f"[bold yellow]○[/] Skipped {total}: [dim]{reasons}[/].")

    def _exporting(self) -> None:
        self._materials()
        if self._once("exporting"):
            self._show("Exporting materials…")

    def _rendering(self) -> None:
        self._materials()
        self._show("Rendering the website…")

    def _done(self) -> None:
        self._materials()
        self._show(None)
        seconds = time.monotonic() - self.start
        self.echo(
            f"[bold green]✓[/] Built the site in "
            f"[bold cyan]{escape(self.build_directory)}[/] [dim]({seconds:.1f} s)[/]."
        )


class _TerminalStatus:
    """A transient status line on the terminal, with a spinner: shown (or
    changed) with a message (rich markup), and cleared with None. Lines must
    be printed with :meth:`print` while it shows, so that they go above it,
    rather than over it."""

    def __init__(self, console: Any = None) -> None:
        from rich.console import Console

        self._console = console or Console(highlight=False)
        self._status: Any = None

    def print(self, markup: str) -> None:
        self._console.print(markup, soft_wrap=True)

    def __call__(self, message: str | None) -> None:
        from rich.text import Text

        if message is None:
            if self._status is not None:
                self._status.stop()
                self._status = None
            return
        # one line, however narrow the terminal (the spinner takes two columns)
        text = Text.from_markup(message)
        text.truncate(self._console.width - 2, overflow="ellipsis")
        if self._status is None:
            self._status = self._console.status(
                text, spinner="dots", spinner_style="bold green"
            )
            self._status.start()
        else:
            self._status.update(text)


@contextlib.contextmanager
def _build_progress(
    project: Automata,
    verbose: bool,
    current_time: datetime.datetime | None,
    err: bool = False,
) -> Iterator["_BuildProgress"]:
    """Report the progress of the build within: with a spinner showing what is
    happening now, on a terminal (unless *verbose*, as recipes' output then
    goes to it). If *err*, on stderr, so that stdout has only the command's
    output (e.g. JSON)."""
    stream = sys.stderr if err else sys.stdout
    if stream.isatty() and not verbose:
        from rich.console import Console

        status = _TerminalStatus(Console(stderr=err, highlight=False))
        # (through the spinner's console, so that the lines go above it)
        progress = _BuildProgress(
            project, echo=status.print, status=status, current_time=current_time
        )
    else:
        status = None
        progress = _BuildProgress(
            project,
            echo=lambda markup: _say(markup, err=err),
            verbose=verbose,
            current_time=current_time,
        )
    try:
        yield progress
    finally:
        if status is not None:
            status(None)


@_command()
def init():
    """Create a new project in the current directory: an automata.yaml and a
    website directory. Existing files are left as they are."""
    created = create_project(pathlib.Path.cwd())
    for path in created:
        _say(f"[green]Created[/] {escape(_relative_path(path))}")
    _say(
        f"\nNext, fill in the course's details in {CONFIGURATION_FILENAME}, and "
        "run [bold]automata serve[/] to see the website."
    )


@_command()
def build(
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Run the full pipeline and produce the site in the build directory."""
    project = _project()
    now = _get_current_time(current_time)
    with _build_progress(project, verbose, now):
        project.build(current_time=now, verbose=verbose)


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
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Build, then say which files publishing would add, modify, or delete, "
            "without publishing."
        ),
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help=(
            "With --dry-run, print the changes as JSON (the build's progress goes "
            'to stderr). Errors are printed as JSON: {"error": ...}.'
        ),
    ),
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Run the full pipeline and deploy the built site."""
    if json_output and not dry_run:
        _error("--json is only for --dry-run.")
        raise typer.Exit(code=1)
    project = _project()
    now = _get_current_time(current_time)
    if dry_run:
        _dry_run(project, target, now, verbose, json_output)
        return
    with _build_progress(project, verbose, now):
        published = project.publish(target=target, current_time=now, verbose=verbose)

    for name in published:
        _say(f"[bold green]✓[/] Published to [bold]{escape(name)}[/].")


# the letters for changes, as in git status --short
_CHANGE_LETTERS = {"added": "A", "modified": "M", "deleted": "D"}


def _dry_run(
    project: Automata,
    target: str | None,
    now: datetime.datetime | None,
    verbose: bool,
    json_output: bool,
) -> None:
    """Print what publishing to *target* (or every target) would change."""
    try:
        with _build_progress(project, verbose, now, err=json_output):
            changes = project.publish_dry_run(
                target=target, current_time=now, verbose=verbose
            )
    except Error as e:
        if not json_output:
            raise
        typer.echo(json.dumps({"error": str(e)}, indent=2))
        raise typer.Exit(code=1)

    strategies = {name: project.config.publish[name]["strategy"] for name in changes}
    if json_output:
        result = {
            name: {
                "strategy": strategies[name],
                "changes": [change.to_dict() for change in target_changes],
            }
            for name, target_changes in changes.items()
        }
        typer.echo(json.dumps({"targets": result}, indent=2))
        return
    for name, target_changes in changes.items():
        where = f"Publishing to {name} ({strategies[name]}) would change"
        if not target_changes:
            typer.echo(f"{where} nothing.")
            continue
        typer.echo(f"{where} {_plural(len(target_changes), 'file')}:")
        for change in target_changes:
            typer.echo(f"  {_CHANGE_LETTERS[change.status]} {change.path}")


@_command()
def serve(
    port: int = typer.Option(8000, "--port", "-p", help="The port to serve on."),
    open_browser: bool = typer.Option(
        True, "--open/--no-open", help="Open the site in a browser (the default)."
    ),
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Build and serve the site locally, rebuilding it when files change."""
    _project().serve(
        port=port,
        current_time=_get_current_time(current_time),
        verbose=verbose,
        echo=typer.echo,
        open_browser=open_browser,
    )


@_command()
def archive(
    path: Optional[pathlib.Path] = typer.Argument(
        None,
        help=(
            "The zip file to write. By default, one named after the course "
            "(e.g. dsc-40b-fall-2026-materials.zip) in the project directory."
        ),
    ),
    all_artifacts: bool = typer.Option(
        False,
        "--all",
        help="Include the artifacts that are not released yet, or not ready.",
    ),
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Build the materials, and zip them up. The website is untouched."""
    project = _project()
    now = _get_current_time(current_time)
    with _build_progress(project, verbose, now) as progress:
        written = project.archive(
            path,
            all_artifacts=all_artifacts,
            current_time=now,
            verbose=verbose,
        )
    size = written.stat().st_size
    _say(
        f"[bold green]✓[/] Archived {_counted(progress.built, 'artifact')} to "
        f"[bold cyan]{escape(_relative_path(written))}[/] [dim]({_size(size)})[/]."
    )


def _size(n: float) -> str:
    """*n* bytes, for people: e.g. "1.2 MB"."""
    for unit in ["bytes", "KB", "MB"]:
        if n < 1000:
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} GB"


@_command(name="clean", group=pipeline)
def clean():
    """Empty the build directory, keeping top-level dot-entries."""
    _project().clean()
    _say("[bold green]✓[/] Build directory cleaned.")


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
    _say("[bold green]✓[/] Materials built.")


@_command(name="export-materials", group=pipeline)
def export_materials(
    all_artifacts: bool = typer.Option(
        False,
        "--all",
        help="Include the artifacts that are not released yet, or not ready.",
    ),
    to: Optional[pathlib.Path] = typer.Option(
        None,
        "--to",
        help=(
            "Export to this directory, rather than to the build directory "
            "(where render-website finds them)."
        ),
    ),
    current_time: Optional[str] = _current_time_option,
    verbose: bool = _verbose_option,
):
    """Discover, build, and export materials to the build directory."""
    project = _project()
    discovered = project.discover()
    built = project.build_materials(
        discovered,
        current_time=_get_current_time(current_time),
        verbose=verbose,
        ignore_release_time=all_artifacts,
        ignore_ready=all_artifacts,
    )
    project.export_materials(built, to=to)
    where = f" to [bold cyan]{escape(str(to))}[/]" if to is not None else ""
    _say(f"[bold green]✓[/] Materials exported{where}.")


@_command(name="render-website", group=pipeline)
def render_website(current_time: Optional[str] = _current_time_option):
    """Render the website from previously exported materials."""
    project = _project()
    materials = project.load_exported_materials()
    project.render_website(materials, current_time=_get_current_time(current_time))
    _say("[bold green]✓[/] Website rendered.")


def _target_key(target: str, root: pathlib.Path) -> str:
    """*target*'s key: itself (e.g. ``homeworks/hw01``), or, if it is an
    existing path, the path of its directory, relative to the project."""
    path = pathlib.Path(target)
    if not path.exists():
        return target.strip("/")
    path = path.resolve()
    if path.is_file():
        path = path.parent
    try:
        return path.relative_to(root.resolve()).as_posix()
    except ValueError:
        raise Error(f'"{target}" is not inside the project ({root}).') from None


def _find_target(universe: Any, key: str) -> Any:
    """The collection or publication with *key* in *universe*."""
    collections = universe.collections
    if key in collections and key != "default":
        return collections[key]
    for collection_key, collection in collections.items():
        if collection_key == "default":
            # publications outside any collection: keyed by their paths
            if key in collection.publications:
                return collection.publications[key]
        elif key.startswith(collection_key + "/"):
            publication_key = key[len(collection_key) + 1 :]
            if publication_key in collection.publications:
                return collection.publications[publication_key]
    raise Error(f'Nothing discovered is named "{key}".')


@_command()
def resolve(
    target: Optional[str] = typer.Argument(
        None,
        help=(
            "Print only this collection or publication: its key (e.g. "
            "homeworks/hw01), or the path of its directory or YAML file."
        ),
    ),
):
    """Print the materials, resolved, with their metadata, as JSON.

    Builds nothing.
    """
    project = _project()
    resolved = project.discover()
    if target is not None:
        resolved = _find_target(resolved, _target_key(target, project.path))
    typer.echo(serialize(resolved))


# status ===============================================================================


def _relative(when: datetime.datetime, now: datetime.datetime) -> str:
    """*when* relative to *now*, e.g. "in 3 days" or "2 hours ago"."""
    seconds = (when - now).total_seconds()
    amount = abs(seconds)
    # weeks only from two weeks on: "in 10 days" is clearer than "in a week"
    units = [("week", 7 * 86400, 14 * 86400), ("day", 86400, 86400)]
    units += [("hour", 3600, 3600), ("minute", 60, 60)]
    for unit, size, least in units:
        if amount >= least:
            n = int(amount // size)
            if n == 1:
                text = f"{'an' if unit == 'hour' else 'a'} {unit}"
            else:
                text = f"{n} {unit}s"
            break
    else:
        text = "less than a minute"
    return f"in {text}" if seconds >= 0 else f"{text} ago"


# each state's symbol and color
_STATE_STYLES = {
    "released": ("●", "green"),
    "scheduled": ("◷", "cyan"),
    "not ready": ("○", "yellow"),
    "missing": ("✗", "red"),
}


def _state(state: str) -> str:
    """*state*, after its symbol, in its color: as markup."""
    symbol, color = _STATE_STYLES[state]
    return f"[{color}]{symbol} {state}[/]"


def _key(key: str) -> str:
    """An artifact's key, with its collection and publication dimmed: as
    markup."""
    *parents, name = key.split("/")
    prefix = "".join(f"{escape(part)}/" for part in parents)
    return f"[dim]{prefix}[/]{escape(name)}"


def _release(when: datetime.datetime, now: datetime.datetime) -> tuple[str, str]:
    """A release time, and how far off it is (in bold yellow, within a week):
    as markup."""
    soon = datetime.timedelta(0) <= when - now <= datetime.timedelta(days=7)
    relative = _relative(when, now)
    return f"{when:%a %Y-%m-%d %H:%M}", (
        f"[bold yellow]{relative}[/]" if soon else f"[dim]{relative}[/]"
    )


def _artifacts_table() -> Any:
    from rich.table import Table

    table = Table(box=None, show_header=False, pad_edge=False, padding=(0, 0, 0, 3))
    # each artifact on one line: on a narrow terminal, cut short
    for _ in range(4):
        table.add_column(no_wrap=True, overflow="ellipsis")
    return table


def _print_status(status: Status, verbose: bool, console: Any = None) -> None:
    """Print *status* for people: styled, on a terminal."""
    from rich.console import Console
    from rich.padding import Padding

    if console is None:
        console = Console(highlight=False)
        if not console.is_terminal:
            # piped: never wrapped
            console.width = 1000
    now = status.current_time

    counts = "  ".join(
        f"[{color}]{symbol}[/] [bold]{n}[/] {state}"
        for state, n in status.counts.items()
        if n
        for symbol, color in [_STATE_STYLES[state]]
    )
    console.print(f"[bold]Artifacts[/]  {counts or '[dim]none[/]'}", soft_wrap=True)

    if status.next_releases:
        console.print("\n[bold]Next releases[/]")
        shown = status.next_releases[:5]
        table = _artifacts_table()
        for artifact in shown:
            assert artifact.release_time is not None
            table.add_row(_key(artifact.key), *_release(artifact.release_time, now))
        console.print(Padding(table, (0, 0, 0, 2), expand=False))
        if len(status.next_releases) > len(shown):
            more = len(status.next_releases) - len(shown)
            console.print(
                f"  [dim]and {more} more (see [bold]automata status --verbose[/])[/]"
            )

    if verbose and status.artifacts:
        console.print("\n[bold]All artifacts[/]")
        table = _artifacts_table()
        collection = None
        for artifact in status.artifacts:
            if collection is not None and artifact.key.split("/")[0] != collection:
                table.add_row()  # a blank line between collections
            collection = artifact.key.split("/")[0]
            cells = [_key(artifact.key), _state(artifact.state)]
            if artifact.state == "scheduled":
                assert artifact.release_time is not None
                cells += _release(artifact.release_time, now)
                if not artifact.ready:
                    cells[-1] += " [dim]· also marked ready: false[/]"
            elif artifact.state == "not ready":
                cells.append("[dim]marked ready: false[/]")
            elif artifact.state == "missing":
                cells.append("[dim]no recipe, and its file doesn't exist[/]")
            table.add_row(*cells)
        console.print(Padding(table, (0, 0, 0, 2), expand=False))


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
    categories: Optional[list[str]] = typer.Argument(
        None,
        help=(
            "Show only these categories: collections and event groups from the "
            "calendar configuration. By default, all are shown."
        ),
        show_default=False,
    ),
    key: Optional[list[str]] = typer.Option(
        None,
        "--key",
        "-k",
        help=(
            "Show only dates under this metadata key, e.g. 'due', and no events; a "
            "glob pattern (may be given more than once)."
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
    """Show week by week the dates in the materials' metadata, and events.

    Which dates (e.g. each homework's released and due dates, and events like
    exams and holidays) is configured in the calendar section of automata.yaml.
    Each category (a collection or event group) has its own color.
    Prints a table, or writes the calendar as HTML or PDF. Builds nothing.
    """

    def make() -> Calendar:
        return _load_project().calendar(
            categories=categories or None,
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
                    result, categories, key, from_this_week=not all_weeks and not start
                )
            )
        else:
            from rich.console import Console

            Console().print(result.rich_table())


def _nothing_to_show(
    calendar: Calendar,
    categories: list[str] | None,
    keys: list[str] | None,
    from_this_week: bool,
) -> str:
    """Why the calendar is empty: the dates it looked for, and where."""

    def day(d: datetime.date) -> str:
        return f"{d:%a %b} {d.day}, {d.year}"

    what = f"{' or '.join(keys)} dates" if keys else "dates"
    where = f" in {' or '.join(categories)}" if categories else ""
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


# commands from extensions ============================================================

_EXTENSIONS_PANEL = "Extensions"


def _builtin_command_names() -> set[str]:
    names = {
        command.name or command.callback.__name__.replace("_", "-")
        for command in app.registered_commands
        if command.callback is not None
    }
    return names | {group.name for group in app.registered_groups if group.name}


def _check_command_names(extension: str, path: list[str], command: Any) -> None:
    """Check the name at the end of *path* (a command's, or a group's), and
    those of the group's commands, if *command* is a group."""
    name = " ".join(path)
    if not re.fullmatch(r"[a-z][a-z0-9-]*", path[-1]):
        raise Error(
            f'Extension "{extension}" adds a command named "{name}": command '
            f"names must be lowercase letters, digits and hyphens, starting with "
            f"a letter."
        )
    if isinstance(command, dict):
        subcommands = {key: value for key, value in command.items() if key != "__doc__"}
        if not subcommands:
            raise Error(
                f'Extension "{extension}" adds an empty command group "{name}".'
            )
        for subname, subcommand in subcommands.items():
            _check_command_names(extension, [*path, subname], subcommand)


def _extension_commands(project: Automata) -> dict[str, tuple[str, Any]]:
    """The commands (and groups of them) the project's extensions add, by
    name, with the name of the extension adding each."""
    builtins = _builtin_command_names()
    commands: dict[str, tuple[str, Any]] = {}
    extensions = all_extensions([project.theme, *project.extensions])
    for extension in extensions.values():
        for name, command in extension.commands.items():
            _check_command_names(extension.name, [name], command)
            if name in builtins:
                raise Error(
                    f'Extension "{extension.name}" adds a command named "{name}", '
                    f"but automata has a command of that name. Rename it."
                )
            if name in commands:
                raise Error(
                    f'Extensions "{commands[name][0]}" and "{extension.name}" both '
                    f'add a command named "{name}". Rename one.'
                )
            commands[name] = (extension.name, command)
    return commands


def _add_extension_command(
    target: typer.Typer,
    name: str,
    extension: str,
    command: Any,
    project: Automata,
    panel: str | None = _EXTENSIONS_PANEL,
) -> None:
    """Add an extension's command to *target*: a function, a script, or a
    group of commands (a dict of them, with its help under "__doc__")."""
    if isinstance(command, dict):
        group = typer.Typer(
            no_args_is_help=True,
            help=command.get("__doc__") or f'Commands from extension "{extension}".',
        )
        for subname, subcommand in command.items():
            if subname != "__doc__":
                _add_extension_command(
                    group, subname, extension, subcommand, project, panel=None
                )
        target.add_typer(group, name=name, rich_help_panel=panel)
        return

    if isinstance(command, ScriptCommand):
        # the command line's arguments (and options, and --help) all go to it
        def run_script(ctx: typer.Context) -> None:
            raise typer.Exit(command(ctx.args))

        target.command(
            name,
            help=command.help or f'Run extension "{extension}"\'s {name} command.',
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
            add_help_option=False,
            rich_help_panel=panel,
        )(run_script)
        return

    # a parameter named "project" is given the project, rather than being an
    # option
    signature = inspect.signature(command)
    takes_project = "project" in signature.parameters

    @functools.wraps(command)
    def run(*args: Any, **kwargs: Any) -> Any:
        if takes_project:
            kwargs["project"] = project
        try:
            return command(*args, **kwargs)
        except Error as e:
            _error(str(e))
            raise typer.Exit(code=1)

    if takes_project:
        run.__signature__ = signature.replace(  # type: ignore[attr-defined]
            parameters=[p for p in signature.parameters.values() if p.name != "project"]
        )
        run.__annotations__ = {
            key: value
            for key, value in getattr(command, "__annotations__", {}).items()
            if key != "project"
        }
    target.command(name, rich_help_panel=panel)(run)


def app_for_directory(directory: pathlib.Path) -> tuple[typer.Typer, Error | None]:
    """The CLI for the project at or above *directory*: automata's commands,
    and its extensions' commands. If the project or its extensions' commands
    can't be loaded, only automata's commands, and the problem."""
    full, _, problem = _load_app(directory)
    return full, problem


def _load_app(
    directory: pathlib.Path,
) -> tuple[typer.Typer, Automata | None, Error | None]:
    """As :func:`app_for_directory`, and also the project, if it loaded."""
    full = typer.Typer(no_args_is_help=True)
    full.registered_commands = list(app.registered_commands)
    full.registered_groups = list(app.registered_groups)
    config_path = find_config(directory)
    if config_path is None:
        problem = Error(
            f"No {CONFIGURATION_FILENAME} found in {directory} or any parent directory."
        )
        return full, None, problem
    try:
        project = Automata(config_path.parent)
    except Error as e:
        return full, None, e
    try:
        commands = _extension_commands(project)
    except Error as e:
        return full, project, e
    for name, (extension, command) in commands.items():
        _add_extension_command(full, name, extension, command, project)
    return full, project, None


def requested_command(argv: list[str]) -> str | None:
    """The command named on the command line *argv*: its first argument that
    isn't an option."""
    return next((arg for arg in argv if not arg.startswith("-")), None)


def main(argv: list[str] | None = None, cwd: pathlib.Path | None = None):
    global _startup_project
    argv = sys.argv[1:] if argv is None else argv
    full, project, problem = _load_app(cwd or pathlib.Path.cwd())
    command = requested_command(argv)
    if (
        problem is not None
        and command is not None
        and command not in _builtin_command_names()
    ):
        # it may be an extension's command, which couldn't be loaded
        _error(str(problem))
        raise SystemExit(1)
    _startup_project = project
    try:
        full(argv)
    finally:
        _startup_project = None


if __name__ == "__main__":
    main()
