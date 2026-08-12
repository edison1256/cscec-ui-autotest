"""
数据驱动测试支持

提供装饰器和工具函数，简化参数化测试用例编写：
- @data_driven 装饰器
- 数据文件自动加载
- 用例 ID 自动生成
"""

import functools
from typing import Any, Callable, Dict, List, Optional, Union

import pytest

from utils.data_loader import get_parametrize_data, get_case_data
from core.logger import get_logger

logger = get_logger("data_driven")


def data_driven(
    module: str,
    case_name: str,
    param_name: str = "cases",
    ids: Optional[Callable] = None,
    scope: str = "function",
):
    """
    数据驱动测试装饰器

    自动从测试数据文件加载参数化数据，简化 pytest.mark.parametrize 使用。

    Args:
        module: 模块名称（如 "login", "console"）
        case_name: 用例名称
        param_name: 参数列表字段名，默认 "cases"
        ids: 用例 ID 生成函数，接收单个数据项，返回字符串
        scope: fixture 作用域

    Example:
        @data_driven("login", "login_failure")
        def test_login_failure(self, case):
            '''测试登录失败场景'''
            login_page.fill_credentials(case["username"], case["password"])
            login_page.should_login_fail()
    """

    def decorator(func: Callable) -> Callable:
        # 加载数据
        cases = get_parametrize_data(module, case_name, param_name)

        if not cases:
            logger.warning(f"[数据驱动] 未找到数据: {module}.{case_name}.{param_name}")
            cases = [{}]

        # 生成用例 ID
        if ids:
            case_ids = [ids(case) for case in cases]
        else:
            # 默认使用 case 中的 name 字段或生成序号
            case_ids = [
                case.get("name", f"case_{i}")
                for i, case in enumerate(cases)
            ]

        # 使用 pytest.mark.parametrize
        @pytest.mark.parametrize("case", cases, ids=case_ids, scope=scope)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def data_case(
    module: str,
    case_name: str,
    field: Optional[str] = None,
    scope: str = "function",
):
    """
    单一数据用例装饰器

    加载单个测试用例数据，适用于不需要参数化的场景。

    Args:
        module: 模块名称
        case_name: 用例名称
        field: 只返回特定字段
        scope: fixture 作用域

    Example:
        @data_case("login", "login_success")
        def test_login_success(self, data, login_page):
            '''测试正常登录'''
            login_page.login(data["username"], data["password"])
            login_page.should_login_succeed()
    """

    def decorator(func: Callable) -> Callable:
        @pytest.fixture(scope=scope)
        def data():
            case_data = get_case_data(module, case_name)
            if field:
                return case_data.get(field, {})
            return case_data

        # 注入 fixture
        func.__pytest_data_fixture__ = data

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


class CaseData:
    """
    测试用例数据包装类

    提供便捷的数据访问方法
    """

    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    @property
    def data(self) -> Dict[str, Any]:
        """返回原始数据"""
        return self._data

    def validate_required(self, *keys: str) -> "CaseData":
        """
        验证必需字段存在

        Raises:
            ValueError: 缺少必需字段
        """
        missing = [k for k in keys if k not in self._data]
        if missing:
            raise ValueError(f"缺少必需字段: {missing}")
        return self

    def to_kwargs(self, *keys: str) -> Dict[str, Any]:
        """
        提取指定字段为关键字参数

        Args:
            *keys: 要提取的字段名

        Returns:
            字段名到值的映射
        """
        if keys:
            return {k: self._data[k] for k in keys if k in self._data}
        return self._data.copy()


def load_cases(module: str, case_name: str) -> List[CaseData]:
    """
    加载测试用例列表，返回 CaseData 对象列表

    Args:
        module: 模块名称
        case_name: 用例名称

    Returns:
        CaseData 对象列表
    """
    cases = get_parametrize_data(module, case_name)
    return [CaseData(case) for case in cases]


def parametrize_from_file(
    file_path: str,
    param_name: str = "cases",
    ids: Optional[Callable] = None,
):
    """
    从数据文件创建参数化测试

    Args:
        file_path: 数据文件路径（相对于 tests/data）
        param_name: 参数列表字段名
        ids: 用例 ID 生成函数

    Example:
        @parametrize_from_file("login/common.yaml", param_name="login_failure")
        def test_login_failure(self, case):
            ...
    """

    def decorator(func: Callable) -> Callable:
        from utils.data_loader import load_data

        data = load_data(file_path)
        cases = data.get(param_name, [])

        if not cases:
            logger.warning(f"[参数化] 未找到数据: {file_path}.{param_name}")
            cases = [{}]

        if ids:
            case_ids = [ids(case) for case in cases]
        else:
            case_ids = [case.get("name", f"case_{i}") for i, case in enumerate(cases)]

        @pytest.mark.parametrize("case", cases, ids=case_ids)
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


# ────────────────────── 便捷导出 ──────────────────────

__all__ = [
    "data_driven",
    "data_case",
    "CaseData",
    "load_cases",
    "parametrize_from_file",
]
