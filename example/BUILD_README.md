# Example Course Build Scripts

This directory contains example build scripts that demonstrate how to use Automata to discover, build, and export course materials.

## Available Scripts

### `build_simple.py` - Materials Pipeline (Recommended)

A simple, focused script that demonstrates the core automata materials workflow:

```bash
python build_simple.py
```

**What it does:**
1. **Discovers** all materials (homeworks, lectures) from the file system
2. **Builds** all artifacts by executing their recipes
3. **Exports** materials to `website/materials/` directory
4. **Serializes** materials to `materials.json` for website use

**Output:**
- `website/materials/materials.json` - Serialized materials metadata
- `website/materials/homeworks/` - Built homework artifacts
- `website/materials/lectures/` - Built lecture artifacts

This script successfully completes the entire materials pipeline and is the recommended way to build course materials.

### `build.py` - Full Build with Website Generation

A more complete script that attempts to build both materials and the website:

```bash
python build.py
```

**What it does:**
1. All the steps from `build_simple.py`
2. **Generates** the static website using `automata.website.generate()`

**Status:**
The materials pipeline (steps 1-3) works perfectly. Website generation currently fails because the example templates (`syllabus.md`, `index.md`) require additional configuration variables that aren't yet fully integrated with the Config system.

**Known Issue:**
The templates expect variables like `vars.course_name` to be available at the top level of the render context, but the current implementation makes them available under `config.vars`. This requires either:
- Updating the templates to use `config.vars.course_name`
- Extending the RenderContext to support custom top-level variables

## Course Structure

The example course demonstrates a typical structure:

```
example/
├── automata.yaml          # Course configuration
├── homeworks/             # Homework collection
│   ├── collection.yaml    # Collection schema
│   ├── hw01/              # Individual homework
│   │   └── publication.yaml
│   └── ...
├── lectures/              # Lecture collection
│   ├── collection.yaml
│   ├── lec01/
│   │   └── publication.yaml
│   └── ...
└── website/               # Website content
    ├── pages/             # Markdown pages
    └── materials/         # Built materials (generated)
```

## Materials Pipeline

The automata materials pipeline follows these stages:

1. **Discover**: Scan filesystem for `collection.yaml` and `publication.yaml` files
2. **Build**: Execute artifact recipes to generate files
3. **Export**: Copy built artifacts to output directory with metadata
4. **Serialize**: Convert to JSON for website consumption

## Example Usage

```python
import pathlib
import automata.materials

# Discover materials
universe = automata.materials.discover(
    root_directory=pathlib.Path("."),
    skip_directories=["_build", "website", ".git"],
)

# Build artifacts
built = automata.materials.build(
    universe,
    ignore_release_time=True,
    ignore_ready=True,
)

# Export to website
exported = automata.materials.export(
    built,
    outdir=pathlib.Path("website/materials"),
)

# Serialize to JSON
materials_json = automata.materials.serialize(exported)
pathlib.Path("website/materials/materials.json").write_text(materials_json)
```

## Next Steps

- Run `build_simple.py` to build all course materials
- Inspect generated files in `website/materials/`
- Review `materials.json` to see the serialized metadata structure
- Examine individual artifacts in collection subdirectories
