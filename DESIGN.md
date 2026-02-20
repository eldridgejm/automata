# Designing an Extensions System: Resources

This document outlines the design of an extensions system for automata, enabling users to customize and extend functionality through modular resources. The system supports both filesystem-based extensions and Python package extensions.

## Resources

There are (currently) four different "resources" that can be provided:

- **Templates**: Jinja2 templates for website generation.
- **Content**: Files that will appear in the output. Markdown (`.md`) files are rendered as pages; everything else (CSS, JS, images, etc.) is copied to the output directory as-is.
- **Elements**: Python classes representing page elements, which can be used in templates.
- **Hooks**: Python functions that can be registered to hook points.

The first three are the "website resources", which are loaded and passed to the website generator. A **builtin** is a set of resources provided by automata itself (e.g., the default theme). An **extension** is a set of resources provided externally.

The first three resources are grouped into a `WebsiteResources`:

```python
@dataclass
class WebsiteResources:
    templates: dict[str, str] = field(default_factory=dict)
    content: dict[str, str | bytes | Traversable] = field(default_factory=dict)
    elements: dict[str, type[Element]] = field(default_factory=dict)
```

A `Resources` extends `WebsiteResources` with hooks:

```python
@dataclass
class Resources(WebsiteResources):
    hooks: ThemeHooks = field(default_factory=ThemeHooks)
```

Multiple `Resources` can be composed. Templates, content, and elements merge with last-wins semantics on key conflicts. Hooks are additive — all registered hooks run, ordered by priority.

When content is loaded, the file extension determines handling: `.md` files are treated as pages and rendered through the template engine; all other files are copied directly to the output as static files. This eliminates the need for separate `pages/` and `static/` directories in an extension — a single `content/` directory suffices.
