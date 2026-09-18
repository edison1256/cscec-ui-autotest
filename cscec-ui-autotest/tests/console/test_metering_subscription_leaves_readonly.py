"""Batch N tenant-subscription metering leaf coverage."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.metering_statistics_page import (
    SUBSCRIPTION_LEAVES,
    MeteringStatisticsPage,
    MeteringSubscriptionLeaf,
)


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.smoke
@pytest.mark.prod_mandatory
@pytest.mark.regression
@pytest.mark.domain_split
class TestMeteringSubscriptionLeavesReadonly:
    """Validate every tenant-subscription leaf through its real menu path."""

    @pytest.mark.parametrize(
        "leaf",
        SUBSCRIPTION_LEAVES,
        ids=lambda leaf: leaf.case_id,
    )
    def test_metering_subscription_leaf(
        self,
        logged_in_page,
        leaf: MeteringSubscriptionLeaf,
    ) -> None:
        """Require a business-success list and matching first-row detail."""
        health = BrowserHealthMonitor(
            logged_in_page,
            f"{leaf.title}只读探查",
        ).start()
        try:
            MeteringStatisticsPage(logged_in_page).inspect_subscription_leaf(leaf)
        finally:
            health.stop()
        health.assert_healthy()
