"""Run blocking I/O in a bounded thread pool.

Use this for sync SDK clients inside async request handlers so the uvicorn
event loop can keep serving other requests while the SDK call is waiting.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable, TypeVar

T = TypeVar("T")

_io_executor = ThreadPoolExecutor(
    max_workers=20,
    thread_name_prefix="sync-io",
)


async def run_sync(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Run a synchronous callable in the shared I/O executor."""
    loop = asyncio.get_running_loop()
    call = partial(func, *args, **kwargs)
    return await loop.run_in_executor(_io_executor, call)


def shutdown_executor() -> None:
    """Shut down the shared I/O executor during app shutdown."""
    _io_executor.shutdown(wait=True, cancel_futures=False)
