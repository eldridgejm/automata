"""Shared type helpers for the website package (private)."""

from __future__ import annotations

import datetime
import pathlib
from typing import Any, NamedTuple

import automata.materials


class RenderContext(NamedTuple):
    """Context passed to page and element templates during rendering."""

    input_path: pathlib.Path
    output_path: pathlib.Path
    theme_path: pathlib.Path
    materials_path: pathlib.Path | None
    materials: automata.materials.Universe | None
    config: dict[str, Any]
    vars: dict[str, Any]
    now: datetime.datetime
