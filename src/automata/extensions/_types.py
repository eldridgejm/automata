"""The Extension type and entry point group names."""

from __future__ import annotations

import dataclasses
import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import smartconfig.types

# entry point groups: themes are set with website.theme, extensions are listed
# under extensions:
THEMES_GROUP = "automata.themes"
EXTENSIONS_GROUP = "automata.extensions"


@dataclasses.dataclass
class Extension:
    """A collection of hooks that customize automata's behavior.

    An extension is the fundamental unit of customization in automata. It maps
    hook point names to callables that are registered when the extension is
    applied. For example, a theme extension registers a hook on
    ``on_render_collect`` to provide templates, static files, and elements.

    Extensions can declare *dependencies* — other extensions that are
    automatically applied first.

    Attributes
    ----------
    name : str
        A human-readable name for the extension.
    hooks : dict[str, Callable]
        A mapping of hook point names to callables. Each key must correspond
        to a hook defined on :class:`automata.hooks.Hooks`.
    config : dict[str, Any]
        Optional configuration for the extension.
    schema : smartconfig.types.Schema | None
        Optional schema for validating *config*.
    dependencies : list[Extension]
        Extensions that must be applied before this one.
    commands : dict[str, Any]
        Commands the extension adds to the CLI, by name: ``automata NAME``.
        Each is a function, whose parameters are the command's options and
        arguments (as with Typer), except that a parameter named ``project``
        is given the :class:`~automata.Automata` project; its docstring is the
        command's help. Or each is a :class:`ScriptCommand`. Or each is a
        group of commands (``automata NAME SUBNAME``): a dict of them, in the
        same form, with the group's help under ``"__doc__"``.

    """

    name: str
    hooks: dict[str, Callable]
    config: dict[str, Any] = dataclasses.field(default_factory=dict)
    schema: smartconfig.types.Schema | None = None
    dependencies: list[Extension] = dataclasses.field(default_factory=list)
    commands: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass
class ScriptCommand:
    """A command that runs a shell command, with the command line's arguments
    appended to it (quoted), as a directory extension's ``commands/`` files do.

    Attributes
    ----------
    command : str
        The shell command.
    help : str | None
        The command's help.
    cwd : Path | None
        The directory to run it in (by default, the current one).
    env : dict[str, str] | None
        Its environment (by default, the current one).

    """

    command: str
    help: str | None = None
    cwd: Path | None = None
    env: dict[str, str] | None = None

    def __call__(self, args: list[str]) -> int:
        """Run the command with *args*; returns its exit status."""
        line = " ".join([self.command, *(shlex.quote(arg) for arg in args)])
        return subprocess.run(line, shell=True, cwd=self.cwd, env=self.env).returncode
