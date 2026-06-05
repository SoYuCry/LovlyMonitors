"""Shared helpers for monitor loops."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

BEIJING_TZ = timezone(timedelta(hours=8))


def retry(
    max_attempts: int = 3,
    delay: float = 2,
    backoff: float = 2,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Retry a function with exponential backoff."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            attempt = 0
            current_delay = delay
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    attempt += 1
                    if attempt >= max_attempts:
                        print(f"[ERROR] {func.__name__} 失败,已重试 {max_attempts} 次: {exc}")
                        raise
                    print(
                        f"[WARN] {func.__name__} 失败 (尝试 {attempt}/{max_attempts}), "
                        f"{current_delay}秒后重试: {exc}"
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

        return wrapper

    return decorator


def get_beijing_time() -> str:
    """Return current Beijing time formatted for notifications/logs."""
    return datetime.now(BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
