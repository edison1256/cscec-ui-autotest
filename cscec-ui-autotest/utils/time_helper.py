"""
时间相关工具
"""

from datetime import datetime


def get_timestamp(fmt: str = "%Y%m%d_%H%M%S") -> str:
    """获取当前时间戳字符串"""
    return datetime.now().strftime(fmt)


def get_date(offset_days: int = 0, fmt: str = "%Y-%m-%d") -> str:
    """
    获取日期字符串

    Args:
        offset_days: 相对今天的偏移天数（负数为过去）
        fmt: 日期格式
    """
    from datetime import timedelta
    target = datetime.now() + timedelta(days=offset_days)
    return target.strftime(fmt)
