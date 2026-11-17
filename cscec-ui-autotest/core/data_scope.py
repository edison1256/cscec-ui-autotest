"""列表数据的「归属范围」断言（越权检测）。

起因（2026-11-17 用户走查）：个人工作台下「订单中心 → 被订阅的订单」返回了
**全量**数据而不是当前账户的订单。生产实测该接口：

    POST /irp-api/irp-portal-console/workbench/rsc/app/apply/history/list
    total=828，tenantNo 去重 = 26 个不同租户

而当前账号 tenantNo = ZH_01_0000。页面照样正常渲染、有数据、分页正常，
现有断言（非空 / 页面可达）完全发现不了。

与前两个能力的分工：
- `data_freshness` 判「数据是不是新的」
- 本模块判「数据是不是本该给我的」

判据：返回记录里表示归属的字段，其取值集合必须落在允许范围内。
超出即为越权，失败信息列出具体越权的租户及其条数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

# 常见归属字段（按优先级）。生产实测：被订阅订单列表用 tenantNo。
DEFAULT_SCOPE_FIELDS: tuple[str, ...] = (
    "tenantNo",
    "tenantCode",
    "tenantId",
    "subscriberTenantNo",
    "ownerTenantNo",
    "orgCode",
    # 「我的订单」这类列表没有 tenantNo，只有创建人账号（生产实测 /order/page
    # 返回 creator=20431644 形式），用于按「本人」维度判定范围。
    "creator",
    "creatorId",
    "userNo",
    "applyUserNo",
)


@dataclass(frozen=True)
class ScopeReport:
    """一次归属范围检查的结果。"""

    label: str
    field: str
    expected: tuple[str, ...]
    counts: Mapping[str, int]
    record_count: int
    total: int | None = None

    @property
    def out_of_scope(self) -> dict[str, int]:
        """不在允许范围内的取值及其条数。"""
        allowed = set(self.expected)
        return {k: v for k, v in self.counts.items() if k not in allowed}

    @property
    def leaked(self) -> bool:
        return bool(self.out_of_scope)

    def describe(self) -> str:
        base = (
            f"{self.label}: {self.record_count} 条"
            f"{f'（total={self.total}）' if self.total is not None else ''}，"
            f"归属字段 {self.field or '(未识别)'} 去重 {len(self.counts)} 个，"
            f"允许范围 {list(self.expected)}"
        )
        if self.leaked:
            top = sorted(self.out_of_scope.items(), key=lambda kv: -kv[1])[:6]
            base += f"；越权取值 {len(self.out_of_scope)} 个，示例 {top}"
        return base


def _pick_field(
    records: Sequence[Mapping[str, Any]],
    fields: Iterable[str],
) -> tuple[str, dict[str, int]]:
    """选出第一个有值的归属字段，并统计其取值分布。"""
    for candidate in fields:
        counts: dict[str, int] = {}
        for record in records:
            if not isinstance(record, Mapping):
                continue
            value = record.get(candidate)
            if value is None:
                continue
            key = str(value).strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
        if counts:
            return candidate, counts
    return "", {}


def check_scope(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    expected: str | Iterable[str],
    fields: Iterable[str] = DEFAULT_SCOPE_FIELDS,
    total: int | None = None,
) -> ScopeReport:
    """构造归属范围报告（不做断言）。"""
    expected_tuple = (expected,) if isinstance(expected, str) else tuple(expected)
    used_field, counts = _pick_field(records, fields)
    return ScopeReport(
        label=label,
        # 不做 fallback：字段识别失败时必须为空，否则「找不到归属字段」的
        # 断言永远成立，越权检查会静默退化成永远通过。
        field=used_field,
        expected=expected_tuple,
        counts=counts,
        record_count=len(records),
        total=total,
    )


def assert_scope(
    records: Sequence[Mapping[str, Any]],
    *,
    label: str,
    expected: str | Iterable[str],
    fields: Iterable[str] = DEFAULT_SCOPE_FIELDS,
    total: int | None = None,
) -> ScopeReport:
    """断言返回记录的数据归属没有越出允许范围。

    失败信息直接可用于缺陷单：列出越权的租户编码与条数。
    """
    assert records, f"{label}: 接口未返回任何记录（total={total}）"

    report = check_scope(
        records, label=label, expected=expected, fields=fields, total=total
    )

    assert report.field, (
        f"{label}: 记录中找不到任何归属字段"
        f"（已尝试 {list(fields)[:5]}）。"
        "无法判断数据是否越权；字段可能被改名，请更新 DEFAULT_SCOPE_FIELDS。"
    )
    assert not report.leaked, (
        f"{report.describe()} —— 返回了当前账户**不应看到**的数据，疑似数据范围未收口"
    )
    return report


def tenant_signature(login_info: Mapping[str, Any] | None) -> tuple[str, ...]:
    """从登录态解析当前账号的租户归属，作为期望范围。

    生产 `__login_info__` 里 `tenantNo=ZH_01_0000` 表示平台租户；
    个人视角账号则是对应个人租户编码。
    """
    if not isinstance(login_info, Mapping):
        return ()
    values = []
    # orgNo 才是用户实际归属的组织/空间标识（生产实测
    # orgNo=ZH_01_0000_0000_000X / orgName=个人工作台）；
    # tenantNo=ZH_01_0000 是**根节点**「中建云」，按设计不应存在用户，
    # 直接拿它当期望范围会得出错误结论（2026-11-17 用户更正）。
    for key in ("orgNo", "orgCode", "tenantNo", "tenantCode"):
        value = login_info.get(key)
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
    return tuple(dict.fromkeys(values))


def looks_like_platform_admin(login_info: Mapping[str, Any] | None) -> bool:
    """判断当前身份是否平台管理侧。

    平台账号可见多租户数据属预期行为，不能据此判越权；
    这类环境应改用个人视角账号跑归属用例，否则只能 N/A。
    """
    if not isinstance(login_info, Mapping):
        return False
    org = str(login_info.get("orgName") or "")
    tenant = str(login_info.get("tenantName") or "")
    markers = ("控制台", "平台", "运营", "管理")
    return any(m in org for m in markers) or "中建云" == tenant
