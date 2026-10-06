"""Rendering a publication's resolved metadata through a template file
(``automata resolve TARGET --template FILE``), e.g. to write a LaTeX file of
a homework's due date and number for the homework to ``\\input``."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import jinja2
import smartconfig

from .exceptions import Error
from .website._render import _NamedDictLoader, _template_line


def _environment(name: str, source: str) -> jinja2.Environment:
    """An environment in which only ``${ ... }`` is special.

    Jinja's statements (``{% ... %}``) and comments (``{# ... #}``) are turned
    off, by giving them delimiters no file has, since a LaTeX file is full of
    ``{%`` and ``{#1}``. Undefined names are errors, and the template's
    trailing newline is kept.
    """
    return jinja2.Environment(
        loader=_NamedDictLoader({name: source}),
        undefined=smartconfig.StrictUndefined,
        variable_start_string="${",
        variable_end_string="}",
        block_start_string="\x00{%",
        block_end_string="%}\x00",
        comment_start_string="\x00{#",
        comment_end_string="#}\x00",
        keep_trailing_newline=True,
        autoescape=False,
    )


def render_publication_template(
    path: Path, publication: Any, variables: Mapping[str, Any]
) -> str:
    """The template at *path*, rendered with *publication* (as
    ``publication``) and *variables* (e.g. ``vars`` and ``course``).

    Raises
    ------
    automata.exceptions.Error
        If the template can't be read, has a syntax error, or uses a name or
        key that isn't defined (located as ``FILE:LINE``).

    """
    try:
        source = path.read_text()
    except OSError as e:
        raise Error(f'Cannot read the template "{path}": {e.strerror}.') from None

    name = str(path)
    try:
        template = _environment(name, source).get_template(name)
        return template.render({**variables, "publication": publication})
    except jinja2.TemplateSyntaxError as e:
        raise Error(f"{name}:{e.lineno}: {e.message}") from None
    except jinja2.UndefinedError as e:
        raise Error(f"{_where(e, name)}: {e.message}") from None
    except (TypeError, ValueError, ArithmeticError) as e:
        # e.g. format() given a string where it needs a number
        raise Error(f"{_where(e, name)}: {e}") from None


def _where(error: Exception, name: str) -> str:
    """``FILE:LINE`` of the template *name* at which *error* was raised."""
    located = _template_line(error.__traceback__, {name})
    return f"{name}:{located[1]}" if located else name
