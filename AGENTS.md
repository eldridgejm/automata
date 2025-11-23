# automata

## Project Overview

**Automata** is a Python tool for automating the publication of course materials (homeworks, lectures, labs) with time-based release scheduling. It provides a pipeline for discovering, building, filtering, and exporting course content, as well as a static course website generator.

### Current Development Status

This repository uses **git worktrees**:
- **`dev` branch** (current directory): Active development - a modernized rewrite with improved typing and architecture. **Partially complete** - library layer is functional but CLI is not yet implemented.
- **`main` branch** (in `_old/` directory): Legacy stable version with complete CLI and coursepage generation features.

## Repository Structure

### New Architecture (`dev` branch)

```
src/automata/
├── __init__.py
├── constants.py              # Configuration constants
└── materials/                # Core materials processing module
    ├── __init__.py           # Public API exports
    ├── _types.py             # Type definitions and hierarchy (~440 lines)
    ├── _discover.py          # Filesystem discovery logic (~380 lines)
    ├── _build.py             # Artifact building logic (~300 lines)
    ├── _export.py            # Artifact export/publication (~190 lines)
    ├── _filter.py            # Filtering/selection logic (~155 lines)
    ├── _read_collection_file.py   # YAML parsing for collections
    ├── _read_publication_file.py  # YAML parsing for publications
    └── exceptions.py         # Custom exceptions

test/                         # Comprehensive pytest test suite
doc/                          # Sphinx documentation
pyproject.toml                # Project metadata and dependencies
flake.nix                     # Nix development environment
```

### Legacy Architecture (`_old/` directory)

```
_old/automata/
├── __init__.py               # Entry point (imports cli)
├── cli.py                    # Command-line interface
├── util.py                   # Utilities
├── lib/materials/            # Core business logic (private)
│   ├── types.py              # Data structures
│   ├── _discover.py          # Discovery logic (MOST COMPLEX ~580 lines)
│   ├── _build.py             # Build execution
│   ├── _publish.py           # File copying
│   └── ...
└── api/                      # High-level public API
    ├── materials/            # Materials publishing API
    └── coursepage/           # Course website generation
```

## Core Concepts

### Data Model

The system uses a hierarchical tree structure with generic types to track artifact state:

```
Universe[ArtifactType]
└── collections: Dict[str, Collection[ArtifactType]]
    └── publications: Dict[str, Publication[ArtifactType]]
        ├── metadata: Dict[str, Any]
        └── artifacts: Dict[str, ArtifactType]
```

### Artifact Lifecycle

Artifacts progress through three states:
1. **UnbuiltArtifact**: Discovered from YAML, contains recipe and release_time
2. **BuiltArtifact**: After recipe execution, contains returncode/stdout/stderr
3. **ExportedArtifact**: After copying to output directory

### Pipeline Stages

```
discover() → build() → filter() → export()
```

1. **Discover**: Scan filesystem for `collection.yaml` and `publication.yaml` files
2. **Build**: Execute shell recipes to generate artifacts (respects release_time)
3. **Filter**: Apply predicates to select specific materials
4. **Export**: Copy built artifacts to output directory

## Configuration Files

### collection.yaml

Defines a collection of related publications:

```yaml
publication_schema:
  required_artifacts:
    - homework.pdf
  optional_artifacts:
    - solution.pdf
  metadata_schema:
    name:
      type: string
    due:
      type: datetime
  is_ordered: true
  allow_unspecified_artifacts: false
```

### publication.yaml

Defines a single publication (assignment, lecture, etc.):

```yaml
metadata:
  name: Homework 01
  due: 2024-09-20 23:59:00

artifacts:
  homework.pdf:
    path: ./build/homework.pdf
    recipe: make homework
    release_time: 2024-09-15
    ready: true
    missing_ok: false
```

## Development Guidelines

### Code Style

- **Python 3.8+** with modern type hints (Union syntax `|` used in dev branch)
- **Dataclasses** for mutable artifact types
- **NamedTuples** for immutable container types (Publication, Collection, Universe)
- **Functional style**: Pure functions, immutable data structures, recursive tree traversal
- **Private module convention**: Underscore prefix for implementation files (`_discover.py`)
- Use `pathlib.Path` for all path handling

### Design Patterns

1. **Callback Pattern**: All operations accept optional Callback classes for extensibility
   ```python
   class BuildCallbacks:
       def on_build(self, key, node): ...
       def on_recipe(self, artifact): ...
       def on_success(self, artifact, built): ...
   ```

2. **Tree Transformation Pattern**:
   - `_children` property exposes child nodes
   - `_replace_children()` creates new node with modified children
   - Operations return new trees, preserving originals

3. **Function Overloads**: Use `@overload` decorator for type-safe recursive functions

### Key Dependencies

- **pyyaml**: YAML parsing
- **jinja2**: Template processing
- **dictconfig**: Schema validation and variable interpolation (custom library)
- **cerberus**: Metadata schema validation style

### Testing

Run tests with pytest:
```bash
pytest test/
```

Tests use:
- `CourseBuilder` fixture for creating test course structures
- Example courses in `test/` directories
- Comprehensive coverage of discovery, build, export, and filtering

### Building and Environment

Using Nix (preferred):
```bash
nix develop
```

Or with pip:
```bash
pip install -e .
```

## Important Notes for Agents

### When Working on dev Branch

1. **No CLI exists yet** - The dev branch is library-only. CLI needs to be ported from `_old/automata/cli.py`.

2. **Reference the old code** - When implementing missing features, consult `_old/` for the original implementation.

3. **Preserve the callback pattern** - All new operations should support callbacks for extensibility.

4. **Maintain type safety** - Use proper type hints and function overloads for recursive tree operations.

5. **Follow the export pattern** - Public API is exported through `__init__.py`, implementation stays in underscore-prefixed files.

### When Comparing Old vs New

| Feature | Old (`_old/`) | New (`dev`) |
|---------|---------------|-------------|
| CLI | Complete | Not implemented |
| Coursepage generation | Complete | Not implemented |
| Type hints | Partial | Comprehensive |
| Callback pattern | Basic | Refined |
| Tree operations | Works | More elegant |
| `publish()` | Named `_publish.py` | Named `_export.py` |

### Common Tasks

**Porting from old to new**:
1. Read the old implementation in `_old/automata/lib/materials/`
2. Adapt to new type system in `_types.py`
3. Use the refined callback pattern
4. Add comprehensive type hints

**Adding tests**:
1. Create test file in `test/test_materials/`
2. Use `CourseBuilder` fixture from `conftest.py`
3. Test both success and error paths

## API Reference (dev branch)

### Main Functions

```python
from automata.materials import discover, build, export, filter

# Discover materials from filesystem
universe: Universe[UnbuiltArtifact] = discover(
    root_directory=Path("course"),
    skip_directories=["_build"],
    callbacks=DiscoverCallbacks(),
    vars={"course_name": "CS101"}
)

# Build artifacts (execute recipes)
built: Universe[BuiltArtifact] = build(
    root=universe,
    ignore_release_time=False,
    ignore_ready=False,
    verbose=True,
    callbacks=BuildCallbacks()
)

# Filter to specific artifacts
filtered = filter(
    root=built,
    predicate=lambda node: True,
    remove_empty_nodes=True
)

# Export to output directory
exported: Universe[ExportedArtifact] = export(
    root=filtered,
    outdir=Path("output"),
    prefix=Path(""),
    callbacks=ExportCallbacks()
)
```

### Serialization

```python
from automata.materials import serialize, deserialize

# Convert to JSON string
json_str: str = serialize(universe)

# Reconstruct from JSON
restored: Universe = deserialize(json_str)
```

## Contact and Resources

- Documentation: `doc/` directory (Sphinx)
- Tests: `test/` directory
- Legacy reference: `_old/` directory
