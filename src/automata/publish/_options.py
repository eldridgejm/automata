"""Checking a publish strategy's options."""

from collections.abc import Collection, Mapping
from typing import Any

from ..exceptions import Error


def check_options(
    strategy: str, config: Mapping[str, Any], options: Collection[str]
) -> None:
    """Raise if *config* has a key that isn't one of the strategy's *options*.

    Without this, a misspelled option (e.g. ``brach`` for ``branch``) would be
    ignored, and its default used instead.
    """
    for key in config:
        if key not in options:
            raise Error(
                f'The {strategy} publish strategy has no option "{key}". Its options '
                f"are {', '.join(sorted(options))}."
            )
