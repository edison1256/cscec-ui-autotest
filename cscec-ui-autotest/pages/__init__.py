"""Page Object 层"""

from .portal import LoginPage, PortalHomePage
from .console import ConsoleHomePage
from .ops import ManualInspectionPage
from .doccenter import DocCenterPage
from .dataresources import DataResourcePage

__all__ = [
    "LoginPage",
    "PortalHomePage",
    "ConsoleHomePage",
    "ManualInspectionPage",
    "DocCenterPage",
    "DataResourcePage",
]
