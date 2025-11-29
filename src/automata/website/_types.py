"""Shared type helpers for the website package."""

import datetime
import pathlib
from typing import Any, NamedTuple

import smartconfig

import automata.materials


class RenderContext(NamedTuple):
    """Context passed to page and element templates during rendering."""

    content_path: pathlib.Path
    materials_path: pathlib.Path
    output_path: pathlib.Path
    materials: automata.materials.Universe
    vars: dict[str, Any]
    now: datetime.datetime


class Theme(NamedTuple):
    templates: pathlib.Path | list[pathlib.Path]
    static: pathlib.Path | list[pathlib.Path]
    schema: smartconfig.types.Schema
