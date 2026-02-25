"""Tests for the CLI entry point.

The bug: pyproject.toml originally pointed to `server:main` which is an
`async def`. pip-generated console_scripts wrappers call the target function
directly, so `main()` returned a coroutine object instead of running the
server. The fix is a sync `run()` wrapper that calls `asyncio.run(main())`.

These tests replicate the exact failure mode: call the entry point function
as a plain callable (no await) and assert it behaves like a sync function,
not an async one. This mirrors what pip does.
"""

import asyncio
import inspect
import importlib.metadata


def test_run_is_not_a_coroutine_function():
    """run() must be a regular sync function, not async def.

    If this fails, calling run() from a pip-generated entry point wrapper
    will return a coroutine object and emit RuntimeWarning.
    """
    from w8s_astro_mcp.server import run
    assert not inspect.iscoroutinefunction(run), (
        "run() is async — pip entry points call it directly without await, "
        "so it would return a coroutine object instead of running the server"
    )


def test_main_is_a_coroutine_function():
    """main() should remain async — run() wraps it with asyncio.run()."""
    from w8s_astro_mcp.server import main
    assert inspect.iscoroutinefunction(main)


def test_calling_run_does_not_return_coroutine(monkeypatch):
    """Simulate what pip does: call run() as a plain function.

    Patch asyncio.run so the server doesn't actually start, then assert
    the return value is not a coroutine (i.e. run() didn't accidentally
    become async again).
    """
    import w8s_astro_mcp.server as server_module

    called_with_coroutine = []

    def fake_asyncio_run(coro):
        called_with_coroutine.append(inspect.iscoroutine(coro))
        # Close the coroutine cleanly to avoid ResourceWarning
        coro.close()

    monkeypatch.setattr(asyncio, "run", fake_asyncio_run)

    result = server_module.run()  # called exactly as pip would call it

    assert result is None, (
        f"run() returned {result!r} — if this is a coroutine the entry point is broken"
    )
    assert called_with_coroutine == [True], (
        "run() should have passed a coroutine to asyncio.run()"
    )


def test_pyproject_entry_point_targets_run():
    """pyproject.toml [project.scripts] must point to server:run, not server:main.

    Reads the installed package metadata so this catches any future
    accidental revert of the entry point.
    """
    try:
        eps = importlib.metadata.entry_points(group="console_scripts")
    except TypeError:
        # Python 3.8 compat
        eps = importlib.metadata.entry_points().get("console_scripts", [])

    our_ep = next((ep for ep in eps if ep.name == "w8s-astro-mcp"), None)

    if our_ep is None:
        # Package not installed in editable mode — skip rather than false-fail
        import pytest
        pytest.skip("w8s-astro-mcp not found in installed entry points (not installed editable?)")

    assert our_ep.value == "w8s_astro_mcp.server:run", (
        f"Entry point is '{our_ep.value}' — should be 'w8s_astro_mcp.server:run'. "
        "Pointing at an async def will produce a coroutine object when invoked by pip."
    )
