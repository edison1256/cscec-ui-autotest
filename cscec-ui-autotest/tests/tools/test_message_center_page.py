"""Unread-message API contract regression tests."""

from typing import Any

import pytest

from pages.portal.message_center_page import MessageCenterPage


class FakeRequest:
    """Minimal request used by a synthetic response."""

    def __init__(self, url: str) -> None:
        self.url = url


class FakeResponse:
    """Minimal Playwright response contract without production data."""

    def __init__(self, payload: Any, *, url: str = "", status: int = 200) -> None:
        self.status = status
        self.request = FakeRequest(
            url
            or "https://irp.cscec.com/message/messageReceiver/page?readState=0"
        )
        self._payload = payload

    def json(self) -> Any:
        """Return the synthetic JSON payload."""
        return self._payload


def _record(**overrides: Any) -> dict[str, Any]:
    record = {
        "id": "RECEIVER-1",
        "messageId": "MESSAGE-1",
        "messageTitle": "测试通知",
        "messageContent": "请查看业务详情",
        "senderName": "中建云",
        "sendTime": "2026-09-16 10:00:00",
        "url": "https://cloud.cscec.com/udpweb/portal/index.html#/target?id=1",
        "readState": 0,
    }
    record.update(overrides)
    return record


def _response(
    *,
    code: Any = 0,
    records: Any = None,
    total: Any = "1",
    status: int = 200,
    url: str = "",
) -> FakeResponse:
    if records is None:
        records = [_record()]
    return FakeResponse(
        {"code": code, "data": {"records": records, "total": total}},
        url=url,
        status=status,
    )


def test_message_response_preserves_target_identity() -> None:
    snapshot = MessageCenterPage._parse_message_response(_response())

    assert snapshot.total == 1
    assert snapshot.first_navigable.message_id == "MESSAGE-1"
    assert snapshot.first_navigable.target_url.endswith("#/target?id=1")


def test_empty_unread_messages_are_a_declared_prerequisite_miss() -> None:
    snapshot = MessageCenterPage._parse_message_response(
        _response(records=[], total="0")
    )

    prerequisite = MessageCenterPage.navigable_message_prerequisite(snapshot)
    assert prerequisite.satisfied is False
    assert prerequisite.actual == "records=0, navigable=0"


@pytest.mark.parametrize(
    "response,match",
    [
        (_response(status=500), "HTTP"),
        (_response(code=50000), "业务失败"),
        (_response(code=False), "业务失败"),
        (_response(records={}), "data.records"),
        (_response(total="invalid"), "total"),
        (_response(total=0), "total 小于"),
        (
            _response(
                url="https://irp.cscec.com/message/messageReceiver/page?readState=1"
            ),
            "未读消息",
        ),
    ],
)
def test_message_response_rejects_invalid_contract(
    response: FakeResponse,
    match: str,
) -> None:
    with pytest.raises(AssertionError, match=match):
        MessageCenterPage._parse_message_response(response)


@pytest.mark.parametrize(
    "field",
    ["id", "messageId", "messageTitle", "messageContent", "senderName", "sendTime"],
)
def test_message_record_requires_display_and_identity_fields(field: str) -> None:
    with pytest.raises(AssertionError, match=field):
        MessageCenterPage._parse_message_response(
            _response(records=[_record(**{field: ""})])
        )


def test_message_response_rejects_read_records() -> None:
    with pytest.raises(AssertionError, match="混入已读"):
        MessageCenterPage._parse_message_response(
            _response(records=[_record(readState=1)])
        )
