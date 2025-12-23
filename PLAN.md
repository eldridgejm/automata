# Plan

In this branch, we will implement the website feature "from scratch". We have already developed a proof of concept in the "proof_of_concept" branch, which demonstrated the core functionality.

- [x] Website abstraction (structure of the input and output)
- [x] The RenderContext abstraction
- [x] Low-level single page renderers (for use with, e.g., the practice problem generator)
- [x] Config type
- [x] generate() signature
- [x] Simple website generation (markdown to HTML)
- [x] Convert HTML files as well?
  - maybe they have frontmatter
  - maybe they have a special extension, like `.html.unrendered`?
- [x] Searching for materials in the content directory
- [ ] Allow overriding markdown renderer
- [ ] Page frontmatter
- [ ] Base path handling
- [ ] The "theme" abstraction
- [ ] Theme plugins as entry points
- [ ] Theme overrides (templates and static files)
- [ ] The "element" abstraction
- [ ] Default configuration of elements
- [ ] Website generation plugins

## Website abstraction

### Input

The input to the website generator will two directories.

The first is a directory of _content_; this is a hierarchy of markdown files,
HTML, and binary files. The markdown content will be converted to HTML, while
the HTML and binary files will be copied as-is to the output.

The second directory is the directory of course _materials_ as exported by
`automata.materials.export()`. There should be a `materials.json` at the root
of this directory. This directory will also be copied to the output directory
(unless it is already there).

### Output

Suppose the content directory has the following structure:

```
content/
    index.md
    syllabus.md
    data/
        reviews.csv
```

Then generating the website will produce an output directory with the following
structure:

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

### Low-level single page renderers

To generate an entire website, we will need to generate individual pages, and
so we will implement low-level single page generators first. It will be useful
to make these available as public functions, so that other tools can use them
to add pages to the website that will have the same look-and-feel as the rest
of the website. An important example is the practice problem generator; this
will run after we generate the website, and will need to add pages to the output
directory.

There is probably a need for multiple low-level single page generators: one for
markdown and one for HTML. The HTML generator is necessary because tools like
the practice problem generator will generate HTML directly.

The generators should take the input, resolve any template variables, render as
HTML (if necessary), and place the output HTML in the appropriate template.
Then, the result should be returned as a string.

```python

def render_page_from_markdown(
    markdown_content: str,
    render_context: RenderContext,
) -> str:
    """Render a single markdown page to HTML.

    Parameters
    ----------
    markdown_content : str
        The content of the markdown page to render.
    render_context : RenderContext
        The rendering context containing information about the website, theme,
        and other relevant data.

    """
    ...


def render_page_from_html(
    html_content: str,
    render_context: RenderContext,
) -> str:
    """Render a single HTML page.

    Parameters
    ----------
    html_content : str
        The content of the HTML page to render. Should be only the body content,
        without the <html>, <head>, or <body> tags.
    render_context : RenderContext
        The rendering context containing information about the website, theme,
        and other relevant data.

    """
    ...


def generate(
    site_config: Optional[Dict[str, Any]] = None,
    vars: Optional[Dict[str, Any]] = None,
    now: Optional[datetime.datetime] = None,
) -> None:
    """Generate a complete website from the given content and materials.

    """
    ...

# ----

config = automata.load_config("./automata.yaml")

context = RenderContext.from_site_config(site_config, vars, now=None)

render_page_from_markdown(
    "# Hello, world!",
    context
)


render_from_markdown = lambda md: render_page_from_markdown(md, context, renderer=markdown.markdown)




```
