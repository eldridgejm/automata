"""Default theme for automata websites."""

import importlib.resources
import json

from automata._extension import Extension
from automata.builtin.elements import listing_extension, schedule_extension
from automata.hooks import GeneratePostHookArgs, WebsiteInputs

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


def _build_extension():
    """Build the default theme Extension."""
    root = importlib.resources.files(__package__)

    templates = _collect_files(root / "templates", as_text=True)
    static_files = _collect_files(root / "static")
    schema = json.loads((root / "schema.json").read_text())

    # ext is set after _build_extension returns; the closures read it lazily.
    ext = None

    def collect(inputs: WebsiteInputs) -> WebsiteInputs:
        inputs.templates.update(templates)
        inputs.static_files.update(static_files)
        inputs.elements.update(elements)
        if ext and ext.config:
            inputs.vars["theme_config"] = ext.config
        return inputs

    def post_generate(args: GeneratePostHookArgs) -> None:
        config = ext.config if ext else {}
        _hooks_module.post_generate(args.build_directory, config)

    ext = Extension(
        name="default",
        hooks={
            "on_website_collect": collect,
            "on_generate_post": post_generate,
        },
        schema=schema,
        dependencies=[listing_extension, schedule_extension],
    )

    return ext


extension = _build_extension()
