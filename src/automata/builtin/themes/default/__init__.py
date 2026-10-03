"""Default theme for automata websites."""

import importlib.resources
import json
import pathlib
import subprocess
from collections.abc import Callable
from typing import Any

from automata.builtin.elements import listing_extension, schedule_extension
from automata.extensions import Extension
from automata.hooks import RenderPostHookArgs, WebsiteInputs

from . import _tailwind
from .elements import elements


def _collect_files(directory, as_text=False):
    """Walk a Traversable directory and return a {relative_path: content} dict."""
    result = {}

    def _walk(node, parts=()):
        for entry in node.iterdir():
            entry_parts = parts + (entry.name,)
            if any(p.startswith(".") for p in entry_parts):
                continue
            if entry.is_dir():
                _walk(entry, entry_parts)
            else:
                key = "/".join(entry_parts)
                result[key] = entry.read_text() if as_text else entry

    _walk(directory)
    return result


_root = importlib.resources.files(__package__)
_templates = _collect_files(_root / "templates", as_text=True)
_static_files = _collect_files(_root / "static")

schema = json.loads((_root / "schema.json").read_text())


def make_extension(
    config: dict,
    *,
    run: Callable[..., Any] = subprocess.run,
    cache_directory: pathlib.Path = _tailwind.CACHE_DIRECTORY,
) -> Extension:
    """Build the default theme Extension for the given (validated) config.

    automata calls this with *config* only. *run* runs npm and the Tailwind CLI
    after rendering (default :func:`subprocess.run`), and *cache_directory* is
    where Tailwind is installed; tests pass a fake and a temporary directory.
    """

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(_templates)
        inputs.static_files.update(_static_files)
        inputs.elements.update(elements)
        return inputs

    def post_render(args: RenderPostHookArgs) -> None:
        _tailwind.rebuild_css(
            args.build_directory, config, run=run, cache_directory=cache_directory
        )

    return Extension(
        name="default",
        hooks={
            "on_render_collect": collect,
            "on_render_post": post_render,
        },
        config=config,
        schema=schema,
        dependencies=[listing_extension, schedule_extension],
    )
