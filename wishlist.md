# Plugin System Wishlist

Future capabilities to consider adding to the Automata plugin system.

## High Priority

### Jinja Filters and Globals

Allow plugins to extend the Jinja2 environment with custom filters and global functions.

```python
@dataclass
class Plugin:
    # ... existing fields ...
    filters: dict[str, Callable] = field(default_factory=dict)
    globals: dict[str, Any] = field(default_factory=dict)
```

**Use cases:**
- Date formatting filters
- Asset URL helpers
- Custom string manipulation
- Site-wide constants

### Hooks with Materials Access

Currently hooks only receive `WebsiteConfig`. Many plugins need access to the materials universe.

**Use cases:**
- Calendar plugin generating iCal from due dates
- Search plugin building index from all content
- Changelog plugin showing recently released materials

**Solution:** Change hook signature to include `RenderContext` or `Universe[ExportedArtifact]`.

### Markdown Extensions

Allow plugins to register markdown extensions and preprocessors.

```python
@dataclass
class Plugin:
    # ... existing fields ...
    markdown_extensions: list[Extension] = field(default_factory=list)
```

**Use cases:**
- LaTeX/math rendering (MathJax/KaTeX)
- Syntax highlighting themes
- Footnotes, tables, definition lists
- Custom fenced code block handlers

### Event Priority System

When multiple plugins define the same hook, allow priority ordering.

```python
@dataclass
class ThemeHooks:
    pre_generate: Callable[..., ...] | None = None
    pre_generate_priority: int = 100  # lower = runs first
```

**Use cases:**
- Ensuring hooks run in correct dependency order
- Allowing plugins to run "before" or "after" other plugins

## Medium Priority

### Granular Page Hooks

More fine-grained hooks for page processing (inspired by MkDocs/Jekyll):

- `on_page_markdown(page, markdown) -> markdown` - Before markdown rendering
- `on_page_content(page, html) -> html` - After markdown, before template
- `on_template_context(page, context) -> context` - Modify template context per-page
- `on_page_rendered(page, html) -> html` - After full page render

**Use cases:**
- SEO metadata injection
- Analytics snippets
- Content transformations
- Auto-linking

### Content Generators

Allow plugins to generate pages from data sources.

```python
class Generator(ABC):
    @abstractmethod
    def generate(self, context: RenderContext) -> list[GeneratedPage]: ...
```

**Use cases:**
- Generate a page per staff member from data
- Create tag/category index pages
- Build API documentation from schemas

**Note:** Content generators can be implemented via hooks for now. A `pre_generate` hook that returns extra content is functionally equivalent to a content generator. The main prerequisite is that hooks need access to richer context (materials, elements, etc.) rather than just `WebsiteConfig`. A formal `Generator` abstraction would only become necessary if we need:
- Caching/incremental builds based on input data changes
- Introspection of what generators are registered
- Different input/output contracts than hooks provide

### Materials System Hooks

Hooks for the materials pipeline (discover → build → export):

- `on_artifact_discovered(artifact)` - When artifact found in YAML
- `on_artifact_built(artifact, result)` - After recipe execution
- `on_publication_exported(publication)` - When publication copied to output

**Use cases:**
- Custom artifact validation
- Metadata enrichment
- Build notifications

## Lower Priority

### Custom File Type Handlers

Register handlers for file extensions beyond `.md` and `.html`.

```python
@dataclass
class Plugin:
    # ... existing fields ...
    converters: dict[str, Callable[[str], str]] = field(default_factory=dict)
```

**Use cases:**
- `.rst` for reStructuredText
- `.ipynb` for Jupyter notebooks
- `.adoc` for AsciiDoc

### Asset Pipeline Hooks

Standard hooks for CSS/JS processing:

- `on_asset_process(path, content) -> content`
- Built-in support for bundling, minification, fingerprinting

**Use cases:**
- CSS/JS minification
- Image optimization
- Cache busting via content hashing

### Page Variants

Support for generating multiple versions of pages (e.g., different languages).

**Use cases:**
- Multi-language course sites
- A/B testing
- Print vs. screen versions

---

## Plugin Use Case Ideas

Potential plugins that would exercise these capabilities:

| Plugin | Templates | Static | Elements | Filters | Hooks | Generators |
|--------|-----------|--------|----------|---------|-------|------------|
| Calendar Integration | | ✓ | ✓ | | ✓ | |
| Grade Calculator | | ✓ | ✓ | | | |
| Search | | ✓ | ✓ | | ✓ | |
| Progress Tracker | | ✓ | ✓ | | | |
| LaTeX/Math | | ✓ | | | | |
| Syntax Themes | | ✓ | | | | |
| Practice Problem Bank | ✓ | | ✓ | | | ✓ |
| Learning Objectives | ✓ | | ✓ | | | |
| Office Hours | | ✓ | ✓ | | | |
| Announcements | ✓ | | ✓ | | | |
| Link Checker | | | | | ✓ | |
| Accessibility Audit | | | | | ✓ | |
| Dark Mode | | ✓ | ✓ | | | |
| Video Player | | ✓ | ✓ | | | |
| Quiz/Self-Assessment | | ✓ | ✓ | | | |

---

## References

Patterns borrowed from other static site generators:

- **Sphinx**: Directives, roles, domains, document transforms
- **Jekyll**: Generators, converters, tags, filters, fine-grained hooks
- **Hugo**: Shortcodes, theme composition, asset pipeline
- **Pelican**: Signal-based architecture, Jinja filters
- **MkDocs**: Event priority system, granular page/template events
