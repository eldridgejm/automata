# Automata Architecture Plan

## Module Structure

```
automata/
├── lib/              # Public - core primitives
├── _website/         # Private - website generation
├── _calendar/        # Private - calendar generation
├── _deploy/          # Private - deployment
├── api/              # Public - high-level programmatic interface
└── cli/              # Public - command line interface
```

## Module Descriptions

### `automata.lib` (public)

Low-level building blocks for course material management. Already implemented.

- **Types**: `Universe`, `Collection`, `Publication`, `PublicationSchema`, `UnbuiltArtifact`, `BuiltArtifact`, `ExportedArtifact`
- **Functions**: `discover()`, `build()`, `filter()`, `export()`, `serialize()`, `deserialize()`
- **Callbacks**: `DiscoverCallbacks`, `BuildCallbacks`, `FilterCallbacks`, `ExportCallbacks`

### `automata._website` (private)

Generates a static course website. Depends on types from `lib`.

- Takes a `Universe` and configuration as input
- Produces HTML pages with course information
- Incorporates exported materials into the site

### `automata._calendar` (private)

Generates calendars showing course material release dates. Independent of `_website`.

- Takes a `Universe` as input
- Outputs in multiple formats:
  - PDF
  - HTML
  - Terminal display

### `automata._deploy` (private)

Handles deployment of the generated website (which includes exported materials).

- Pushes website directory to a server

### `automata.api` (public)

High-level programmatic interface for use in Python scripts.

- Provides convenience functions that orchestrate `lib` and private modules
- Example functions: `publish()`, `generate_website()`, `deploy()`

### `automata.cli` (public)

Command line interface.

- Thin wrapper that parses arguments and calls `api` functions
- Subcommands for materials, website, calendar, deployment

## Data Flow

```
lib.discover() → Universe[UnbuiltArtifact]
       ↓
lib.build() → Universe[BuiltArtifact]
       ↓
lib.export() → materials in output directory
       ↓
_website → generates HTML site around materials
       ↓
_deploy → pushes to server

_calendar → independent path: Universe metadata → PDF/HTML/terminal
```

## Design Decisions

1. **Underscore prefix for private modules**: `_website`, `_calendar`, `_deploy` signal internal implementation details not intended for external use.

2. **`lib` remains public**: Provides low-level API for users who need fine-grained control.

3. **`api` as high-level public interface**: Convenience layer for common workflows.

4. **`cli` separate from `api`**: CLI is a thin wrapper; business logic lives in `api`.

5. **`_calendar` independent of `_website`**: Calendar generation is a separate concern, not a website component.

## Eventual CLI

```
automata deploy
    Builds and deploys website, e.g., on GitHub pages

automata calendar
    Makes an HTML calendar showing the course schedule based on when publications are released. Intended to give an overview of the course.

automata status
    An overview of which materials are next to be published.

automata build
    Builds the website locally.

automata export
    Exports all course materials to another directory without building the website.

automata resolve
    Lists all of the publications and their resolved metadata in a JSON output.

automata unready
    Unreadies publications. Interactive by default, but supports an —all argument.

automata ready
    Same as above, but inverted.

automata init
    Creates a basic automata course from a template.

```
