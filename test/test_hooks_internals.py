"""Tests for the hooks system."""

import dataclasses
import json

import pytest

from automata.hooks._internals import HooksBase, ObserverHook, PipelineHook


# --- ObserverHook ---


@dataclasses.dataclass
class SampleArgs:
    message: str
    count: int = 0


class TestObserverHook:

    def test_calls_registered_function(self):
        hook = ObserverHook[SampleArgs]()
        calls = []

        @hook.register()
        def handler(args):
            calls.append(args.message)

        hook(SampleArgs(message="hello"))
        assert calls == ["hello"]

    def test_calls_multiple_in_priority_order(self):
        hook = ObserverHook[SampleArgs]()
        calls = []

        @hook.register(priority=10)
        def second(args):
            calls.append("second")

        @hook.register(priority=0)
        def first(args):
            calls.append("first")

        hook(SampleArgs(message="x"))
        assert calls == ["first", "second"]

    def test_no_implementations_does_nothing(self):
        hook = ObserverHook[SampleArgs]()
        hook(SampleArgs(message="ignored"))


# --- ObserverHook shell scripts ---


class TestObserverHookShellScript:

    def test_shell_script_receives_json_on_stdin(self, tmp_path):
        hook = ObserverHook[SampleArgs]()
        output_file = tmp_path / "output.json"

        hook.register_shell_script(f"cat > {output_file}")
        hook(SampleArgs(message="hello", count=42))

        result = json.loads(output_file.read_text())
        assert result["message"] == "hello"
        assert result["count"] == 42

    def test_shell_script_respects_priority(self, tmp_path):
        hook = ObserverHook[SampleArgs]()
        log_file = tmp_path / "log.txt"

        @hook.register(priority=0)
        def python_first(args):
            log_file.write_text("python\n")

        hook.register_shell_script(
            f'echo "shell" >> {log_file}', priority=10
        )

        hook(SampleArgs(message="x"))
        lines = log_file.read_text().strip().split("\n")
        assert lines == ["python", "shell"]

    def test_shell_script_disallowed_when_allow_shell_false(self):
        hook = ObserverHook[SampleArgs](allow_shell=False)

        with pytest.raises(TypeError, match="Shell scripts are not enabled"):
            hook.register_shell_script("echo hi")

    def test_shell_script_with_custom_serializer(self, tmp_path):
        output_file = tmp_path / "output.txt"

        hook = ObserverHook[SampleArgs](
            serializer=lambda args: f"custom:{args.message}"
        )
        hook.register_shell_script(f"cat > {output_file}")
        hook(SampleArgs(message="hello"))

        assert output_file.read_text() == "custom:hello"


# --- PipelineHook ---


class TestPipelineHook:

    def test_transforms_through_chain(self):
        hook = PipelineHook[SampleArgs]()

        @hook.register()
        def double(args):
            return SampleArgs(message=args.message, count=args.count * 2)

        @hook.register()
        def add_one(args):
            return SampleArgs(message=args.message, count=args.count + 1)

        result = hook(SampleArgs(message="x", count=5))
        assert result.count == 11  # (5 * 2) + 1

    def test_priority_controls_order(self):
        hook = PipelineHook[SampleArgs]()

        @hook.register(priority=10)
        def add_one(args):
            return SampleArgs(message=args.message, count=args.count + 1)

        @hook.register(priority=0)
        def double(args):
            return SampleArgs(message=args.message, count=args.count * 2)

        result = hook(SampleArgs(message="x", count=5))
        assert result.count == 11  # (5 * 2) + 1

    def test_no_implementations_returns_input(self):
        hook = PipelineHook[SampleArgs]()
        args = SampleArgs(message="unchanged", count=7)
        result = hook(args)
        assert result is args


# --- HooksBase ---


class TestHooksBase:

    def test_instances_get_independent_hooks(self):
        class MyHooks(HooksBase):
            on_event: ObserverHook[SampleArgs]

        h1 = MyHooks()
        h2 = MyHooks()

        calls = []
        h1.on_event.register()(lambda args: calls.append("h1"))

        h1.on_event(SampleArgs(message="x"))
        h2.on_event(SampleArgs(message="x"))

        assert calls == ["h1"]  # h2 should not have the handler
