"""Read-only coverage for subscription-service sidebar leaves."""

from __future__ import annotations

from dataclasses import dataclass

from playwright.sync_api import Page, expect

from core.interaction_evidence import require_business_identity
from pages.console.console_menu_page import ConsoleMenuPage
from pages.console.console_workbench_page import ConsoleWorkbenchPage


@dataclass(frozen=True)
class SubscriptionLeaf:
    """One subscription-service menu leaf and its evidence contract."""

    case_id: str
    title: str
    route_pattern: str
    list_api_pattern: str
    required_labels: tuple[str, ...] = ()
    detail_api_pattern: str | None = None
    visible_identity_field: str | None = None

    @property
    def supports_detail(self) -> bool:
        """Return whether the current production page exposes a detail action."""
        return bool(self.required_labels)


ORDER_DETAIL_LABELS = (
    "详情",
    "基础信息",
    "订单编码",
    "资源信息",
    "审批进度",
)


SUBSCRIPTION_LEAVES = (
    SubscriptionLeaf(
        case_id="SUBSCRIPTION-APP-001",
        title="应用列表",
        route_pattern=r"[#/]subscription/app/appInfo(?:[/?]|$)",
        list_api_pattern="/console/rsc/app/apply/history/list",
        required_labels=ORDER_DETAIL_LABELS,
        detail_api_pattern=r"/order/orderDetail[?]",
    ),
    SubscriptionLeaf(
        case_id="SUBSCRIPTION-CLOUD-001",
        title="云产品列表",
        route_pattern=r"[#/]subscription/cloud(?:[/?]|$)",
        list_api_pattern="/cloud/applyList",
        required_labels=ORDER_DETAIL_LABELS,
        detail_api_pattern=r"/order/orderDetail[?]",
    ),
    SubscriptionLeaf(
        case_id="SUBSCRIPTION-API-001",
        title="API列表",
        route_pattern=r"[#/]subscription/apiResource(?:[/?]|$)",
        list_api_pattern="/console/rsc/api/apply/history/list",
    ),
    SubscriptionLeaf(
        case_id="SUBSCRIPTION-COMPONENT-001",
        title="组件列表",
        route_pattern=r"[#/]subscription/comp(?:[/?]|$)",
        list_api_pattern="/console/rsc/compt/apply/history/list",
        required_labels=("详情", "订单ID"),
        visible_identity_field="orderId",
    ),
    SubscriptionLeaf(
        case_id="SUBSCRIPTION-DATA-ASSET-001",
        title="数据资产列表",
        route_pattern=r"[#/]subscription/dataAssets(?:[/?]|$)",
        list_api_pattern="/workbench/rsc/data/apply/history/list",
        required_labels=ORDER_DETAIL_LABELS + ("资产列表",),
        detail_api_pattern=r"/order/orderDetail[?]",
        visible_identity_field="rscName",
    ),
)

PROCESS_LEAVES = tuple(
    leaf
    for leaf in SUBSCRIPTION_LEAVES
    if leaf.title in {"应用列表", "云产品列表", "数据资产列表"}
)


class SubscriptionServicePage(ConsoleMenuPage):
    """Inspect subscription lists through their authorized sidebar paths."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._detail_reader = ConsoleWorkbenchPage(page)

    def inspect_leaf(self, leaf: SubscriptionLeaf) -> "SubscriptionServicePage":
        """Bind a sidebar leaf to its list record and optional read-only detail."""
        self.open_console_home()
        prerequisite = self.menu_path_prerequisite("订阅服务", leaf.title)
        assert prerequisite.satisfied, prerequisite.reason
        response = self.open_menu_path(
            "订阅服务",
            leaf.title,
            response_pattern=leaf.list_api_pattern,
            route_pattern=leaf.route_pattern,
        )
        snapshot = self._detail_reader._parse_list_response(response, leaf.title)
        assert snapshot.records, f"{leaf.title}列表接口没有可核验记录"

        record = snapshot.first_record
        record_id = self._detail_reader._required_record_text(record, "id")
        resource_name = self._detail_reader._record_resource_name(record)
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(record_id, exact=True)
        ).first
        require_business_identity(row, record_id, f"{leaf.title}首条记录")
        require_business_identity(row, resource_name, f"{leaf.title}首条记录")
        expect(self.page.get_by_role("button", name="查 询", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="重 置", exact=True)).to_be_visible()

        if leaf.supports_detail:
            self._detail_reader.open_first_detail(
                snapshot,
                row_identity_field="id",
                detail_identity_field="orderId",
                required_labels=leaf.required_labels,
                detail_api_pattern=leaf.detail_api_pattern,
                visible_identity_field=leaf.visible_identity_field,
            )
        else:
            expect(row.get_by_role("button", name="详情", exact=True)).to_have_count(0)
        return self

    def inspect_process_history(
        self,
        leaf: SubscriptionLeaf,
    ) -> "SubscriptionServicePage":
        """Verify transfer history and process diagram in a subscription detail."""
        assert leaf in PROCESS_LEAVES, f"{leaf.title}未登记流程详情覆盖"
        self.inspect_leaf(leaf)
        detail = self.page.locator(
            ".ant-drawer:visible, .ant-modal:visible, "
            ".el-dialog:visible, .el-drawer:visible"
        ).first

        transfer_tab = detail.get_by_role("tab", name="流转明细", exact=True)
        transfer_tab.click()
        expect(transfer_tab).to_have_attribute("aria-selected", "true")
        transfer_panel = detail.get_by_role(
            "tabpanel",
            name="流转明细",
            exact=True,
        )
        expect(transfer_panel.get_by_text("发起人：", exact=True)).to_be_visible()
        expect(transfer_panel.get_by_text("流转状态：", exact=True).first).to_be_visible()

        detail.get_by_role("button", name="流程图", exact=True).click()
        process_dialog = self.page.locator(".ant-modal:visible").filter(
            has_text="查看流程图"
        ).last
        expect(process_dialog).to_be_visible()
        for status in ("已完成", "进行中", "未办理"):
            expect(process_dialog.get_by_text(status, exact=True)).to_be_visible()
        close = process_dialog.locator(
            ".ant-modal-close, .el-dialog__headerbtn, [aria-label='close']"
        ).first
        close.click()
        expect(
            self.page.locator(".ant-modal:visible").filter(has_text="查看流程图")
        ).to_have_count(0)
        return self
