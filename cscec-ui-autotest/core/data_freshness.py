"""列表数据「新鲜度」断言。

起因（2026-11-17 生产走查）：订单中心的近期订单整体不显示，但历史数据仍在，
页面 total 依然 > 0 —— 原有断言 `assert result.records` 只验证「有数据」，
完全无法发现「数据是死的」。

本模块提供统一判据：从接口记录里取时间字段的最大值，换算成距今时长，
超过阈值即判定为「数据不新鲜」，并给出可直接写进缺陷单的描述。

设计取舍：
- **找不到时间字段时明确失败，不静默通过**。字段被改名时断言必须失效，
  否则会退化成又一个「看起来在验、其实什么都没验」的空断言。
- 阈值按调用方传入。不同业务的数据频率差异很大（订单每日，计量 T+1），
  统一阈值必然误报。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping, Sequence

# 常见时间字段名（按优先级）。生产实测：订单列表用 insertDt。
DEFAULT_TIME_FIELDS: tuple[str, ...] = (
    "insertDt",
    "createTime",
    "createdAt",
    "createDt",
    "gmtCreate",
    "orderTime",
    "submitTime",
    "sendTime",
    "updateTime",
    "updateDt",
    "applyTime",
)

_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%d",
)


def parse_time(value: Any) -> datetime | None:
    """把接口里的时间值解析成 datetime（不带时区，按本地时间理解）。

    支持：字符串（多种格式）、毫秒/秒级时间戳。
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (int, float)):
        ts = float(value)
        if ts > 1e11:  # 毫秒
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.isdigit():
            return parse_time(int(text))
        for fmt in _DATETIME_FORMATS:
            try:
                return datetime.strptime(text[:26], fmt)
            except ValueError:
                continue
    return None


@dataclass(frozen=True)
class FreshnessReport:
    """一次新鲜度检查的结果。"""

    label: str
    field: str
    record_count: int
    total: int | None
    latest: datetime | None
    age_hours: float | None
    threshold_days: float

    @property
    def stale(self) -> bool:
        return self.age_hours is not None and self.age_hours > self.threshold_days * 24

    def describe(self) -> str:
        if self.latest is None:
            return f"{self.label}: 记录中未解析到时间字段 {self.field}"
        return (
            f"{self.label}: 共 {self.record_count} 条"
            f"{f'（total={self.total}）' if self.total is not None else ''}，"
            f"最新一条 {self.field}={self.latest:%Y-%m-%d %H:%M:%S}，"
            f"距今 {self.age_hours:.1f} 小时（阈值 {self.threshold_days:g} 天）"
        )


def latest_time_in(
    records: Sequence[Mapping[str, Any]],
    fields: Iterable[str] = DEFAULT_TIME_FIELDS,
) -> tuple[datetime | None, str]:
    """返回记录集中最晚的时间与命中的字段名。"""
    best: datetime | None = None
    best_field = ""
    for record in records:
        if not isinstance(record, Mapping):
            continue
        for field in fields:
            parsed = parse_time(record.get(field))
            if parsed is None:
                continue
            if best is None or parsed > best:
                best = parsed
                best_field = field
            break
    return best, best_field


def check_freshness(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    threshold_days: float = 3.0,
    fields: Iterable[str] = DEFAULT_TIME_FIELDS,
    total: int | None = None,
    now: datetime | None = None,
) -> FreshnessReport:
    """构造新鲜度报告，不做断言（供需要自定义错误信息的调用方使用）。"""
    latest, field = latest_time_in(records, fields)
    current = now or datetime.now()
    age_hours = (current - latest).total_seconds() / 3600 if latest else None
    return FreshnessReport(
        label=label,
        field=field or ",".join(list(fields)[:3]),
        record_count=len(records),
        total=total,
        latest=latest,
        age_hours=age_hours,
        threshold_days=threshold_days,
    )


def assert_fresh(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    threshold_days: float = 3.0,
    fields: Iterable[str] = DEFAULT_TIME_FIELDS,
    total: int | None = None,
    now: datetime | None = None,
) -> FreshnessReport:
    """断言记录集非空且最新一条在阈值内。

    失败信息直接可用于缺陷单，无需再翻日志。
    """
    assert records, f"{label}: 接口未返回任何记录（total={total}）"

    report = check_freshness(
        records,
        label=label,
        threshold_days=threshold_days,
        fields=fields,
        total=total,
        now=now,
    )

    assert report.latest is not None, (
        f"{label}: 记录中没有可解析的时间字段"
        f"（已尝试 {list(fields)[:6]}）。"
        "字段可能被改名，请更新 DEFAULT_TIME_FIELDS 或调用处传入 fields。"
    )
    assert not report.stale, (
        f"{report.describe()} —— 最新数据超过 {threshold_days:g} 天未更新，"
        "疑似数据管道中断（页面仍有历史数据，total 不为 0，仅看非空无法发现）"
    )
    return report


def days_ago(days: float, *, now: datetime | None = None) -> datetime:
    """辅助：构造一个 N 天前的时间（用于单测）。"""
    return (now or datetime.now()) - timedelta(days=days)
