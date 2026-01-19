"""Tests for the descriptor-based hook system."""

import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from automata import (
    HookDescriptor,
    HookInteractor,
    Hooks,
    HooksBase,
    Registry,
    ResolveOverrides,
    WebsiteContent,
    hook,
    merge_resolve_results,
)

# =============================================================================
# Hooks Class Tests
# =============================================================================


class TestHooksClass:
    """Tests for the centralized Hooks class."""

    def test_hooks_instance_creation(self):
        """Verify Hooks can be instantiated."""
        hooks = Hooks()
        assert isinstance(hooks, HooksBase)
        assert isinstance(hooks._registry, dict)

    def test_hook_names_are_defined(self):
        """Verify all expected hook points exist on Hooks class."""
        expected_hooks = [
            "discover_on_collection",
            "discover_on_publication",
            "discover_on_skip",
            "pre_resolve",
            "build_on_start",
            "build_on_too_soon",
            "build_on_not_ready",
            "build_on_missing",
            "build_on_recipe",
            "build_on_success",
            "export_on_copy",
            "export_on_node",
            "filter_on_hit",
            "filter_on_miss",
            "pre_generate_website",
            "post_generate_website",
        ]

        hooks = Hooks()
        for name in expected_hooks:
            assert hasattr(hooks, name), f"Hook '{name}' not found on Hooks"
            interactor = getattr(hooks, name)
            assert isinstance(interactor, HookInteractor)

    def test_hooks_copy(self):
        """Verify Hooks.copy() creates independent copy."""
        hooks1 = Hooks()

        @hooks1.discover_on_skip.register(priority=50)
        def handler1(path):
            pass

        hooks2 = hooks1.copy()

        # Should have the same handler
        assert len(hooks2._registry["discover_on_skip"]) == 1

        # Adding to hooks2 shouldn't affect hooks1
        @hooks2.discover_on_skip.register(priority=60)
        def handler2(path):
            pass

        assert len(hooks1._registry["discover_on_skip"]) == 1
        assert len(hooks2._registry["discover_on_skip"]) == 2


# =============================================================================
# Hook Registration Tests
# =============================================================================


class TestHookRegistration:
    """Tests for hook registration via decorator."""

    def test_register_adds_to_registry(self):
        """Verify register() adds hook to registry."""
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=50)
        def my_hook(path: Path) -> None:
            pass

        assert "discover_on_skip" in hooks._registry
        assert len(hooks._registry["discover_on_skip"]) == 1
        assert hooks._registry["discover_on_skip"][0] == (50, my_hook)

    def test_register_respects_priority(self):
        """Verify register() stores the priority."""
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=25)
        def hook_25(path: Path) -> None:
            pass

        @hooks.discover_on_skip.register(priority=75)
        def hook_75(path: Path) -> None:
            pass

        assert hooks._registry["discover_on_skip"][0] == (25, hook_25)
        assert hooks._registry["discover_on_skip"][1] == (75, hook_75)

    def test_register_returns_original_function(self):
        """Verify register() returns the original function."""
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=50)
        def my_hook(path: Path) -> str:
            return "result"

        # The decorator should return the original function
        assert my_hook(Path("/test")) == "result"

    def test_append_adds_to_registry(self):
        """Verify append() adds hook tuple to registry."""
        hooks = Hooks()

        def my_hook(path: Path) -> None:
            pass

        hooks.discover_on_skip.append((50, my_hook))

        assert hooks._registry["discover_on_skip"][0] == (50, my_hook)


# =============================================================================
# Script Hook Tests
# =============================================================================


class TestFromScript:
    """Tests for from_script method on HookInteractor."""

    def test_from_script_returns_tuple(self):
        """Verify from_script returns (priority, callable) tuple."""
        hooks = Hooks()
        result = hooks.post_generate_website.from_script(
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
        hooks = Hooks()
        result = hooks.post_generate_website.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=75,
        )

        assert result[0] == 75

    @patch("subprocess.run")
    def test_from_script_executes_command(self, mock_run):
        """Verify script hook executes command with mocked subprocess."""
        mock_run.return_value = Mock(returncode=0)

        hooks = Hooks()
        _, hook_fn = hooks.post_generate_website.from_script(
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

        hooks = Hooks()
        _, hook_fn = hooks.post_generate_website.from_script(
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
        hooks = Hooks()
        # pre_generate_website doesn't have serialize_args
        with pytest.raises(ValueError, match="not scriptable"):
            hooks.pre_generate_website.from_script(
                command="echo hello",
                cwd=Path("/tmp"),
                priority=50,
            )


# =============================================================================
# Dataclass Tests
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
    """Tests for hook execution via direct call."""

    def test_execute_runs_in_priority_order(self):
        """Verify lower priority runs first."""
        call_order = []
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=50)
        def hook_a(path):
            call_order.append("A")

        @hooks.discover_on_skip.register(priority=10)
        def hook_b(path):
            call_order.append("B")

        @hooks.discover_on_skip.register(priority=100)
        def hook_c(path):
            call_order.append("C")

        hooks.discover_on_skip(Path("/test"))

        # Should be B (10), A (50), C (100)
        assert call_order == ["B", "A", "C"]

    def test_execute_preserves_insertion_order_for_ties(self):
        """Verify stable sort preserves insertion order for ties."""
        call_order = []
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=50)
        def hook_1(path):
            call_order.append("first")

        @hooks.discover_on_skip.register(priority=50)
        def hook_2(path):
            call_order.append("second")

        @hooks.discover_on_skip.register(priority=50)
        def hook_3(path):
            call_order.append("third")

        hooks.discover_on_skip(Path("/test"))

        # Same priority, should preserve insertion order
        assert call_order == ["first", "second", "third"]

    def test_execute_returns_results(self):
        """Verify hook results are collected."""
        hooks = Hooks()

        @hooks.pre_resolve.register(priority=10)
        def hook_1(call_site, path):
            return ResolveOverrides(global_variables={"x": 1})

        @hooks.pre_resolve.register(priority=20)
        def hook_2(call_site, path):
            return ResolveOverrides(global_variables={"y": 2})

        results = hooks.pre_resolve("test", Path("/test"))

        assert len(results) == 2
        assert results[0].global_variables["x"] == 1
        assert results[1].global_variables["y"] == 2

    def test_execute_with_no_hooks_returns_empty_list(self):
        """Verify no hooks registered returns empty list."""
        hooks = Hooks()

        results = hooks.discover_on_skip(Path("/test"))

        assert results == []

    def test_hook_exception_propagates(self):
        """Verify no silent swallowing of exceptions."""
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=50)
        def failing_hook(path):
            raise ValueError("Hook failed!")

        with pytest.raises(RuntimeError) as exc_info:
            hooks.discover_on_skip(Path("/test"))

        assert "discover_on_skip" in str(exc_info.value)
        assert "priority 50" in str(exc_info.value)
        assert "Hook failed!" in str(exc_info.value)


# =============================================================================
# Pipeline Execution Tests
# =============================================================================


class TestPipelineExecution:
    """Tests for pipeline execution mode (hooks with pipeline_arg set)."""

    def test_pipeline_passes_through_values(self):
        """Verify pipeline passes output from one hook to the next."""
        hooks = Hooks()

        @hooks.pre_generate_website.register(priority=50)
        def add_content(website_content, **kwargs):
            new_content = dict(website_content.content)
            new_content["added.html"] = "Added by hook"
            return WebsiteContent(
                content=new_content,
                assets=website_content.assets,
                static_files=website_content.static_files,
            )

        @hooks.pre_generate_website.register(priority=100)
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

        result = hooks.pre_generate_website(
            initial,
            materials=Mock(),
            website_config=Mock(),
            build_directory=Path("/build"),
            vars={},
            current_time=datetime.datetime.now(),
        )

        # Original content preserved
        assert result.content["index.html"] == "Original"
        # Added content was modified by second hook
        assert result.content["added.html"] == "Modified by second hook"

    def test_pipeline_returns_initial_when_no_hooks(self):
        """Verify pipeline returns initial value when no hooks registered."""
        hooks = Hooks()

        initial = WebsiteContent(content={"page.html": "Content"})

        result = hooks.pre_generate_website(
            initial,
            materials=Mock(),
            website_config=Mock(),
            build_directory=Path("/build"),
            vars={},
            current_time=datetime.datetime.now(),
        )

        assert result is initial

    def test_pipeline_skips_none_results(self):
        """Verify pipeline skips hooks that return None."""
        hooks = Hooks()

        @hooks.pre_generate_website.register(priority=50)
        def returns_none(website_content, **kwargs):
            return None  # Should be skipped

        initial = WebsiteContent(content={"page.html": "Content"})

        result = hooks.pre_generate_website(
            initial,
            materials=Mock(),
            website_config=Mock(),
            build_directory=Path("/build"),
            vars={},
            current_time=datetime.datetime.now(),
        )

        # Should still have original content
        assert result.content["page.html"] == "Content"


# =============================================================================
# Reduce Results Tests
# =============================================================================


class TestReduceResults:
    """Tests for reduce() method and merge_resolve_results function."""

    def test_pre_resolve_hook_reduce_results(self):
        """Verify pre_resolve reduce merges overrides."""

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

        merged = merge_resolve_results(results)

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

        merged = merge_resolve_results(results)

        assert "foo" in merged.functions
        assert merged.global_variables["x"] == 1

    def test_reduce_empty_results(self):
        """Verify empty results list returns empty overrides."""
        merged = merge_resolve_results([])

        assert merged.functions == {}
        assert merged.global_variables == {}


# =============================================================================
# Registry Merge Tests
# =============================================================================


class TestMergeRegistry:
    """Tests for merge_registry method."""

    def test_merge_registry_adds_hooks(self):
        """Verify merge_registry adds hooks from external registry."""
        hooks = Hooks()

        def external_hook(path):
            return "external"

        external_registry: Registry = {
            "discover_on_skip": [(50, external_hook)],
        }

        hooks.merge_registry(external_registry)

        assert len(hooks._registry["discover_on_skip"]) == 1
        assert hooks._registry["discover_on_skip"][0] == (50, external_hook)

    def test_merge_registry_accumulates_hooks(self):
        """Verify merge_registry adds to existing hooks."""
        hooks = Hooks()

        @hooks.discover_on_skip.register(priority=10)
        def internal_hook(path):
            return "internal"

        def external_hook(path):
            return "external"

        external_registry: Registry = {
            "discover_on_skip": [(50, external_hook)],
        }

        hooks.merge_registry(external_registry)

        assert len(hooks._registry["discover_on_skip"]) == 2
        assert hooks._registry["discover_on_skip"][0] == (10, internal_hook)
        assert hooks._registry["discover_on_skip"][1] == (50, external_hook)


# =============================================================================
# Custom Hook Decorator Tests
# =============================================================================


class TestHookDecorator:
    """Tests for the @hook decorator."""

    def test_hook_decorator_creates_descriptor(self):
        """Verify @hook creates a HookDescriptor."""

        class TestHooks(HooksBase):
            @hook
            @staticmethod
            def my_test_hook(arg: str) -> str:
                raise NotImplementedError

        # The class attribute should be a HookDescriptor
        assert isinstance(TestHooks.__dict__["my_test_hook"], HookDescriptor)

    def test_hook_decorator_with_options(self):
        """Verify @hook accepts options."""

        def custom_reduce(results):
            return results[0] if results else None

        class TestHooks(HooksBase):
            @hook(reduce_results=custom_reduce)
            @staticmethod
            def my_test_hook(arg: str) -> str:
                raise NotImplementedError

        hooks = TestHooks()
        # The reduce method should use our custom reducer
        result = hooks.my_test_hook.reduce(["a", "b", "c"])
        assert result == "a"

    def test_custom_hooks_class(self):
        """Verify custom HooksBase subclass works correctly."""

        class MyHooks(HooksBase):
            @hook
            @staticmethod
            def on_event(name: str, value: int) -> str:
                raise NotImplementedError

        hooks = MyHooks()

        @hooks.on_event.register(priority=50)
        def handler(name, value):
            return f"{name}:{value}"

        results = hooks.on_event("test", 42)
        assert results == ["test:42"]
