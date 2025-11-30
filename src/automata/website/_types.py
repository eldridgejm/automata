"""Shared type helpers for the website package."""

import datetime
import pathlib
from types import ModuleType
from typing import Any, Mapping, NamedTuple

import smartconfig

import automata.materials


class RenderContext(NamedTuple):
    """Context passed to page and element templates during rendering."""

    content_path: pathlib.Path
    materials_path: pathlib.Path
    output_path: pathlib.Path
    materials: automata.materials.Universe
    vars: dict[str, Any]
    element_configs: dict[str, dict[str, Any]]
    now: datetime.datetime
    theme: "Theme"


class Theme(NamedTuple):
    templates: ModuleType
    static: ModuleType
    schema: smartconfig.types.Schema

    template_overrides: Mapping[str, str] | None = None
    static_overrides: Mapping[str, str | bytes] | None = None
