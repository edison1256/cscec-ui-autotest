"""
自定义断言

提供比 assert 更友好的断言函数，自动附加上下文信息。
"""

from typing import Any


def assert_with_context(
    condition: bool,
    message: str = "",
    context: dict = None,
):
    """
    带上下文的断言

    Args:
        condition: 断言条件
        message: 失败消息
        context: 额外上下文信息
    """
    if not condition:
        ctx_str = ""
        if context:
            ctx_str = " | 上下文: " + ", ".join(f"{k}={v}" for k, v in context.items())
        raise AssertionError(f"{message}{ctx_str}")


def assert_in_range(value: Any, min_val: Any, max_val: Any, name: str = "值"):
    """断言值在范围内"""
    assert_with_context(
        min_val <= value <= max_val,
        f"{name}({value}) 不在范围 [{min_val}, {max_val}] 内",
    )


def assert_not_empty(value: Any, name: str = "值"):
    """断言值非空"""
    assert_with_context(
        bool(value),
        f"{name} 为空",
    )
