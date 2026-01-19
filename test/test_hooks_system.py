"""Tests for the unified hook system."""

import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from automata import (
    HOOK_POINTS,
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
    Hook,
    PostGenerateWebsiteHook,
    PreGenerateWebsiteHook,
    PreResolveHook,
    Registry,
    ResolveOverrides,
    WebsiteContent,
    define_hook,
    validate_hook_point_names,
)

# =============================================================================
# Registry Tests
# =============================================================================


class TestDefineHookDecorator:
    """Tests for the @define_hook decorator."""

    def test_define_hook_creates_hook_class(self):
        """Verify @define_hook creates a proper Hook subclass."""

        @define_hook("test:my_hook")
        def TestHook(arg: str) -> None: ...

        # Verify it's a Hook subclass
        assert issubclass(TestHook, Hook)
        assert TestHook.hook_point == "test:my_hook"

        # Clean up
        del HOOK_POINTS["test:my_hook"]

    def test_define_hook_registers_in_hook_points(self):
        """Verify @define_hook adds to HOOK_POINTS."""

        @define_hook("test:registered_hook")
        def RegisteredHook(value: int) -> int: ...

        assert "test:registered_hook" in HOOK_POINTS
        assert HOOK_POINTS["test:registered_hook"] is RegisteredHook

        # Clean up
        del HOOK_POINTS["test:registered_hook"]


class TestHookPointsRegistry:
    """Tests for the HOOK_POINTS registry."""

    def test_all_hook_points_registered(self):
        """Verify all 16 documented hook points exist."""
        expected_hook_points = [
            # Resolution
            "pre_resolve",
            # Materials discovery
            "materials.discover:on_collection",
            "materials.discover:on_publication",
            "materials.discover:on_skip",
            # Materials build
            "materials.build:on_start",
            "materials.build:on_too_soon",
            "materials.build:on_not_ready",
            "materials.build:on_missing",
            "materials.build:on_recipe",
            "materials.build:on_success",
            # Materials export
            "materials.export:on_copy",
            "materials.export:on_node",
            # Materials filter
            "materials.filter:on_hit",
            "materials.filter:on_miss",
            # Website generation
            "pre_generate_website",
            "post_generate_website",
        ]

        for name in expected_hook_points:
            assert name in HOOK_POINTS, f"Hook point '{name}' not registered"

        assert len(expected_hook_points) == 16

    def test_hook_point_returns_correct_type(self):
        """Verify type lookup works for each hook point."""
        on_coll = "materials.discover:on_collection"
        on_pub = "materials.discover:on_publication"
        assert HOOK_POINTS[on_coll] is DiscoverOnCollectionHook
        assert HOOK_POINTS[on_pub] is DiscoverOnPublicationHook
        assert HOOK_POINTS["materials.discover:on_skip"] is DiscoverOnSkipHook
        assert HOOK_POINTS["materials.build:on_start"] is BuildOnStartHook
        assert HOOK_POINTS["materials.build:on_too_soon"] is BuildOnTooSoonHook
        assert HOOK_POINTS["materials.build:on_not_ready"] is BuildOnNotReadyHook
        assert HOOK_POINTS["materials.build:on_missing"] is BuildOnMissingHook
        assert HOOK_POINTS["materials.build:on_recipe"] is BuildOnRecipeHook
        assert HOOK_POINTS["materials.build:on_success"] is BuildOnSuccessHook
        assert HOOK_POINTS["materials.export:on_copy"] is ExportOnCopyHook
        assert HOOK_POINTS["materials.export:on_node"] is ExportOnNodeHook
        assert HOOK_POINTS["materials.filter:on_hit"] is FilterOnHitHook
        assert HOOK_POINTS["materials.filter:on_miss"] is FilterOnMissHook
        assert HOOK_POINTS["pre_resolve"] is PreResolveHook
        assert HOOK_POINTS["pre_generate_website"] is PreGenerateWebsiteHook
        assert HOOK_POINTS["post_generate_website"] is PostGenerateWebsiteHook


# =============================================================================
# Hook Registration Tests
# =============================================================================


class TestHookRegistration:
    """Tests for hook registration via decorator."""

    def test_register_adds_to_registry(self):
        """Verify register() adds hook to registry."""
        hooks: Registry = {}

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def my_hook(path: Path) -> None:
            pass

        assert DiscoverOnSkipHook in hooks
        assert len(hooks[DiscoverOnSkipHook]) == 1
        assert hooks[DiscoverOnSkipHook][0] == (50, my_hook)

    def test_register_respects_priority(self):
        """Verify register() stores the priority."""
        hooks: Registry = {}

        @DiscoverOnSkipHook.register(hooks, priority=25)
        def hook_25(path: Path) -> None:
            pass

        @DiscoverOnSkipHook.register(hooks, priority=75)
        def hook_75(path: Path) -> None:
            pass

        assert hooks[DiscoverOnSkipHook][0] == (25, hook_25)
        assert hooks[DiscoverOnSkipHook][1] == (75, hook_75)

    def test_register_returns_original_function(self):
        """Verify register() returns the original function."""
        hooks: Registry = {}

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def my_hook(path: Path) -> None:
            return "result"

        # The decorator should return the original function
        assert my_hook(Path("/test")) == "result"


# =============================================================================
# ScriptableHook Tests
# =============================================================================


class TestFromScript:
    """Tests for from_script class method."""

    def test_from_script_returns_tuple(self):
        """Verify from_script returns (priority, callable) tuple."""
        result = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=50,
        )

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert result[0] == 50
        assert callable(result[1])

    def test_from_script_with_custom_priority(self):
        """Verify from_script respects priority parameter."""
        result = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=75,
        )

        assert result[0] == 75

    @patch("subprocess.run")
    def test_from_script_executes_command(self, mock_run):
        """Verify script hook executes command with mocked subprocess."""
        mock_run.return_value = Mock(returncode=0)

        _, hook_fn = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=50,
        )

        # Create mock arguments
        mock_materials = Mock()
        mock_website_config = Mock()
        mock_website_config.content_directory = Path("/content")
        mock_website_config.build_directory = Path("/build")
        mock_website_config.materials_directory_name = "materials"
        mock_website_config.base_path = "/"

        hook_fn(
            materials=mock_materials,
            website_config=mock_website_config,
            build_directory=Path("/build"),
            vars={"var": "value"},
            current_time=datetime.datetime(2024, 1, 1),
        )

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["shell"] is True
        assert call_kwargs["cwd"] == "/tmp"

    @patch("subprocess.run")
    def test_from_script_passes_json_on_stdin(self, mock_run):
        """Verify serialized arguments are passed on stdin."""
        mock_run.return_value = Mock(returncode=0)

        _, hook_fn = PostGenerateWebsiteHook.from_script(
            command="cat",
            cwd=Path("/tmp"),
            priority=50,
        )

        # Create a mock Universe that can be serialized
        from automata.materials import Universe

        mock_materials = Universe(collections={})
        mock_website_config = Mock()
        mock_website_config.content_directory = Path("/content")
        mock_website_config.build_directory = Path("/build")
        mock_website_config.materials_directory_name = "materials"
        mock_website_config.base_path = "/"

        hook_fn(
            materials=mock_materials,
            website_config=mock_website_config,
            build_directory=Path("/build"),
            vars={"key": "value"},
            current_time=datetime.datetime(2024, 1, 1),
        )

        call_kwargs = mock_run.call_args[1]
        assert "input" in call_kwargs
        assert "config" in call_kwargs["input"]
        assert "build_directory" in call_kwargs["input"]
        assert "vars" in call_kwargs["input"]

    def test_from_script_raises_for_non_scriptable(self):
        """Verify from_script raises for hooks without serialize_args."""
        # PreGenerateWebsiteHook doesn't have serialize_args
        with pytest.raises(ValueError, match="not scriptable"):
            PreGenerateWebsiteHook.from_script(
                command="echo hello",
                cwd=Path("/tmp"),
                priority=50,
            )


# =============================================================================
# Override Dataclass Tests
# =============================================================================


class TestResolveOverrides:
    """Tests for ResolveOverrides dataclass."""

    def test_resolve_overrides_defaults_to_empty_dicts(self):
        """Verify default factory creates empty dicts."""
        overrides = ResolveOverrides()

        assert overrides.functions == {}
        assert overrides.global_variables == {}

    def test_resolve_overrides_with_values(self):
        """Verify can create with actual values."""

        def my_func():
            pass

        overrides = ResolveOverrides(
            functions={"my_func": my_func}, global_variables={"x": 1}
        )

        assert overrides.functions["my_func"] is my_func
        assert overrides.global_variables["x"] == 1

    def test_resolve_overrides_merge(self):
        """Verify merge combines overrides correctly."""

        def fn1():
            return 1

        def fn2():
            return 2

        overrides1 = ResolveOverrides(functions={"foo": fn1}, global_variables={"x": 1})
        overrides2 = ResolveOverrides(
            functions={"foo": fn2, "bar": fn2}, global_variables={"y": 2}
        )

        merged = overrides1.merge(overrides2)

        # foo should be overwritten by second
        assert merged.functions["foo"] is fn2
        assert merged.functions["bar"] is fn2
        # Both x and y should be present
        assert merged.global_variables["x"] == 1
        assert merged.global_variables["y"] == 2


class TestWebsiteContent:
    """Tests for WebsiteContent dataclass."""

    def test_website_content_defaults_to_empty_dicts(self):
        """Verify default factory creates empty dicts."""
        content = WebsiteContent()

        assert content.content == {}
        assert content.assets == {}
        assert content.static_files == {}

    def test_website_content_with_values(self):
        """Verify can create with actual values."""
        content = WebsiteContent(
            content={"about.html": "# About"},
            assets={"image.png": b"PNG..."},
            static_files={"style.css": "body {}"},
        )

        assert content.content["about.html"] == "# About"
        assert content.assets["image.png"] == b"PNG..."
        assert content.static_files["style.css"] == "body {}"


# =============================================================================
# Execution Tests
# =============================================================================


class TestHookExecution:
    """Tests for Hook.execute() method."""

    def test_execute_runs_in_priority_order(self):
        """Verify lower priority runs first."""
        call_order = []
        hooks: Registry = {}

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def hook_a(path):
            call_order.append("A")

        @DiscoverOnSkipHook.register(hooks, priority=10)
        def hook_b(path):
            call_order.append("B")

        @DiscoverOnSkipHook.register(hooks, priority=100)
        def hook_c(path):
            call_order.append("C")

        DiscoverOnSkipHook.execute(hooks, {"path": Path("/test")})

        # Should be B (10), A (50), C (100)
        assert call_order == ["B", "A", "C"]

    def test_execute_preserves_insertion_order_for_ties(self):
        """Verify stable sort preserves insertion order for ties."""
        call_order = []
        hooks: Registry = {}

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def hook_1(path):
            call_order.append("first")

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def hook_2(path):
            call_order.append("second")

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def hook_3(path):
            call_order.append("third")

        DiscoverOnSkipHook.execute(hooks, {"path": Path("/test")})

        # Same priority, should preserve insertion order
        assert call_order == ["first", "second", "third"]

    def test_execute_returns_results(self):
        """Verify hook results are collected."""
        hooks: Registry = {}

        @PreResolveHook.register(hooks, priority=10)
        def hook_1(call_site, path):
            return ResolveOverrides(global_variables={"x": 1})

        @PreResolveHook.register(hooks, priority=20)
        def hook_2(call_site, path):
            return ResolveOverrides(global_variables={"y": 2})

        results = PreResolveHook.execute(
            hooks, {"call_site": "test", "path": Path("/test")}
        )

        assert len(results) == 2
        assert results[0].global_variables["x"] == 1
        assert results[1].global_variables["y"] == 2

    def test_execute_with_none_registry_returns_empty_list(self):
        """Verify None hooks returns empty list."""
        results = DiscoverOnSkipHook.execute(None, {"path": Path("/test")})

        assert results == []

    def test_execute_with_empty_registry_returns_empty_list(self):
        """Verify empty registry returns empty list."""
        hooks: Registry = {}

        results = DiscoverOnSkipHook.execute(hooks, {"path": Path("/test")})

        assert results == []

    def test_hook_exception_propagates(self):
        """Verify no silent swallowing of exceptions."""
        hooks: Registry = {}

        @DiscoverOnSkipHook.register(hooks, priority=50)
        def failing_hook(path):
            raise ValueError("Hook failed!")

        with pytest.raises(RuntimeError) as exc_info:
            DiscoverOnSkipHook.execute(hooks, {"path": Path("/test")})

        assert "materials.discover:on_skip" in str(exc_info.value)
        assert "priority 50" in str(exc_info.value)
        assert "Hook failed!" in str(exc_info.value)


# =============================================================================
# Pipeline Execution Tests
# =============================================================================


class TestPipelineExecution:
    """Tests for pipeline execution mode (hooks with pipeline_arg set)."""

    def test_pipeline_passes_through_values(self):
        """Verify pipeline passes output from one hook to the next."""
        hooks: Registry = {}

        @PreGenerateWebsiteHook.register(hooks, priority=50)
        def add_content(website_content, **kwargs):
            new_content = dict(website_content.content)
            new_content["added.html"] = "Added by hook"
            return WebsiteContent(
                content=new_content,
                assets=website_content.assets,
                static_files=website_content.static_files,
            )

        @PreGenerateWebsiteHook.register(hooks, priority=100)
        def modify_content(website_content, **kwargs):
            new_content = dict(website_content.content)
            if "added.html" in new_content:
                new_content["added.html"] = "Modified by second hook"
            return WebsiteContent(
                content=new_content,
                assets=website_content.assets,
                static_files=website_content.static_files,
            )

        initial = WebsiteContent(
            content={"index.html": "Original"},
            assets={},
            static_files={},
        )

        result = PreGenerateWebsiteHook.execute(
            hooks,
            {
                "website_content": initial,
                "materials": Mock(),
                "website_config": Mock(),
                "build_directory": Path("/build"),
                "vars": {},
                "current_time": datetime.datetime.now(),
            },
        )

        # Original content preserved
        assert result.content["index.html"] == "Original"
        # Added content was modified by second hook
        assert result.content["added.html"] == "Modified by second hook"

    def test_pipeline_returns_initial_when_no_hooks(self):
        """Verify pipeline returns initial value when no hooks registered."""
        hooks: Registry = {}

        initial = WebsiteContent(content={"page.html": "Content"})

        result = PreGenerateWebsiteHook.execute(
            hooks,
            {
                "website_content": initial,
                "materials": Mock(),
                "website_config": Mock(),
                "build_directory": Path("/build"),
                "vars": {},
                "current_time": datetime.datetime.now(),
            },
        )

        assert result is initial

    def test_pipeline_skips_none_results(self):
        """Verify pipeline skips hooks that return None."""
        hooks: Registry = {}

        @PreGenerateWebsiteHook.register(hooks, priority=50)
        def returns_none(website_content, **kwargs):
            return None  # Should be skipped

        initial = WebsiteContent(content={"page.html": "Content"})

        result = PreGenerateWebsiteHook.execute(
            hooks,
            {
                "website_content": initial,
                "materials": Mock(),
                "website_config": Mock(),
                "build_directory": Path("/build"),
                "vars": {},
                "current_time": datetime.datetime.now(),
            },
        )

        # Should still have original content
        assert result.content["page.html"] == "Content"


# =============================================================================
# Reduce Results Tests
# =============================================================================


class TestReduceResults:
    """Tests for reduce_results functionality."""

    def test_pre_resolve_hook_reduce_results(self):
        """Verify PreResolveHook.reduce_results merges overrides."""

        def fn1():
            return 1

        def fn2():
            return 2

        def fn3():
            return 3

        results = [
            ResolveOverrides(functions={"foo": fn1}, global_variables={"x": 1}),
            ResolveOverrides(
                functions={"foo": fn2, "bar": fn3}, global_variables={"y": 2}
            ),
        ]

        merged = PreResolveHook.reduce_results(results)

        # foo should be overwritten by second hook
        assert merged.functions["foo"] is fn2
        assert merged.functions["bar"] is fn3
        # Both x and y should be present
        assert merged.global_variables["x"] == 1
        assert merged.global_variables["y"] == 2

    def test_reduce_handles_none_results(self):
        """Verify None results are skipped during reduce."""
        results = [
            None,
            ResolveOverrides(functions={"foo": lambda: 1}),
            None,
            ResolveOverrides(global_variables={"x": 1}),
        ]

        merged = PreResolveHook.reduce_results(results)

        assert "foo" in merged.functions
        assert merged.global_variables["x"] == 1

    def test_reduce_empty_results(self):
        """Verify empty results list returns empty overrides."""
        merged = PreResolveHook.reduce_results([])

        assert merged.functions == {}
        assert merged.global_variables == {}


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidateHookPointNames:
    """Tests for validate_hook_point_names function."""

    def test_validates_known_hook_points(self):
        """Verify known hook points pass validation."""
        hooks: Registry = {
            DiscoverOnCollectionHook: [],
            PreResolveHook: [],
            PostGenerateWebsiteHook: [],
        }

        # Should not raise
        validate_hook_point_names(hooks)

    def test_raises_on_unknown_hook_class(self):
        """Verify unknown hook class raises ValueError."""

        class FakeHook:
            pass

        hooks = {
            DiscoverOnCollectionHook: [],
            FakeHook: [],  # Invalid
        }

        with pytest.raises(ValueError) as exc_info:
            validate_hook_point_names(hooks)  # type: ignore[arg-type]

        assert "Unknown hook" in str(exc_info.value)
