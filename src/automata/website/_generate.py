"""Generates a course website.

Inputs and Outputs
==================

Input
-----

The website generator takes two main inputs:

1.  **Content Directory**: A directory containing a hierarchy of markdown files, HTML,
and other static assets. Markdown files will be converted to HTML, while HTML and binary
files will be copied as-is to the output.

2.  **Materials Directory**: The directory of course materials previously exported by
`automata.materials.export()`. This directory is expected to contain a `materials.json`
file at its root and will be copied to the output directory (if not already present).

Website Structure
-----------------

The generator processes the input to produce a static website. For example, suppose the
materials directory contains lecture notes and homework assignments, and the content
directory contains:

```
content/
    index.md
    syllabus.md
    data/
        reviews.csv
```

The generated website will be structured similarly, with markdown files converted to
HTML, and materials and static assets from the theme integrated:

```
materials/
    materials.json
    lectures/
        ...
    homeworks/
        ...
static/
    style.css
index.html
syllabus.html
data/
    reviews.csv
```

"""

import datetime
import pathlib
from typing import Any

from ._render import RenderContext, render_page_from_markdown


def _render_content_into_website(
    content_path: pathlib.Path,
    website_path: pathlib.Path,
    context: RenderContext,
):
    """Renders content from the content directory into the website output directory.

    Markdown files are converted to HTML, while other files are copied as-is. Files are
    processed recursively to preserve directory structure.

    """

    for path in content_path.rglob("*"):
        relative_path = path.relative_to(content_path)
        output_path = website_path / relative_path

        if path.is_dir():
            output_path.mkdir(parents=True, exist_ok=True)

        elif path.suffix.lower() == ".md":
            markdown_contents = path.read_text()
            html_contents = render_page_from_markdown(markdown_contents, context)
            output_path.with_suffix(".html").write_text(html_contents)
        else:
            # copy other files as-is
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(path.read_bytes())


def generate(
    content_path: pathlib.Path,
    website_path: pathlib.Path,
    vars: dict[str, Any] | None = None,
    now: datetime.datetime | None = None,
):
    """Generates a static website from course materials."""

    # set default values for optional parameters
    if vars is None:
        vars = {}

    if now is None:
        now = datetime.datetime.now()

    context = RenderContext(now=now, vars=vars)

    _render_content_into_website(content_path, website_path, context)
