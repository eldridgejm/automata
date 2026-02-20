# Designing an Extensions System: Resources

This document outlines the design of an extensions system for automata, enabling users to customize and extend functionality through modular resources. The system supports both filesystem-based extensions and Python package extensions.

## Resources

There are (currently) five different "resources" that can be provided:

- **Templates**: Jinja2 templates for website generation.
- **Pages**: Markdown or HTML representing website pages, which will be rendered.
- **Static files**: Any static files (e.g. CSS, JS, images) to be copied to the output directory directly.
- **Elements**: Python classes representing page elements, which can be used in templates.
- **Hooks**: Python functions that can be registered to hook points.

The first four are the "website resources", which are loaded and passed to the website generator. A **builtin** is a set of resources provided by automata itself (e.g., the default theme). An **extension** is a set of resources provided externally.

The first four resources are grouped into a `WebsiteResources`:

```python
@dataclass
class WebsiteResources:
    templates: dict[str, str] = field(default_factory=dict)
    pages: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    static_files: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type[Element]] = field(default_factory=dict)
```

A `Resources` extends `WebsiteResources` with hooks:

```python
@dataclass
class Resources(WebsiteResources):
    hooks: ThemeHooks = field(default_factory=ThemeHooks)
```

Multiple `Resources` can be composed. Templates, pages, static files, and elements merge with last-wins semantics on key conflicts. Hooks are additive — all registered hooks run, ordered by priority.

On the filesystem, pages and static files are provided together in a single `content/` directory (rather than separate `pages/` and `static/` directories). When content is loaded, the file extension determines which attribute a file is assigned to: `.md` files become pages; all other files become static files.
