"""
Common executor utilities to ensure every YOLO model runs on a single dedicated
background thread.  Acquire the context to run one or more blocking YOLO calls
sequentially while preventing other services (e.g. device monitor) from using
the model at the same time.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from typing import Any, Callable

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yolo-worker")
_lock = asyncio.Lock()
_device_monitor_gate = asyncio.Event()
_device_monitor_gate.set()


class YOLOContext:
    """Helper that exposes `run` to execute blocking functions on the shared thread."""

    def __init__(self, loop: asyncio.AbstractEventLoop, executor: ThreadPoolExecutor) -> None:
        self._loop = loop
        self._executor = executor

    async def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run `func(*args, **kwargs)` on the dedicated YOLO thread."""
        return await self._loop.run_in_executor(
            self._executor,
            partial(func, *args, **kwargs),
        )


@asynccontextmanager
async def acquire_yolo_context() -> YOLOContext:
    """
    Acquire exclusive access to the YOLO thread.

    All tasks that need to run YOLO inference should use this context to ensure
    that only one logical flow owns the thread at a time.
    """
    await _lock.acquire()
    try:
        loop = asyncio.get_running_loop()
        yield YOLOContext(loop, _executor)
    finally:
        _lock.release()


async def run_on_yolo_thread(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Convenience helper to run a single function on the YOLO thread."""
    async with acquire_yolo_context() as ctx:
        return await ctx.run(func, *args, **kwargs)


def is_yolo_busy() -> bool:
    """Return True if the YOLO thread is currently locked by another flow."""
    return _lock.locked()


def pause_device_monitor() -> None:
    """Prevent the device monitor from scheduling new YOLO work."""
    _device_monitor_gate.clear()


def resume_device_monitor() -> None:
    """Allow the device monitor to continue scheduling YOLO work."""
    if not _device_monitor_gate.is_set():
        _device_monitor_gate.set()


async def wait_for_device_monitor_slot() -> None:
    """
    Wait until the pipeline allows the device monitor to use the YOLO thread.
    Called inside the monitor loop before attempting inference.
    """
    await _device_monitor_gate.wait()


def is_device_monitor_paused() -> bool:
    """Convenience helper mainly for logging."""
    return not _device_monitor_gate.is_set()


def shutdown_executor() -> None:
    """Shutdown the executor (used when gracefully stopping the service)."""
    _executor.shutdown(wait=False)

