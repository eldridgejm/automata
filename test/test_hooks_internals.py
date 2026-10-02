"""Tests for the hooks system."""

import dataclasses
import json

import pytest

from automata.hooks._internals import HooksBase, ObserverHook, PipelineHook


@dataclasses.dataclass
class SampleArgs:
    message: str
    count: int = 0


# ObserverHook =========================================================================


def test_observer_hook_calls_registered_function():
    hook = ObserverHook[SampleArgs]()
    calls = []

    @hook.register()
    def handler(args):
        calls.append(args.message)

    hook(SampleArgs(message="hello"))
    assert calls == ["hello"]


def test_observer_hook_calls_multiple_in_priority_order():
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


def test_observer_hook_with_no_implementations_does_nothing():
    hook = ObserverHook[SampleArgs]()
    hook(SampleArgs(message="ignored"))


# ObserverHook shell scripts ===========================================================


def test_shell_script_receives_json_on_stdin(tmp_path):
    hook = ObserverHook[SampleArgs]()
    output_file = tmp_path / "output.json"

    hook.register_shell_script(f"cat > {output_file}")
    hook(SampleArgs(message="hello", count=42))

    result = json.loads(output_file.read_text())
    assert result["message"] == "hello"
    assert result["count"] == 42


def test_shell_script_respects_priority(tmp_path):
    hook = ObserverHook[SampleArgs]()
    log_file = tmp_path / "log.txt"

    @hook.register(priority=0)
    def python_first(args):
        log_file.write_text("python\n")

    hook.register_shell_script(f'echo "shell" >> {log_file}', priority=10)

    hook(SampleArgs(message="x"))
    lines = log_file.read_text().strip().split("\n")
    assert lines == ["python", "shell"]


def test_shell_script_disallowed_when_allow_shell_false():
    hook = ObserverHook[SampleArgs](allow_shell=False)

    with pytest.raises(TypeError, match="Shell scripts are not enabled"):
        hook.register_shell_script("echo hi")


def test_shell_script_with_custom_serializer(tmp_path):
    output_file = tmp_path / "output.txt"

    hook = ObserverHook[SampleArgs](serializer=lambda args: f"custom:{args.message}")
    hook.register_shell_script(f"cat > {output_file}")
    hook(SampleArgs(message="hello"))

    assert output_file.read_text() == "custom:hello"


def test_failing_shell_script_raises(tmp_path):
    from automata.exceptions import Error

    hook = ObserverHook[SampleArgs]()
    hook.register_shell_script("cat > /dev/null && exit 2")

    with pytest.raises(Error) as excinfo:
        hook(SampleArgs(message="hello"))

    assert "exit status 2" in str(excinfo.value)


def test_shell_script_with_non_dataclass_args_raises(tmp_path):
    hook = ObserverHook[int]()
    hook.register_shell_script(f"cat > {tmp_path / 'out.json'}")

    with pytest.raises(TypeError, match="expected a dataclass"):
        hook(42)


# PipelineHook =========================================================================


def test_pipeline_hook_transforms_through_chain():
    hook = PipelineHook[SampleArgs]()

    @hook.register()
    def double(args):
        return SampleArgs(message=args.message, count=args.count * 2)

    @hook.register()
    def add_one(args):
        return SampleArgs(message=args.message, count=args.count + 1)

    result = hook(SampleArgs(message="x", count=5))
    assert result.count == 11  # (5 * 2) + 1


def test_pipeline_hook_priority_controls_order():
    hook = PipelineHook[SampleArgs]()

    @hook.register(priority=10)
    def add_one(args):
        return SampleArgs(message=args.message, count=args.count + 1)

    @hook.register(priority=0)
    def double(args):
        return SampleArgs(message=args.message, count=args.count * 2)

    result = hook(SampleArgs(message="x", count=5))
    assert result.count == 11  # (5 * 2) + 1


def test_pipeline_hook_with_no_implementations_returns_input():
    hook = PipelineHook[SampleArgs]()
    args = SampleArgs(message="unchanged", count=7)
    result = hook(args)
    assert result is args


# Hooks base class =====================================================================


def test_hooks_instances_get_independent_hooks():
    class MyHooks(HooksBase):
        on_event: ObserverHook[SampleArgs]

    h1 = MyHooks()
    h2 = MyHooks()

    calls = []
    h1.on_event.register()(lambda args: calls.append("h1"))

    h1.on_event(SampleArgs(message="x"))
    h2.on_event(SampleArgs(message="x"))

    assert calls == ["h1"]  # h2 should not have the handler
