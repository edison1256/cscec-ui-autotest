"""Evidence contracts for PRE black-box regression; no historical pass reuse."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict, deque
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

MANIFEST = Path(__file__).resolve().parents[1] / "test_assets/metering_subscription_260901/blackbox_verified.json"
PRE_HOSTS = {"cloud-pre.cscec.com", "irp-pre.cscec.com"}
AUTH_HOSTS = {"iam-pre.cscec.com", "iam.cscec.com", "iamuat.cscec.com"}
WB_HEADERS = ("资源名称", "资源编码", "服务模式", "资源发布方", "订阅数量", "操作")
CS_HEADERS = ("序号", "租户编码", "租户名称", "资源名称", "资源编码", "服务模式", "资源发布方", "订阅数量", "操作")
ACCOUNT_HEADERS = ("资源名称", "服务模式", "订阅应用", "资源发布方", "生效时间", "截止时间", "可用状态", "总可调用额", "已调用额", "剩余调用额", "操作")
USAGE_HEADERS = ("接口名称", "已调用额", "操作")
ORDER_HEADERS = ("订单ID", "订阅人", "订阅人所在组织", "生效时间", "操作")
DAILY_HEADERS = ("日期", "已调用次数", "已调用额")


class MissingMeteringData(Exception):
    """A declared positive test sample is absent, not a successful test."""


def require_data(condition: bool, reason: str) -> None:
    if not condition:
        raise MissingMeteringData(reason)


def load_manifest(path: Path = MANIFEST) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    ids = [case["case_id"] for case in data["cases"]]
    mapped = [cid for scenario in data["scenarios"] for cid in scenario["case_ids"]]
    assert len(ids) == len(set(ids)) == data["historical_passed"]
    assert len(mapped) == len(set(mapped)) and set(ids) == set(mapped), "覆盖映射重复或遗漏"
    return data


def assert_pre(env: str, *urls: str) -> None:
    if env != "pre":
        raise ValueError("ENV_MISMATCH: black-box suite only supports PRE")
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in PRE_HOSTS or parsed.port not in (None, 443):
            raise ValueError("ENV_MISMATCH: non-PRE business origin rejected")


def allowed_request(url: str, resource_type: str, method: str = "GET") -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"data", "blob", "about"}:
        return True
    if parsed.scheme == "https" and parsed.hostname == "at.alicdn.com" and method == "GET" and re.fullmatch(r"/t/c/font_[A-Za-z0-9_]+\.js", parsed.path):
        return True
    if parsed.path.startswith("/irp-api/"):
        return parsed.scheme == "https" and parsed.hostname in PRE_HOSTS
    if resource_type in {"document", "xhr", "fetch"}:
        return parsed.scheme == "https" and parsed.hostname in PRE_HOSTS | AUTH_HOSTS
    return True


def optional_telemetry(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.hostname == "data-track-api.cscec.com" and parsed.path == "/apipool"


def amount(value: str) -> Decimal:
    text = value.strip().replace(",", "")
    assert re.fullmatch(r"\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text), f"不是无单位数值: {value!r}"
    return Decimal(text)


def account_instance_ids(accounts: list[dict]) -> set[str]:
    values = [str(value) for account in accounts for value in account.get("instanceIds", [account["id"]])]
    assert len(values) == len(set(values)), "不同聚合账户重复关联同一原始权益ID"
    return set(values)


def align_records(rows: list[dict], records: list[dict], fields: dict[str, str], allow_ambiguous=False) -> list[dict]:
    ui_keys = [tuple(str(row[field]) for field in fields) for row in rows]
    raw_keys = [tuple(str(record[key]) for key in fields.values()) for record in records]
    if not allow_ambiguous:
        assert len(raw_keys) == len(set(raw_keys)), "当前响应存在重复业务组合，不能按行号猜测对应关系"
    assert Counter(ui_keys) == Counter(raw_keys), "当前页面业务组合与本轮响应不一致"
    indexed = defaultdict(deque)
    for key, record in zip(raw_keys, records):
        indexed[key].append(record)
    return [indexed[key].popleft() for key in ui_keys]


def assert_children(parent: dict, children: list[dict], raw: dict, accounts: list[dict]) -> None:
    expected = int(parent["订阅数量"])
    assert len(children) == len(accounts) == expected, "订阅数量、UI账户行及响应账户数不一致"
    assert int(raw["subscriptionCount"]) == expected
    assert account_instance_ids(accounts) == {str(i) for i in raw["instanceIds"]}, "不是当前父行账户"
    assert all(c["资源名称"] == parent["资源名称"] and c["服务模式"] == parent["服务模式"] for c in children)
    assert all(a["resourceId"] == raw["resourceId"] and a["serviceMode"] == raw["serviceMode"] for a in accounts)
    assert Counter(c["订阅应用"] for c in children) == Counter(a["applyAppName"] for a in accounts)
    assert Counter((c["订阅应用"], amount(c["已调用额"])) for c in children) == Counter(
        (a["applyAppName"], amount(str(a["usedQuota"]))) for a in accounts
    ), "当前聚合账户的应用/累计用量与页面不一致"


def assert_daily(rows: list[dict], total: int, used: str) -> None:
    require_data(bool(rows), "当前接口没有正向日级计量数据")
    assert len(rows) == total, "日明细未覆盖全部分页"
    dates = [row["日期"] for row in rows]
    assert all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) for date in dates)
    assert dates == sorted(dates, reverse=True) and len(set(dates)) == len(dates), "日明细排序/重复日期异常"
    assert sum((amount(row["已调用额"]) for row in rows), Decimal(0)) == amount(used), "日明细合计不等于接口累计"


def assert_export(blob: bytes, expected: list[dict]) -> dict:
    # Content comparison is separate from the known filename/double-BOM defect.
    parsed = list(csv.reader(io.StringIO(blob.decode("utf-8-sig"))))
    assert parsed, "下载文件为空"
    header = tuple(cell.lstrip("\ufeff").strip() for cell in parsed[0])
    assert header in {DAILY_HEADERS, ("日期", "已调用次数", "已调用额度")}, "CSV列不属于当前日明细"
    actual = sorted((row[0], amount(row[1]), amount(row[2])) for row in parsed[1:])
    desired = sorted((row["日期"], amount(row["已调用次数"]), amount(row["已调用额"])) for row in expected)
    assert actual == desired, "CSV未包含当前接口全部分页数据"
    return {"rows": len(actual), "header": header, "double_bom": blob.startswith(b"\xef\xbb\xbf\xef\xbb\xbf")}


def assert_daily_response(rows: list[dict], data: dict) -> None:
    assert len(rows) == int(data["total"]) == len(data["list"]), "日明细页面/本轮返回总数及记录数不一致"
    ui = [(row["日期"], amount(row["已调用次数"]), amount(row["已调用额"])) for row in rows]
    raw = [(row["usageDate"], amount(str(row["callCount"])), amount(str(row["callQuota"]))) for row in data["list"]]
    assert Counter(ui) == Counter(raw), "日明细日期、次数、额度与本轮返回记录不一致"
