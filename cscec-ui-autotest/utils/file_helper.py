"""
文件操作工具

提供测试中常用的文件操作函数。
"""

from pathlib import Path
from typing import Optional


def get_test_file(file_name: str, sub_dir: str = "") -> Optional[str]:
    """
    获取测试文件路径

    在项目的 tests/data/ 目录下查找文件

    Args:
        file_name: 文件名
        sub_dir: 子目录

    Returns:
        文件的绝对路径字符串，不存在则返回 None
    """
    base_dir = Path(__file__).resolve().parent.parent / "tests" / "data"
    if sub_dir:
        target = base_dir / sub_dir / file_name
    else:
        target = base_dir / file_name

    if target.exists():
        return str(target)
    return None


def ensure_dir(path: str) -> str:
    """确保目录存在，不存在则创建"""
    Path(path).mkdir(parents=True, exist_ok=True)
    return path
