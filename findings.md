# Codebase Review: Code Smells, Duplications, and Architectural Issues

## 1. Critical: Assert Statements Used for Runtime Validation

Several files use `assert` for runtime type checks, which will be silently stripped in optimized Python (`python -O`):

| File | Line | Issue |
|------|------|-------|
| `_build.py` | 260 | `assert isinstance(child, (Collection, Publication, UnbuiltArtifact))` |
| `_export.py` | 170 | `assert isinstance(child, (Universe, Collection, Publication, Artifact))` |

**Recommendation**: Replace with explicit `ValueError` or `TypeError` exceptions:
```python
if not isinstance(child, (Collection, Publication, UnbuiltArtifact)):
    raise TypeError(f"Unexpected child type: {type(child).__name__}")
```

---

## 2. Code Duplication: Content Splitting Logic

The same logic for splitting content files (`.md`/`.html` → pages, others → static) appears in **three places**:

1. `extensions.py:271-279` in `Extension.from_directory()`
2. `_load.py:101-108` in `_load_site_extension()`
3. Conceptually similar in `_generate.py:340-343`

**Recommendation**: Extract to a shared utility function:
```python
def split_content_files(content: dict) -> tuple[dict, dict]:
    """Split content into pages (.md/.html) and static files."""
    pages, static = {}, {}
    for path, value in content.items():
        if path.endswith((".md", ".html")):
            pages[path] = value
        else:
            static[path] = value
    return pages, static
```

---

## 3. Naming Inconsistency: Exception Attribute Names

The two file-related exception classes use different attribute names:

| Class | Message attr | Path attr |
|-------|--------------|-----------|
| `DiscoveryError` | `msg` | `path` |
| `PageError` | `message` | `path` |

**Recommendation**: Standardize on `message` (more descriptive):
```python
class DiscoveryError(MaterialsError):
    def __init__(self, message: str, path: Path):
        self.message = message
        self.path = path
```

---

## 4. Redundant Error Message

In `_build.py:122`:
```python
raise BuildError(f"Artifact {path} does not exist at {path}.")
```

The path is mentioned twice.

**Recommendation**:
```python
raise BuildError(f"Artifact not found at {path}")
```

---

## 5. Fragile Deserialization Heuristic

`_types.py:93-122` uses key-presence heuristics to determine artifact types:

```python
if "recipe" in dct:
    type_ = UnbuiltArtifact
elif "returncode" in dct:
    type_ = BuiltArtifact
else:
    type_ = ExportedArtifact
```

This is fragile if fields are added or renamed in the future.

**Recommendation**: Add an explicit `_type` field during serialization:
```python
def serialize(node):
    dct = dataclasses.asdict(node)
    dct["_type"] = type(node).__name__  # "UnbuiltArtifact", etc.
    return json.dumps(dct, ...)
```

---

## 6. Inconsistent `Hooks | None` Pattern

All materials functions accept `hooks: Hooks | None = None` but then check `if hooks is not None:` before every hook call:

```python
if hooks is not None:
    hooks.build_on_too_soon(artifact)
```

This pattern appears 15+ times across `_build.py`, `_export.py`, and `_filter.py`.

**Recommendation**: Create a no-op `Hooks` instance as the default:
```python
_NOOP_HOOKS = Hooks()  # Empty registry, all calls are no-ops

def build(root, ..., hooks: Hooks = _NOOP_HOOKS):
    # Now can call hooks directly without None checks
    hooks.build_on_too_soon(artifact)
```

---

## 7. Duplicate Constants

`CONFIGURATION_FILENAME = "automata.yaml"` is defined in both:
- `_config.py:10`
- `_load.py:10`

**Recommendation**: Import from `_config.py` or move to `constants.py`:
```python
from .._config import CONFIGURATION_FILENAME
```

---

## 8. Missing Type Annotations

Several parameters lack type hints:

| File | Function | Parameter |
|------|----------|-----------|
| `_build.py:187-188` | `build()` | `run`, `exists` |
| `_types.py:94` | `_artifact_from_dict()` | `dct` |
| `_types.py:195` | `_replace_children()` | `new_children` |
| `_types.py:246` | `_replace_children()` | `new_children` |

**Recommendation**: Add explicit type hints:
```python
def build(..., run: Callable = subprocess.run, exists: Callable[[Path], bool] = Path.exists)
def _artifact_from_dict(dct: dict[str, Any]) -> ...
def _replace_children(self, new_children: Mapping[str, ArtifactType]) -> ...
```

---

## 9. Potential Module Naming Improvements

| Current | Suggested | Rationale |
|---------|-----------|-----------|
| `_resolution.py` in `materials/` | `_smartconfig.py` or `_schema.py` | More descriptive of actual purpose |
| `util/resolution.py` | Keep, but consider `util/config.py` | More general config utilities |
| `_read_collection_file.py` | `_collection.py` | Shorter, consistent with `_types.py` |
| `_read_publication_file.py` | `_publication.py` | Shorter, consistent pattern |

---

## 10. `WebsiteComponents` Dataclass Redundancy

`loaders.py` defines `WebsiteComponents` with `content` and `assets` fields that are immediately merged in `_load_site_extension()`. The distinction is only used briefly.

**Recommendation**: Consider whether this intermediate type adds value, or if `load_website_components_from_directory` should return a simpler structure.

---

## 11. Overly Permissive Type Bounds

In `_types.py:138-144`, the generic type bound is very complex:
```python
class Publication[
    ArtifactType: (
        UnbuiltArtifact,
        BuiltArtifact,
        ExportedArtifact,
        UnbuiltArtifact | BuiltArtifact | ExportedArtifact,
    )
]:
```

The fourth option is redundant since it's already covered by the first three.

**Recommendation**: Simplify to:
```python
class Publication[ArtifactType: UnbuiltArtifact | BuiltArtifact | ExportedArtifact]:
```

---

## 12. Magic String: `"page.html"` Template Requirement

`_generate.py:510` hardcodes the required template name:
```python
if "page.html" not in templates:
    raise ValueError('Templates must include a "page.html" template.')
```

**Recommendation**: Make this a constant:
```python
DEFAULT_TEMPLATE = "page.html"
```

---

## 13. Long Function: `_api/_build.py:build()`

At ~120 lines, the `build()` function in `_api/_build.py` handles many responsibilities:
- Config loading
- Materials discovery, building, and export
- Website content filtering
- Hook execution
- Website generation

**Recommendation**: Extract sub-functions:
```python
def _build_materials(path, config, hooks, current_time) -> Universe[ExportedArtifact]
def _prepare_website_content(extension, materials_dir_name) -> WebsiteContent
def _generate_website(content, config, extension, ...)
```

---

## 14. Inconsistent Use of `MutableMapping` vs `dict`

`_types.py` uses `typing.MutableMapping[str, ...]` for generic containers:
```python
artifacts: typing.MutableMapping[str, ArtifactType]
```

But other modules use plain `dict[str, ...]`. This inconsistency can cause confusion.

**Recommendation**: Standardize on one style (preferring `dict` for simplicity in Python 3.9+).

---

## 15. Missing `__all__` in Some Modules

Some internal modules export via `__all__` in their parent `__init__.py`, but the modules themselves don't define `__all__`:
- `hooks/_base.py` (exports are in `hooks/__init__.py`)
- Most `_*.py` files

This is fine for private modules, but consider adding for better IDE support.

---

## Summary of Priorities

| Priority | Issue | Impact |
|----------|-------|--------|
| High | Assert statements for runtime checks | Security/reliability |
| High | Fragile deserialization heuristic | Future maintainability |
| Medium | Content splitting duplication | DRY violation |
| Medium | Hooks None-check repetition | Code verbosity |
| Medium | Duplicate constants | Maintenance burden |
| Low | Naming inconsistencies | Developer experience |
| Low | Missing type annotations | Static analysis |
| Low | Long functions | Readability |

---

## Overall Assessment

The codebase is generally well-structured with good patterns:
- **Hooks system**: Excellent descriptor-based design with type safety
- **Tree transformations**: Clean immutable operations via `_children` and `_replace_children()`
- **Generic types**: Good use of generics for artifact lifecycle tracking
- **Module organization**: Clear separation with underscore-prefixed private modules

The issues identified are mostly minor and won't cause immediate problems, but addressing them would improve maintainability and type safety.
