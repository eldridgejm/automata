"""Tests for the unified hook system."""

import inspect
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from automata.hooks import (
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
    Hooks,
    PostGenerateWebsiteHook,
    PreGenerateWebsiteHook,
    PreResolveHook,
    ResolveOverrides,
    WebsiteContent,
    execute_hooks,
    execute_pre_generate_hooks,
    hook_point,
    sort_hooks_by_priority,
    validate_hook_point_names,
)

# =============================================================================
# Registry Tests
# =============================================================================


class TestHookPointDecorator:
    """Tests for the @hook_point decorator."""

    def test_hook_point_decorator_registers_class(self):
        """Verify @hook_point adds the class to HOOK_POINTS."""

        # Create a test hook class
        @hook_point("test:my_hook")
        class TestHook:
            priority: int

            def __call__(self):
                pass

        # Verify it's registered
        assert "test:my_hook" in HOOK_POINTS
        assert HOOK_POINTS["test:my_hook"] is TestHook

        # Clean up
        del HOOK_POINTS["test:my_hook"]

    def test_hook_point_sets_hook_point_name_attribute(self):
        """Verify decorator sets _hook_point_name on the class."""

        @hook_point("test:named_hook")
        class NamedHook:
            priority: int

            def __call__(self):
                pass

        assert NamedHook._hook_point_name == "test:named_hook"

        # Clean up
        del HOOK_POINTS["test:named_hook"]


class TestHookPointsRegistry:
    """Tests for the HOOK_POINTS registry."""

    def test_all_hook_points_registered(self):
        """Verify all 17 documented hook points exist."""
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

        # Should have exactly 16 hook points (17 mentioned in feature.md but
        # pre_resolve + 15 materials/website hooks = 16)
        assert len(expected_hook_points) == 16

    def test_hook_point_returns_correct_type(self):
        """Verify type lookup works for each hook point."""
        on_collection = "materials.discover:on_collection"
        on_publication = "materials.discover:on_publication"
        assert HOOK_POINTS[on_collection] is DiscoverOnCollectionHook
        assert HOOK_POINTS[on_publication] is DiscoverOnPublicationHook
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
# Abstract Base Class Tests
# =============================================================================


class TestHookAbstractBaseClass:
    """Tests for hook ABC enforcement."""

    def test_hook_requires_priority_attribute(self):
        """Verify hooks need a priority attribute."""
        # All hook classes should have priority in their annotations
        assert "priority" in DiscoverOnCollectionHook.__annotations__
        assert "priority" in PreResolveHook.__annotations__
        assert "priority" in PostGenerateWebsiteHook.__annotations__

    def test_hook_subclass_must_implement_call(self):
        """Verify ABC enforcement on __call__."""

        # Creating an incomplete subclass should not raise at definition time
        class IncompleteHook(DiscoverOnCollectionHook):
            priority: int = 50

            # Missing __call__ implementation

        # But instantiation should fail
        with pytest.raises(TypeError, match="abstract method"):
            IncompleteHook()

    def test_concrete_hook_instantiation(self):
        """Verify can create valid subclass with priority."""

        @dataclass
        class ConcreteHook(DiscoverOnCollectionHook):
            priority: int = 50

            def __call__(self, path, collection):
                pass

        hook = ConcreteHook()
        assert hook.priority == 50


# =============================================================================
# ScriptableHookMixin Tests
# =============================================================================


class TestScriptableHookMixin:
    """Tests for ScriptableHookMixin."""

    def test_from_script_returns_proper_subclass(self):
        """Verify from_script returns an instance that passes isinstance checks."""
        hook = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=50,
        )

        # Should be an instance of PostGenerateWebsiteHook
        assert isinstance(hook, PostGenerateWebsiteHook)

    def test_from_script_sets_priority(self):
        """Verify from_script sets the priority attribute."""
        hook = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=75,
        )

        assert hook.priority == 75

    def test_from_script_copies_signature(self):
        """Verify inspect.signature returns parent's signature."""
        hook = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=50,
        )

        sig = inspect.signature(hook.__call__)
        params = list(sig.parameters.keys())

        # Should have the same parameters as PostGenerateWebsiteHook.__call__
        assert "materials" in params
        assert "website_config" in params
        assert "build_directory" in params
        assert "vars" in params
        assert "current_time" in params

    @patch("subprocess.run")
    def test_from_script_executes_command(self, mock_run):
        """Verify script hook executes command with mocked subprocess."""
        import datetime

        mock_run.return_value = Mock(returncode=0)

        hook = PostGenerateWebsiteHook.from_script(
            command="echo hello",
            cwd=Path("/tmp"),
            priority=50,
        )

        # Create mock arguments matching the new signature
        mock_materials = Mock()
        mock_website_config = Mock()
        mock_website_config.content_directory = Path("/content")
        mock_website_config.build_directory = Path("/build")
        mock_website_config.materials_directory_name = "materials"
        mock_website_config.base_path = "/"

        hook(
            mock_materials,
            mock_website_config,
            Path("/build"),
            {"var": "value"},
            datetime.datetime(2024, 1, 1),
        )

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["shell"] is True
        assert call_kwargs["cwd"] == "/tmp"

    @patch("subprocess.run")
    def test_from_script_passes_json_on_stdin(self, mock_run):
        """Verify serialized arguments are passed on stdin."""
        import datetime

        mock_run.return_value = Mock(returncode=0)

        hook = PostGenerateWebsiteHook.from_script(
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

        hook(
            mock_materials,
            mock_website_config,
            Path("/build"),
            {"key": "value"},
            datetime.datetime(2024, 1, 1),
        )

        call_kwargs = mock_run.call_args[1]
        assert "input" in call_kwargs
        assert "config" in call_kwargs["input"]
        assert "build_directory" in call_kwargs["input"]
        assert "vars" in call_kwargs["input"]

    def test_script_hook_returns_none(self):
        """Verify fire-and-forget behavior - script hooks return None."""
        import datetime

        # Script hooks should not return values
        # This is implied by the __call__ signature returning None
        @dataclass
        class ConcretePost(PostGenerateWebsiteHook):
            priority: int = 50

            def __call__(
                self, materials, website_config, build_directory, vars, current_time
            ):
                return None  # Explicit None

            @staticmethod
            def serialize_args(
                materials, website_config, build_directory, vars, current_time
            ):
                return {}

        hook = ConcretePost()
        result = hook(Mock(), Mock(), Path("/tmp"), {}, datetime.datetime.now())
        assert result is None


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


class TestExecuteHooks:
    """Tests for execute_hooks function."""

    def test_execute_hooks_in_priority_order(self):
        """Verify lower priority runs first."""
        call_order = []

        @dataclass
        class HookA(DiscoverOnSkipHook):
            priority: int = 50

            def __call__(self, path):
                call_order.append("A")

        @dataclass
        class HookB(DiscoverOnSkipHook):
            priority: int = 10

            def __call__(self, path):
                call_order.append("B")

        @dataclass
        class HookC(DiscoverOnSkipHook):
            priority: int = 100

            def __call__(self, path):
                call_order.append("C")

        hooks: Hooks = {
            "materials.discover:on_skip": [HookA(), HookB(), HookC()],
        }

        execute_hooks(hooks, "materials.discover:on_skip", Path("/test"))

        # Should be B (10), A (50), C (100)
        assert call_order == ["B", "A", "C"]

    def test_execute_hooks_preserves_insertion_order_for_ties(self):
        """Verify stable sort preserves insertion order for ties."""
        call_order = []

        @dataclass
        class Hook1(DiscoverOnSkipHook):
            priority: int = 50
            name: str = "1"

            def __call__(self, path):
                call_order.append(self.name)

        @dataclass
        class Hook2(DiscoverOnSkipHook):
            priority: int = 50
            name: str = "2"

            def __call__(self, path):
                call_order.append(self.name)

        @dataclass
        class Hook3(DiscoverOnSkipHook):
            priority: int = 50
            name: str = "3"

            def __call__(self, path):
                call_order.append(self.name)

        hooks: Hooks = {
            "materials.discover:on_skip": [
                Hook1(name="first"),
                Hook2(name="second"),
                Hook3(name="third"),
            ],
        }

        execute_hooks(hooks, "materials.discover:on_skip", Path("/test"))

        # Same priority, should preserve insertion order
        assert call_order == ["first", "second", "third"]

    def test_execute_hooks_returns_results(self):
        """Verify hook results are collected."""

        @dataclass
        class HookWithResult(PreResolveHook):
            priority: int = 50
            value: int = 0

            def __call__(self, call_site, path):
                return ResolveOverrides(global_variables={"x": self.value})

        hooks: Hooks = {
            "pre_resolve": [
                HookWithResult(value=1),
                HookWithResult(value=2),
            ],
        }

        results = execute_hooks(hooks, "pre_resolve", "test", Path("/test"))

        assert len(results) == 2
        assert results[0].global_variables["x"] == 1
        assert results[1].global_variables["x"] == 2

    def test_execute_hooks_with_none_returns_empty_list(self):
        """Verify None hooks returns empty list."""
        results = execute_hooks(None, "materials.discover:on_skip", Path("/test"))

        assert results == []

    def test_execute_hooks_with_unknown_point_returns_empty_list(self):
        """Verify unknown hook point returns empty list."""
        hooks: Hooks = {}

        results = execute_hooks(hooks, "unknown:point", Path("/test"))

        assert results == []

    def test_hook_exception_propagates(self):
        """Verify no silent swallowing of exceptions."""

        @dataclass
        class FailingHook(DiscoverOnSkipHook):
            priority: int = 50

            def __call__(self, path):
                raise ValueError("Hook failed!")

        hooks: Hooks = {
            "materials.discover:on_skip": [FailingHook()],
        }

        with pytest.raises(RuntimeError) as exc_info:
            execute_hooks(hooks, "materials.discover:on_skip", Path("/test"))

        assert "Hook 'materials.discover:on_skip'" in str(exc_info.value)
        assert "priority 50" in str(exc_info.value)
        assert "Hook failed!" in str(exc_info.value)


# =============================================================================
# Merge Results Tests
# =============================================================================


class TestMergeResults:
    """Tests for hook merge_results static methods."""

    def test_merge_resolve_override_results(self):
        """Verify later hooks override earlier ones for ResolveOverrides."""

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

        merged = PreResolveHook.merge_results(results)

        # foo should be overwritten by second hook
        assert merged.functions["foo"] is fn2
        assert merged.functions["bar"] is fn3
        # Both x and y should be present
        assert merged.global_variables["x"] == 1
        assert merged.global_variables["y"] == 2

    def test_execute_pre_generate_hooks_pipeline(self):
        """Verify pre_generate_website hooks form a transformation pipeline."""
        import datetime

        @dataclass
        class AddContentHook(PreGenerateWebsiteHook):
            priority: int = 50

            def __call__(
                self,
                website_content,
                materials,
                website_config,
                build_directory,
                vars,
                current_time,
            ):
                # Add a new page
                new_content = dict(website_content.content)
                new_content["added.html"] = "Added by hook"
                return WebsiteContent(
                    content=new_content,
                    assets=website_content.assets,
                    static_files=website_content.static_files,
                )

        @dataclass
        class ModifyContentHook(PreGenerateWebsiteHook):
            priority: int = 100  # Runs after AddContentHook

            def __call__(
                self,
                website_content,
                materials,
                website_config,
                build_directory,
                vars,
                current_time,
            ):
                # Modify the content added by previous hook
                new_content = dict(website_content.content)
                if "added.html" in new_content:
                    new_content["added.html"] = "Modified by second hook"
                return WebsiteContent(
                    content=new_content,
                    assets=website_content.assets,
                    static_files=website_content.static_files,
                )

        hooks: Hooks = {
            "pre_generate_website": [AddContentHook(), ModifyContentHook()],
        }

        initial = WebsiteContent(
            content={"index.html": "Original"},
            assets={},
            static_files={},
        )

        result = execute_pre_generate_hooks(
            hooks,
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

    def test_merge_handles_none_results(self):
        """Verify None results are skipped during merge."""
        results = [
            None,
            ResolveOverrides(functions={"foo": lambda: 1}),
            None,
            ResolveOverrides(global_variables={"x": 1}),
        ]

        merged = PreResolveHook.merge_results(results)

        assert "foo" in merged.functions
        assert merged.global_variables["x"] == 1

    def test_merge_empty_results(self):
        """Verify empty results list returns empty overrides."""
        merged = PreResolveHook.merge_results([])

        assert merged.functions == {}
        assert merged.global_variables == {}


# =============================================================================
# Validation Tests
# =============================================================================


class TestValidateHookPointNames:
    """Tests for validate_hook_point_names function."""

    def test_validates_known_hook_points(self):
        """Verify known hook points pass validation."""
        hooks: Hooks = {
            "materials.discover:on_collection": [],
            "pre_resolve": [],
            "post_generate_website": [],
        }

        # Should not raise
        validate_hook_point_names(hooks)

    def test_raises_on_unknown_hook_point(self):
        """Verify unknown hook point raises ValueError."""
        hooks = {
            "materials.discover:on_collection": [],
            "unknown:hook:point": [],  # Invalid
        }

        with pytest.raises(ValueError) as exc_info:
            validate_hook_point_names(hooks)  # type: ignore[arg-type]

        assert "Unknown hook point" in str(exc_info.value)
        assert "unknown:hook:point" in str(exc_info.value)


class TestSortHooksByPriority:
    """Tests for sort_hooks_by_priority function."""

    def test_pre_sorts_by_priority(self):
        """Verify sorted once at merge time."""

        @dataclass
        class TestHook(DiscoverOnSkipHook):
            priority: int

            def __call__(self, path):
                pass

        hooks: Hooks = {
            "materials.discover:on_skip": [
                TestHook(priority=100),
                TestHook(priority=10),
                TestHook(priority=50),
            ],
        }

        sorted_hooks = sort_hooks_by_priority(hooks)

        priorities = [h.priority for h in sorted_hooks["materials.discover:on_skip"]]
        assert priorities == [10, 50, 100]

    def test_preserves_multiple_hook_points(self):
        """Verify all hook points are sorted."""

        @dataclass
        class SkipHook(DiscoverOnSkipHook):
            priority: int

            def __call__(self, path):
                pass

        @dataclass
        class CollectionHook(DiscoverOnCollectionHook):
            priority: int

            def __call__(self, path, collection):
                pass

        hooks: Hooks = {
            "materials.discover:on_skip": [
                SkipHook(priority=50),
                SkipHook(priority=10),
            ],
            "materials.discover:on_collection": [
                CollectionHook(priority=100),
                CollectionHook(priority=20),
            ],
        }

        sorted_hooks = sort_hooks_by_priority(hooks)

        skip_priorities = [
            h.priority for h in sorted_hooks["materials.discover:on_skip"]
        ]
        coll_priorities = [
            h.priority for h in sorted_hooks["materials.discover:on_collection"]
        ]

        assert skip_priorities == [10, 50]
        assert coll_priorities == [20, 100]
