"""Integration tests for hooks in the materials module."""

import pathlib
from dataclasses import dataclass
from unittest.mock import Mock

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
    Hooks,
)

# =============================================================================
# Helper Classes for Testing
# =============================================================================


@dataclass
class TrackingDiscoverOnCollectionHook(DiscoverOnCollectionHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, path, collection):
        self.calls.append(("on_collection", path, collection))


@dataclass
class TrackingDiscoverOnPublicationHook(DiscoverOnPublicationHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, path, publication):
        self.calls.append(("on_publication", path, publication))


@dataclass
class TrackingDiscoverOnSkipHook(DiscoverOnSkipHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, path):
        self.calls.append(("on_skip", path))


@dataclass
class TrackingBuildOnStartHook(BuildOnStartHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, key, node):
        self.calls.append(("on_start", key, type(node).__name__))


@dataclass
class TrackingBuildOnRecipeHook(BuildOnRecipeHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, artifact):
        self.calls.append(("on_recipe", artifact.path))


@dataclass
class TrackingBuildOnSuccessHook(BuildOnSuccessHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, artifact):
        self.calls.append(("on_success", artifact.path))


@dataclass
class TrackingBuildOnTooSoonHook(BuildOnTooSoonHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, artifact):
        self.calls.append(("on_too_soon", artifact.path))


@dataclass
class TrackingBuildOnNotReadyHook(BuildOnNotReadyHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, artifact):
        self.calls.append(("on_not_ready", artifact.path))


@dataclass
class TrackingBuildOnMissingHook(BuildOnMissingHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, artifact):
        self.calls.append(("on_missing", artifact.path))


@dataclass
class TrackingExportOnCopyHook(ExportOnCopyHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, src, dst):
        self.calls.append(("on_copy", str(src), str(dst)))


@dataclass
class TrackingExportOnNodeHook(ExportOnNodeHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, key, node):
        self.calls.append(("on_node", key, type(node).__name__))


@dataclass
class TrackingFilterOnHitHook(FilterOnHitHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, key, node):
        self.calls.append(("on_hit", key, type(node).__name__))


@dataclass
class TrackingFilterOnMissHook(FilterOnMissHook):
    """Hook that tracks calls."""

    priority: int = 50
    calls: list = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.calls is None:
            self.calls = []

    def __call__(self, key, node):
        self.calls.append(("on_miss", key, type(node).__name__))


# =============================================================================
# discover() Hook Integration Tests
# =============================================================================


class TestDiscoverWithHooks:
    """Tests for discover() with hooks parameter."""

    def test_discover_calls_on_collection_hooks(self, default_example_course):
        """Verify on_collection hooks are called for each collection."""
        hook = TrackingDiscoverOnCollectionHook()
        hooks: Hooks = {"materials.discover:on_collection": [hook]}

        automata.materials.discover(default_example_course.path, hooks=hooks)

        # Should have been called once for the "homeworks" collection
        assert len(hook.calls) == 1
        assert hook.calls[0][0] == "on_collection"
        assert "homeworks" in str(hook.calls[0][1])

    def test_discover_calls_on_publication_hooks(self, default_example_course):
        """Verify on_publication hooks are called for each publication."""
        hook = TrackingDiscoverOnPublicationHook()
        hooks: Hooks = {"materials.discover:on_publication": [hook]}

        automata.materials.discover(default_example_course.path, hooks=hooks)

        # Should have been called for each publication
        assert len(hook.calls) >= 1
        for call in hook.calls:
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

        hook = TrackingDiscoverOnSkipHook()
        hooks: Hooks = {"materials.discover:on_skip": [hook]}

        automata.materials.discover(
            temporary_course.path,
            skip_directories=["_build"],
            hooks=hooks,
        )

        # Should have been called for the skipped directory
        assert len(hook.calls) == 1
        assert hook.calls[0][0] == "on_skip"
        assert "_build" in str(hook.calls[0][1])

    def test_discover_with_multiple_hooks_runs_in_priority_order(
        self, default_example_course
    ):
        """Verify hooks run in priority order."""
        call_order = []

        @dataclass
        class FirstHook(DiscoverOnCollectionHook):
            priority: int = 10

            def __call__(self, path, collection):
                call_order.append("first")

        @dataclass
        class SecondHook(DiscoverOnCollectionHook):
            priority: int = 50

            def __call__(self, path, collection):
                call_order.append("second")

        hooks: Hooks = {"materials.discover:on_collection": [SecondHook(), FirstHook()]}

        automata.materials.discover(default_example_course.path, hooks=hooks)

        assert call_order == ["first", "second"]


# =============================================================================
# build() Hook Integration Tests
# =============================================================================


class TestBuildWithHooks:
    """Tests for build() with hooks parameter."""

    def test_build_calls_on_start_hooks(self, default_example_course):
        """Verify on_start hooks are called."""
        hook = TrackingBuildOnStartHook()
        hooks: Hooks = {"materials.build:on_start": [hook]}

        universe = automata.materials.discover(default_example_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for collections, publications
        assert len(hook.calls) >= 1
        # Check that we got some calls
        assert any("on_start" in call for call in hook.calls)

    def test_build_calls_on_recipe_hooks(self, default_example_course):
        """Verify on_recipe hooks are called when recipe runs."""
        hook = TrackingBuildOnRecipeHook()
        hooks: Hooks = {"materials.build:on_recipe": [hook]}

        universe = automata.materials.discover(default_example_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for artifacts with recipes
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_recipe" for call in hook.calls)

    def test_build_calls_on_success_hooks(self, default_example_course):
        """Verify on_success hooks are called on successful build."""
        hook = TrackingBuildOnSuccessHook()
        hooks: Hooks = {"materials.build:on_success": [hook]}

        universe = automata.materials.discover(default_example_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for successfully built artifacts
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_success" for call in hook.calls)

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

        hook = TrackingBuildOnTooSoonHook()
        hooks: Hooks = {"materials.build:on_too_soon": [hook]}

        universe = automata.materials.discover(temporary_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for the unreleased artifact
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_too_soon" for call in hook.calls)

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

        hook = TrackingBuildOnNotReadyHook()
        hooks: Hooks = {"materials.build:on_not_ready": [hook]}

        universe = automata.materials.discover(temporary_course.path)
        automata.materials.build(universe, hooks=hooks)

        # Should have been called for the not-ready artifact
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_not_ready" for call in hook.calls)


# =============================================================================
# export() Hook Integration Tests
# =============================================================================


class TestExportWithHooks:
    """Tests for export() with hooks parameter."""

    def test_export_calls_on_copy_hooks(self, default_example_course, tmp_path):
        """Verify on_copy hooks are called when copying files."""
        hook = TrackingExportOnCopyHook()
        hooks: Hooks = {"materials.export:on_copy": [hook]}

        universe = automata.materials.discover(default_example_course.path)
        built = automata.materials.build(universe)

        # Use a separate output directory to avoid source == destination
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        automata.materials.export(built, output_dir, hooks=hooks)

        # Should have been called for each copied file
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_copy" for call in hook.calls)

    def test_export_calls_on_node_hooks(self, default_example_course, tmp_path):
        """Verify on_node hooks are called for each node."""
        hook = TrackingExportOnNodeHook()
        hooks: Hooks = {"materials.export:on_node": [hook]}

        universe = automata.materials.discover(default_example_course.path)
        built = automata.materials.build(universe)

        # Use a separate output directory to avoid source == destination
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        automata.materials.export(built, output_dir, hooks=hooks)

        # Should have been called for nodes
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_node" for call in hook.calls)


# =============================================================================
# filter() Hook Integration Tests
# =============================================================================


class TestFilterWithHooks:
    """Tests for filter() with hooks parameter."""

    def test_filter_calls_on_hit_hooks(self, default_example_course):
        """Verify on_hit hooks are called for matching nodes."""
        hook = TrackingFilterOnHitHook()
        hooks: Hooks = {"materials.filter:on_hit": [hook]}

        universe = automata.materials.discover(default_example_course.path)

        # Filter that matches everything
        automata.materials.filter(
            universe,
            predicate=lambda key, node: True,
            hooks=hooks,
        )

        # Should have been called for matching nodes
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_hit" for call in hook.calls)

    def test_filter_calls_on_miss_hooks(self, default_example_course):
        """Verify on_miss hooks are called for non-matching nodes."""
        hook = TrackingFilterOnMissHook()
        hooks: Hooks = {"materials.filter:on_miss": [hook]}

        universe = automata.materials.discover(default_example_course.path)

        # Filter that matches nothing
        automata.materials.filter(
            universe,
            predicate=lambda key, node: False,
            hooks=hooks,
        )

        # Should have been called for non-matching nodes
        assert len(hook.calls) >= 1
        assert all(call[0] == "on_miss" for call in hook.calls)


# =============================================================================
# Backward Compatibility Tests
# =============================================================================


class TestBackwardCompatibility:
    """Tests for backward compatibility with callbacks parameter."""

    def test_discover_callbacks_still_works(self, default_example_course):
        """Verify callbacks parameter still works."""
        callbacks = automata.materials.DiscoverCallbacks()
        callbacks.on_collection = Mock(return_value=None)

        # Should not raise
        automata.materials.discover(default_example_course.path, callbacks=callbacks)

        # Should have been called
        assert callbacks.on_collection.called

    def test_build_callbacks_still_works(self, default_example_course):
        """Verify callbacks parameter still works."""
        callbacks = automata.materials.BuildCallbacks()
        callbacks.on_success = Mock(return_value=None)

        universe = automata.materials.discover(default_example_course.path)

        # Should not raise
        automata.materials.build(universe, callbacks=callbacks)

        # Should have been called
        assert callbacks.on_success.called

    def test_export_callbacks_still_works(self, default_example_course, tmp_path):
        """Verify callbacks parameter still works."""
        callbacks = automata.materials.ExportCallbacks()
        callbacks.on_copy = Mock(return_value=None)

        universe = automata.materials.discover(default_example_course.path)
        built = automata.materials.build(universe)

        # Use a separate output directory to avoid source == destination
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Should not raise
        automata.materials.export(built, output_dir, callbacks=callbacks)

        # Should have been called
        assert callbacks.on_copy.called

    def test_filter_callbacks_still_works(self, default_example_course):
        """Verify callbacks parameter still works."""
        callbacks = automata.materials.FilterCallbacks()
        callbacks.on_hit = Mock(return_value=None)

        universe = automata.materials.discover(default_example_course.path)

        # Should not raise
        automata.materials.filter(
            universe,
            predicate=lambda key, node: True,
            callbacks=callbacks,
        )

        # Should have been called
        assert callbacks.on_hit.called
