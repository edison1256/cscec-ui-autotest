"""Collect browser and declared business-response failures for one action."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from time import monotonic
from typing import Any

from playwright.sync_api import (
    ConsoleMessage,
    Error,
    Page,
    Request,
    Response,
    TimeoutError as PlaywrightTimeoutError,
)

from config.settings import settings


@dataclass(frozen=True)
class BrowserHealthIssue:
    """A browser-side failure captured while an interaction is running."""

    category: str
    detail: str


@dataclass(frozen=True)
class BusinessResponseRule:
    """Expected business success semantics for one critical JSON endpoint."""

    url_pattern: str
    success_values: tuple[Any, ...] = (0, 200, "0", "200", True)
    code_fields: tuple[str, ...] = ("code", "status", "success")
    required_data_path: str | None = None


@dataclass(frozen=True)
class HealthIgnoreRule:
    """Narrow, reviewable exception for a known browser-health signal."""

    category: str
    detail_pattern: str
    reason: str
    expires_on: date


class BrowserHealthMonitor:
    """Capture runtime, console, and critical HTTP failures for one action."""

    def __init__(
        self,
        page: Page,
        action_name: str,
        *,
        business_rules: tuple[BusinessResponseRule, ...] = (),
        ignore_rules: tuple[HealthIgnoreRule, ...] = (),
    ) -> None:
        self.page = page
        self.context = page.context
        self.action_name = action_name
        self.business_rules = business_rules
        self.ignore_rules = ignore_rules
        self.issues: list[BrowserHealthIssue] = []
        self._started = False
        self._pages: list[Page] = []
        self._business_rule_hits = {
            rule.url_pattern: 0 for rule in self.business_rules
        }

    @classmethod
    def for_case(
        cls,
        page: Page,
        case_id: str,
        action_name: str,
    ) -> "BrowserHealthMonitor":
        """Build a monitor from one machine-readable case contract."""
        from core.execution_contract import CaseContractRegistry

        contract = CaseContractRegistry.load().require(case_id)
        rules = tuple(
            BusinessResponseRule(pattern)
            for pattern in contract.critical_api_patterns
        )
        ignore_rules = tuple(
            HealthIgnoreRule(
                category=str(raw["category"]),
                detail_pattern=str(raw["detail_pattern"]),
                reason=str(raw["reason"]),
                expires_on=date.fromisoformat(str(raw["expires_on"])),
            )
            for raw in contract.ignore_rules
        )
        return cls(
            page,
            action_name,
            business_rules=rules,
            ignore_rules=ignore_rules,
        )

    def start(self) -> "BrowserHealthMonitor":
        """Attach listeners before the target interaction starts."""
        if not self._started:
            self.context.on("page", self._on_new_page)
            for current_page in self.context.pages:
                self._attach_page(current_page)
            self._started = True
        return self

    def stop(self) -> "BrowserHealthMonitor":
        """Detach listeners while preserving all captured issues."""
        if self._started:
            self._wait_for_required_business_responses()
            self.context.remove_listener("page", self._on_new_page)
            for current_page in tuple(self._pages):
                self._detach_page(current_page)
            self._started = False
        return self

    def assert_healthy(self) -> "BrowserHealthMonitor":
        """Fail with compact evidence when the monitored action was unhealthy."""
        for pattern, hit_count in self._business_rule_hits.items():
            if hit_count == 0:
                self._record(
                    "business_response_missing",
                    f"关键接口未触发: pattern={pattern}",
                )
        if self.issues:
            evidence = "\n".join(
                f"- {issue.category}: {issue.detail[:1200]}" for issue in self.issues[:10]
            )
            raise AssertionError(f"{self.action_name} 触发浏览器端异常:\n{evidence}")
        return self

    def _on_console(self, message: ConsoleMessage) -> None:
        if message.type == "error":
            location = message.location
            source_url = location.get("url", "") if location else ""
            detail = f"{message.text} @ {source_url}" if source_url else message.text
            self._record("console.error", detail)

    def _on_page_error(self, error: Error) -> None:
        self._record("pageerror", str(error))

    def _on_response(self, response: Response) -> None:
        if response.status == 404 or response.status >= 500:
            self._record("http", f"{response.status} {response.url}")

        for rule in self.business_rules:
            if re.search(rule.url_pattern, response.url):
                self._business_rule_hits[rule.url_pattern] += 1
                self._inspect_business_response(response, rule)

    def _on_request_failed(self, request: Request) -> None:
        failure = request.failure or "unknown failure"
        self._record("requestfailed", f"{request.method} {request.url}: {failure}")

    def _on_new_page(self, page: Page) -> None:
        self._attach_page(page)

    def _attach_page(self, page: Page) -> None:
        if page in self._pages:
            return
        page.on("console", self._on_console)
        page.on("pageerror", self._on_page_error)
        page.on("response", self._on_response)
        page.on("requestfailed", self._on_request_failed)
        self._pages.append(page)

    def _detach_page(self, page: Page) -> None:
        page.remove_listener("console", self._on_console)
        page.remove_listener("pageerror", self._on_page_error)
        page.remove_listener("response", self._on_response)
        page.remove_listener("requestfailed", self._on_request_failed)
        self._pages.remove(page)

    def _inspect_business_response(
        self,
        response: Response,
        rule: BusinessResponseRule,
    ) -> None:
        if not 200 <= response.status < 300:
            self._record("business_response", f"HTTP {response.status} {response.url}")
            return

        resource_type = response.request.resource_type
        content_type = (response.header_value("content-type") or "").lower()
        if resource_type not in {"xhr", "fetch"} or "json" not in content_type:
            self._record(
                "business_response",
                f"关键接口未返回 JSON XHR/Fetch: {resource_type} {content_type} {response.url}",
            )
            return

        try:
            payload = response.json()
        except Exception as exc:
            self._record(
                "business_response",
                f"关键接口 JSON 解析失败: {response.url}: {exc}",
            )
            return

        code_field, code_value = self._first_payload_value(payload, rule.code_fields)
        if code_field is None:
            self._record(
                "business_response",
                f"关键接口缺少业务状态字段 {rule.code_fields}: {response.url}",
            )
            return
        if not self._is_success_value(code_value, rule.success_values):
            message = self._payload_message(payload)
            self._record(
                "business_response",
                f"{response.url}: {code_field}={code_value!r}, message={message!r}",
            )
            return

        if rule.required_data_path and self._dotted_value(payload, rule.required_data_path) is None:
            self._record(
                "business_response",
                f"{response.url}: 缺少有效数据路径 {rule.required_data_path}",
            )

    def _record(self, category: str, detail: str) -> None:
        for rule in self.ignore_rules:
            if rule.category != category or not re.search(rule.detail_pattern, detail):
                continue
            if rule.expires_on < date.today():
                self.issues.append(
                    BrowserHealthIssue(
                        "expired_ignore",
                        f"{category}: {detail}; expired={rule.expires_on}; reason={rule.reason}",
                    )
                )
            return
        self.issues.append(BrowserHealthIssue(category, detail))

    def _wait_for_required_business_responses(self) -> None:
        """Wait for declared responses using Playwright events, not fixed delays."""
        deadline = monotonic() + settings.ACTION_TIMEOUT / 1000
        for pattern, hit_count in tuple(self._business_rule_hits.items()):
            if hit_count > 0 or self.page.is_closed():
                continue
            remaining_ms = max(1, int((deadline - monotonic()) * 1000))
            if remaining_ms <= 1:
                return
            try:
                self.page.wait_for_event(
                    "response",
                    predicate=lambda response, target=pattern: bool(
                        re.search(target, response.url)
                    ),
                    timeout=remaining_ms,
                )
            except PlaywrightTimeoutError:
                return

    @staticmethod
    def _is_success_value(value: Any, allowed: tuple[Any, ...]) -> bool:
        return any(type(value) is type(candidate) and value == candidate for candidate in allowed)

    @staticmethod
    def _first_payload_value(
        payload: Any,
        fields: tuple[str, ...],
    ) -> tuple[str | None, Any]:
        if not isinstance(payload, dict):
            return None, None
        for field in fields:
            if field in payload:
                return field, payload[field]
        return None, None

    @staticmethod
    def _payload_message(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        for field in ("message", "msg", "error", "errorMessage"):
            if field in payload:
                return str(payload[field])
        return ""

    @staticmethod
    def _dotted_value(payload: Any, path: str) -> Any:
        value = payload
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                return None
            value = value[part]
        return value
