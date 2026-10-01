"""Default theme for automata websites."""

import importlib.resources
import json

from automata.builtin.elements import listing_extension, schedule_extension
from automata.extensions import Extension
from automata.hooks import RenderPostHookArgs, WebsiteInputs

from . import hooks as _hooks_module
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


def make_extension(config: dict) -> Extension:
    """Build the default theme Extension for the given (validated) config."""

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(_templates)
        inputs.static_files.update(_static_files)
        inputs.elements.update(elements)
        return inputs

    def post_render(args: RenderPostHookArgs) -> None:
        _hooks_module.post_render(args.build_directory, config)

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
