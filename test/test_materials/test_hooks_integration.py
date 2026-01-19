"""Integration tests for hooks in the materials module."""

import pathlib

import automata.materials
from automata.hooks import (
    BuildOnMissingHook,
    BuildOnNotReadyHook,
    BuildOnRecipeHook,
    BuildOnStartHook,
    BuildOnSuccessHook,
    BuildOnTooSoonHook,
    DiscoverOnCollectionHook,
    DiscoverOnPublicationHook,
    DiscoverOnSkipHook,
    ExportOnCopyHook,
    ExportOnNodeHook,
    FilterOnHitHook,
    FilterOnMissHook,
    Registry,
)

# =============================================================================
# Helper Functions for Testing
# =============================================================================


def make_tracking_registry():
    """Create a registry with tracking hooks for all materials hook points."""
    hooks: Registry = {}
    calls = []

    def make_tracker(event_name):
        def tracker(*args, **kwargs):
            calls.append((event_name, args, kwargs))

        return tracker

    # Register trackers for all hook points
    DiscoverOnCollectionHook.register(hooks, priority=50)(make_tracker("on_collection"))
    DiscoverOnPublicationHook.register(hooks, priority=50)(
        make_tracker("on_publication")
    )
    DiscoverOnSkipHook.register(hooks, priority=50)(make_tracker("on_skip"))
    BuildOnStartHook.register(hooks, priority=50)(make_tracker("on_start"))
    BuildOnRecipeHook.register(hooks, priority=50)(make_tracker("on_recipe"))
    BuildOnSuccessHook.register(hooks, priority=50)(make_tracker("on_success"))
    BuildOnTooSoonHook.register(hooks, priority=50)(make_tracker("on_too_soon"))
    BuildOnNotReadyHook.register(hooks, priority=50)(make_tracker("on_not_ready"))
    BuildOnMissingHook.register(hooks, priority=50)(make_tracker("on_missing"))
    ExportOnCopyHook.register(hooks, priority=50)(make_tracker("on_copy"))
    ExportOnNodeHook.register(hooks, priority=50)(make_tracker("on_node"))
    FilterOnHitHook.register(hooks, priority=50)(make_tracker("on_hit"))
    FilterOnMissHook.register(hooks, priority=50)(make_tracker("on_miss"))

    return hooks, calls


# =============================================================================
# discover() Hook Integration Tests
# =============================================================================


class TestDiscoverWithHooks:
    """Tests for discover() with hooks parameter."""

    def test_discover_calls_on_collection_hooks(self, default_example_course):
        """Verify on_collection hooks are called for each collection."""
        hooks: Registry = {}
        calls = []

        @DiscoverOnCollectionHook.register(hooks, priority=50)
        def track_collection(path, collection):
            calls.append(("on_collection", path, collection))

        automata.materials.discover(default_example_course.path, hooks=hooks)

        # Should have been called once for the "homeworks" collection
        assert len(calls) == 1
        assert calls[0][0] == "on_collection"
        assert "homeworks" in str(calls[0][1])

    def test_discover_calls_on_publication_hooks(self, default_example_course):
        """Verify on_publication hooks are called for each publication."""
        hooks: Registry = {}
        calls = []

        @DiscoverOnPublicationHook.register(hooks, priority=50)
        def track_publication(path, publication):
            calls.append(("on_publication", path, publication))

        automata.materials.discover(default_example_course.path, hooks=hooks)

        # Should have been called for each publication
        assert len(calls) >= 1
        for call in calls:
            assert call[0] == "on_publication"

    def test_discover_calls_on_skip_hooks(self, temporary_course):
        """Verify on_skip hooks are called for skipped directories."""
        # Create a directory to skip
        skip_dir = pathlib.Path(temporary_course.path) / "_build"
        skip_dir.mkdir()

        # Create a minimal collection
        temporary_course.create_collection(
            "homeworks",
            """
            publication_schema:
                required_artifacts: []
            """,
        )

        hooks: Registry = {}
        calls = []

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def track_skip(path):
            calls.append(("on_skip", path))

        automata.materials.discover(
            temporary_course.path,
            skip_directories=["_build"],
            hooks=hooks,
        )

        # Should have been called for the skipped directory
        assert len(calls) == 1
        assert calls[0][0] == "on_skip"
        assert "_build" in str(calls[0][1])

    def test_discover_with_multiple_hooks_runs_in_priority_order(
        self, default_example_course
    ):
        """Verify hooks run in priority order."""
        call_order = []
        hooks: Registry = {}

        @DiscoverOnCollectionHook.register(hooks, priority=10)
        def first_hook(path, collection):
            call_order.append("first")

        @DiscoverOnCollectionHook.register(hooks, priority=50)
        def second_hook(path, collection):
            call_order.append("second")

        automata.materials.discover(default_example_course.path, hooks=hooks)

        assert call_order == ["first", "second"]


# =============================================================================
# build() Hook Integration Tests
# =============================================================================


class TestBuildWithHooks:
    """Tests for build() with hooks parameter."""

    def test_build_calls_on_start_hooks(self, default_example_course):
        """Verify on_start hooks are called."""
        hooks: Registry = {}
        calls = []

        @BuildOnStartHook.register(hooks, priority=50)
        def track_start(key, node):
            calls.append(("on_start", key, type(node).__name__))

        universe = automata.materials.discover(default_example_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for collections, publications
        assert len(calls) >= 1
        assert any("on_start" in call for call in calls)

    def test_build_calls_on_recipe_hooks(self, default_example_course):
        """Verify on_recipe hooks are called when recipe runs."""
        hooks: Registry = {}
        calls = []

        @BuildOnRecipeHook.register(hooks, priority=50)
        def track_recipe(artifact):
            calls.append(("on_recipe", artifact.path))

        universe = automata.materials.discover(default_example_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for artifacts with recipes
        assert len(calls) >= 1
        assert all(call[0] == "on_recipe" for call in calls)

    def test_build_calls_on_success_hooks(self, default_example_course):
        """Verify on_success hooks are called on successful build."""
        hooks: Registry = {}
        calls = []

        @BuildOnSuccessHook.register(hooks, priority=50)
        def track_success(artifact):
            calls.append(("on_success", artifact.path))

        universe = automata.materials.discover(default_example_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for successfully built artifacts
        assert len(calls) >= 1
        assert all(call[0] == "on_success" for call in calls)

    def test_build_calls_on_too_soon_hooks(self, temporary_course):
        """Verify on_too_soon hooks are called for unreleased artifacts."""
        temporary_course.create_collection(
            "homeworks",
            """
            publication_schema:
                required_artifacts:
                    - homework.pdf
            """,
        )

        temporary_course.create_publication(
            "homeworks",
            "01-intro",
            """
            metadata: {}
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                    release_time: 2099-12-31 23:59:59
            """,
        )

        hooks: Registry = {}
        calls = []

        @BuildOnTooSoonHook.register(hooks, priority=50)
        def track_too_soon(artifact):
            calls.append(("on_too_soon", artifact.path))

        universe = automata.materials.discover(temporary_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for the unreleased artifact
        assert len(calls) >= 1
        assert all(call[0] == "on_too_soon" for call in calls)

    def test_build_calls_on_not_ready_hooks(self, temporary_course):
        """Verify on_not_ready hooks are called for unready artifacts."""
        temporary_course.create_collection(
            "homeworks",
            """
            publication_schema:
                required_artifacts:
                    - homework.pdf
            """,
        )

        temporary_course.create_publication(
            "homeworks",
            "01-intro",
            """
            metadata: {}
            artifacts:
                homework.pdf:
                    recipe: touch homework.pdf
                    ready: false
            """,
        )

        hooks: Registry = {}
        calls = []

        @BuildOnNotReadyHook.register(hooks, priority=50)
        def track_not_ready(artifact):
            calls.append(("on_not_ready", artifact.path))

        universe = automata.materials.discover(temporary_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for the not-ready artifact
        assert len(calls) >= 1
        assert all(call[0] == "on_not_ready" for call in calls)


# =============================================================================
# export() Hook Integration Tests
# =============================================================================


class TestExportWithHooks:
    """Tests for export() with hooks parameter."""

    def test_export_calls_on_copy_hooks(self, default_example_course, tmp_path):
        """Verify on_copy hooks are called when copying files."""
        hooks: Registry = {}
        calls = []

        @ExportOnCopyHook.register(hooks, priority=50)
        def track_copy(src, dst):
            calls.append(("on_copy", str(src), str(dst)))

        universe = automata.materials.discover(default_example_course.path)
        built = automata.materials.build(universe)

        # Use a separate output directory to avoid source == destination
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        automata.materials.export(built, output_dir, hooks=hooks)

        # Should have been called for each copied file
        assert len(calls) >= 1
        assert all(call[0] == "on_copy" for call in calls)

    def test_export_calls_on_node_hooks(self, default_example_course, tmp_path):
        """Verify on_node hooks are called for each node."""
        hooks: Registry = {}
        calls = []

        @ExportOnNodeHook.register(hooks, priority=50)
        def track_node(key, node):
            calls.append(("on_node", key, type(node).__name__))

        universe = automata.materials.discover(default_example_course.path)
        built = automata.materials.build(universe)

        # Use a separate output directory to avoid source == destination
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        automata.materials.export(built, output_dir, hooks=hooks)

        # Should have been called for nodes
        assert len(calls) >= 1
        assert all(call[0] == "on_node" for call in calls)


# =============================================================================
# filter() Hook Integration Tests
# =============================================================================


class TestFilterWithHooks:
    """Tests for filter() with hooks parameter."""

    def test_filter_calls_on_hit_hooks(self, default_example_course):
        """Verify on_hit hooks are called for matching nodes."""
        hooks: Registry = {}
        calls = []

        @FilterOnHitHook.register(hooks, priority=50)
        def track_hit(key, node):
            calls.append(("on_hit", key, type(node).__name__))

        universe = automata.materials.discover(default_example_course.path)

        # Filter that matches everything
        automata.materials.filter(
            universe,
            predicate=lambda key, node: True,
            hooks=hooks,
        )

        # Should have been called for matching nodes
        assert len(calls) >= 1
        assert all(call[0] == "on_hit" for call in calls)

    def test_filter_calls_on_miss_hooks(self, default_example_course):
        """Verify on_miss hooks are called for non-matching nodes."""
        hooks: Registry = {}
        calls = []

        @FilterOnMissHook.register(hooks, priority=50)
        def track_miss(key, node):
            calls.append(("on_miss", key, type(node).__name__))

        universe = automata.materials.discover(default_example_course.path)

        # Filter that matches nothing
        automata.materials.filter(
            universe,
            predicate=lambda key, node: False,
            hooks=hooks,
        )

        # Should have been called for non-matching nodes
        assert len(calls) >= 1
        assert all(call[0] == "on_miss" for call in calls)
