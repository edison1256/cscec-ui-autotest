"""Environment and evidence contracts for metering black-box regression."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter, defaultdict, deque
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlparse

MANIFEST = Path(__file__).resolve().parents[1] / "test_assets/metering_subscription_260901/blackbox_verified.json"
PRE_HOSTS = {"cloud-pre.cscec.com", "irp-pre.cscec.com"}
BUSINESS_HOSTS = {"pre": PRE_HOSTS, "prod": {"cloud.cscec.com", "irp.cscec.com"}}
AUTH_HOSTS = {"iam-pre.cscec.com", "iam.cscec.com", "iamuat.cscec.com"}
READ_POST_ACTIONS = {
    "aggregate", "aggregateForConsole", "list", "listByIds", "listSummary",
    "findByOrderIds", "detail", "query", "page", "get", "getInfo",
    "getUserInfo", "getMenu", "getMenus", "getTree", "tree", "count",
    "findAll", "findById", "findList", "pageList", "queryList", "queryPage",
}
METERING_READ_ACTIONS = {
    "quota-instance": {"aggregate", "aggregateForConsole", "list", "listByIds"},
    "quota-instance-order": {"findByOrderIds"},
    "quota-daily": {"listSummary", "detail"},
}
BOOTSTRAP_READ_POST_PATHS = {
    "/irp-api/irp-portal-public/banner/listForPortalNoAuth",
    "/portal/loginConfig/getLoginConfigForLogin",
    "/portal/loginConfig/getCheckUrl",
    "/integration-portal/subSystem/v2/getSubSystemApplicationInfo",
    # Read-only homepage consumers verified against PRE assets; see production guide.
    "/integration-portal/individuation/getSystemName",
    "/irp-api/irp-portal-public/knowledge-center/queryNoAuth",
    "/irp-api/irp-portal-console/knowledge-center/queryNoAuth",
    "/irp-api/irp-portal-workbench/developer-community-post-portal/postPortalWorkbench",
    # The actual control-mode consumer reads AD_CONSOLE and community lists only.
    "/irp-api/irp-portal-console/developer-community-post-portal/postPortalConsole",
    # User confirmed this exact endpoint has no data writes on 2026-10-15.
    "/irp-api/irp-portal-console/link/checkNoAuth",
    "/basedata/api/tenant/getUserJobByUserCodeAndDataSource",
    "/irp-api/irp-portal-public/tenant/viewBatch",
    "/engine/metadata/getMenuPageName",
    "/auth/resolve/getNoGrantButtons",
}
AUTHENTICATION_POST_PATHS = {
    "/portal/login/v2/loginByIamCode", "/portal/login/checkToken",
    "/portal/login/changeOrgByNo",
}
WB_HEADERS = ("资源名称", "资源编码", "服务模式", "资源发布方", "订阅数量", "操作")
CS_HEADERS = ("序号", "租户编码", "租户名称", "资源名称", "资源编码", "服务模式", "资源发布方", "订阅数量", "操作")
ACCOUNT_HEADERS = ("资源名称", "服务模式", "订阅应用", "资源发布方", "生效时间", "截止时间", "可用状态", "总可调用额", "已调用额", "剩余调用额", "操作")
USAGE_HEADERS = ("接口名称", "已调用额", "操作")
ORDER_HEADERS = ("订单ID", "订阅人", "订阅人所在租户", "生效时间", "操作")
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


def assert_metering_environment(env: str, *urls: str) -> None:
    if env not in BUSINESS_HOSTS:
        raise ValueError("ENV_MISMATCH: metering supports PRE or explicitly selected PROD")
    for url in urls:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname not in BUSINESS_HOSTS[env]
                or parsed.port not in (None, 443) or parsed.username or parsed.password):
            raise ValueError(f"ENV_MISMATCH: business origin does not belong to {env}")


def readonly_business_request(path: str, method: str) -> bool:
    parts = unquote(path).rstrip("/").split("/")
    if any(part in {".", ".."} or "\\" in part for part in parts):
        return False
    action = parts[-1]
    for namespace, actions in METERING_READ_ACTIONS.items():
        if namespace in parts:
            return (parts.index(namespace) == len(parts) - 2 and action in actions
                    and method in {"GET", "POST", "HEAD", "OPTIONS"})
    if re.search(r"(?:export|downloadTask|createTask)", path, re.I):
        return False
    if method == "POST" and path in BOOTSTRAP_READ_POST_PATHS | AUTHENTICATION_POST_PATHS:
        return True
    if method in {"GET", "HEAD", "OPTIONS"}:
        return not re.search(r"/(?:save|update|delete|remove|create|submit|approve|buy)(?:/|$)", path, re.I)
    return method == "POST" and action in READ_POST_ACTIONS


def allowed_request(url: str, resource_type: str, method: str = "GET", env: str = "pre", readonly: bool = False) -> bool:
    if env not in BUSINESS_HOSTS:
        return False
    parsed = urlparse(url)
    if (env == "prod" or readonly) and parsed.hostname in BUSINESS_HOSTS[env]:
        if not readonly_business_request(parsed.path, method):
            return False
    if parsed.scheme in {"data", "blob", "about"}:
        return True
    if parsed.scheme == "https" and parsed.hostname == "at.alicdn.com" and method == "GET" and re.fullmatch(r"/t/c/font_[A-Za-z0-9_]+\.js", parsed.path):
        return True
    if parsed.path.startswith("/irp-api/"):
        return (parsed.scheme == "https" and parsed.port in (None, 443)
                and parsed.hostname in BUSINESS_HOSTS[env]
                and (not (env == "prod" or readonly) or readonly_business_request(parsed.path, method)))
    if resource_type in {"document", "xhr", "fetch"}:
        if parsed.scheme != "https" or parsed.port not in (None, 443):
            return False
        if parsed.hostname in AUTH_HOSTS:
            return True
        return (parsed.hostname in BUSINESS_HOSTS[env]
                and (not (env == "prod" or readonly) or readonly_business_request(parsed.path, method)))
    return True


def optional_telemetry(url: str, env: str | None = None) -> bool:
    parsed = urlparse(url)
    return ((parsed.hostname == "data-track-api.cscec.com" and parsed.path == "/apipool")
            or (parsed.scheme == "https" and parsed.port in (None, 443)
                and parsed.hostname in BUSINESS_HOSTS.get(env, set())
                and parsed.path in {"/udp-monitor/logging", "/integration-portal/recentUseMenu/useMenu"}))


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
