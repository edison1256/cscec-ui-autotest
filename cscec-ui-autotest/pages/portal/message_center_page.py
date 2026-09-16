"""Console notification popover Page Object for the M3-04 baseline."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Locator, Page, Response, expect

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.interaction_evidence import click_and_expect
from pages.console.console_menu_page import ConsoleMenuPage


@dataclass(frozen=True)
class MessageRecord:
    """Stable identity and navigation fields for one unread message."""

    receiver_id: str
    message_id: str
    title: str
    content: str
    sender_name: str
    send_time: str
    target_url: str
    read_state: int


@dataclass(frozen=True)
class MessageSnapshot:
    """Validated unread-message response captured while opening the bell."""

    records: tuple[MessageRecord, ...]
    total: int

    @property
    def first_navigable(self) -> MessageRecord:
        """Return the first unread message with a business target URL."""
        record = next((item for item in self.records if item.target_url), None)
        assert record is not None, "未读消息中没有可跳转的业务样本"
        return record


class MessageCenterPage(BasePage):
    """Exercise the console bell and an API-backed unread message target."""

    PAGE_NAME = "消息通知"
    LIST_API = re.compile(r"/message/messageReceiver/page[?]")
    TAB_NAMES = ("审批", "任务", "通知")

    def open_console_home(self) -> "MessageCenterPage":
        """Open the real console shell before using its top-bar bell."""
        ConsoleMenuPage(self.page).open_console_home()
        return self

    def open_message_bell(self) -> MessageSnapshot:
        """Open the bell, validate its tabs, and capture unread messages."""
        bell = self.page.get_by_role("img", name="bell", exact=True)
        expect(bell).to_have_count(1)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            bell.click()

        snapshot = self._parse_message_response(captured.value)
        for name in self.TAB_NAMES:
            expect(self.page.get_by_role("tab", name=name, exact=True)).to_be_visible()
        approval_tab = self.page.get_by_role("tab", name="审批", exact=True)
        expect(approval_tab).to_have_attribute("aria-selected", "true")
        panel = self.page.get_by_role("tabpanel", name="审批", exact=True)
        expect(panel).to_be_visible()
        self._assert_panel_matches_snapshot(panel, snapshot)
        return snapshot

    @staticmethod
    def navigable_message_prerequisite(
        snapshot: MessageSnapshot,
    ) -> PrerequisiteResult:
        """Declare whether the bell exposes a message that can be opened."""
        navigable = tuple(record for record in snapshot.records if record.target_url)
        return PrerequisiteResult(
            satisfied=bool(navigable),
            reason="当前账号没有带业务跳转地址的未读消息",
            expected="未读消息接口至少返回 1 条带 url 的记录",
            actual=f"records={len(snapshot.records)}, navigable={len(navigable)}",
        )

    def open_message_target(self, snapshot: MessageSnapshot) -> "MessageCenterPage":
        """Click the exact API-backed unread message and validate its target."""
        record = snapshot.first_navigable
        panel = self.page.get_by_role("tabpanel", name="审批", exact=True)
        item = panel.get_by_text(record.title, exact=True)
        expect(item).to_have_count(1)
        expected = urlparse(record.target_url)

        def target_ready() -> None:
            current = urlparse(self.page.url)
            assert current.netloc.lower() == expected.netloc.lower(), (
                "消息落地域名与接口目标不一致"
            )
            assert current.fragment.partition("?")[0] == expected.fragment.partition("?")[0], (
                "消息落地业务路由与接口目标不一致"
            )
            self.assertions.page_not_blank_or_error()

        click_and_expect(item, target_ready, action_name="打开未读消息业务目标")
        return self

    @classmethod
    def _parse_message_response(cls, response: Response) -> MessageSnapshot:
        """Validate transport, query contract, business code, and records."""
        assert response.status == 200, "未读消息接口 HTTP 状态异常"
        query = response.request.url.split("?", 1)[-1]
        assert "readState=0" in query, "铃铛未请求未读消息"
        payload = response.json()
        assert isinstance(payload, dict), "未读消息接口响应不是对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"未读消息接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, Mapping), "未读消息接口 data 不是对象"
        raw_records = data.get("records")
        assert isinstance(raw_records, list), "未读消息接口 data.records 不是列表"
        records = tuple(cls._parse_record(raw) for raw in raw_records)
        try:
            total = int(data.get("total", len(records)))
        except (TypeError, ValueError) as exc:
            raise AssertionError("未读消息接口 total 不是整数") from exc
        assert total >= len(records), "未读消息 total 小于当前记录数"
        return MessageSnapshot(records=records, total=total)

    @classmethod
    def _parse_record(cls, raw: Any) -> MessageRecord:
        assert isinstance(raw, Mapping), "未读消息包含非对象记录"
        read_state = raw.get("readState")
        assert type(read_state) is int and read_state == 0, "未读消息列表混入已读记录"
        return MessageRecord(
            receiver_id=cls._required_text(raw, "id"),
            message_id=cls._required_text(raw, "messageId"),
            title=cls._required_text(raw, "messageTitle"),
            content=cls._required_text(raw, "messageContent"),
            sender_name=cls._required_text(raw, "senderName"),
            send_time=cls._required_text(raw, "sendTime"),
            target_url=cls._optional_text(raw, "url"),
            read_state=read_state,
        )

    @staticmethod
    def _required_text(raw: Mapping[str, Any], field: str) -> str:
        value = raw.get(field)
        assert value is not None and str(value).strip(), (
            f"未读消息缺少有效字段 {field!r}"
        )
        return str(value).strip()

    @staticmethod
    def _optional_text(raw: Mapping[str, Any], field: str) -> str:
        value = raw.get(field)
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _assert_panel_matches_snapshot(
        panel: Locator,
        snapshot: MessageSnapshot,
    ) -> None:
        if not snapshot.records:
            expect(panel.get_by_text("暂无数据", exact=True)).to_be_visible()
            return
        expect(panel.get_by_text(snapshot.records[0].title, exact=True)).to_be_visible()
