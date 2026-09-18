"""Batch I subscription-service sidebar coverage."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.subscription_service_page import (
    PROCESS_LEAVES,
    SUBSCRIPTION_LEAVES,
    SubscriptionLeaf,
    SubscriptionServicePage,
)


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
]


@pytest.mark.smoke
@pytest.mark.prod_mandatory
class TestSubscriptionServiceSidebarReadonly:
    """Follow each authorized subscription leaf from the real sidebar."""

    @pytest.mark.parametrize(
        "leaf",
        [pytest.param(leaf, id=leaf.case_id) for leaf in SUBSCRIPTION_LEAVES],
    )
    def test_subscription_sidebar_leaf(
        self,
        logged_in_page,
        leaf: SubscriptionLeaf,
    ) -> None:
        """Require API-backed list identity and detail where the UI exposes it."""
        health = BrowserHealthMonitor(
            logged_in_page,
            f"订阅服务侧栏 {leaf.title}",
        ).start()
        try:
            SubscriptionServicePage(logged_in_page).inspect_leaf(leaf)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.parametrize(
        "leaf",
        [pytest.param(leaf, id=f"{leaf.case_id}-PROCESS") for leaf in PROCESS_LEAVES],
    )
    def test_subscription_process_history(
        self,
        logged_in_page,
        leaf: SubscriptionLeaf,
    ) -> None:
        """Inspect transfer history and process diagram without changing state."""
        health = BrowserHealthMonitor(
            logged_in_page,
            f"订阅服务流程详情 {leaf.title}",
        ).start()
        try:
            SubscriptionServicePage(logged_in_page).inspect_process_history(leaf)
        finally:
            health.stop()
        health.assert_healthy()
