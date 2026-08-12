"""
网络/操作级重试装饰器

封装 goto_with_retry 等重试逻辑，支持可配置重试次数和延迟。
"""

import functools
import time
from typing import Callable, TypeVar

from playwright.sync_api import Error as PlaywrightError

from core.logger import get_logger

logger = get_logger("retry")

T = TypeVar("T")


def retry_on_network_error(
    max_retries: int = 3,
    base_delay: int = 30,
    retryable_exceptions: tuple = (PlaywrightError, TimeoutError, ConnectionError),
):
    """
    网络错误重试装饰器

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒），每次重试翻倍
        retryable_exceptions: 可重试的异常类型

    用法::

        @retry_on_network_error(max_retries=3, base_delay=30)
        def navigate_to(page, url):
            page.goto(url)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"[重试 {attempt}/{max_retries}] {func.__name__} 失败: {e}，"
                        f"{delay}s 后重试..."
                    )
                    time.sleep(delay)

            logger.error(
                f"[重试耗尽] {func.__name__} 在 {max_retries} 次尝试后仍失败"
            )
            raise last_exception

        return wrapper

    return decorator
