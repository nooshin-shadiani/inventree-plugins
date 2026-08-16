"""Plugin registration for stock XLSX adjustments."""

from django.urls import path, reverse
from plugin import InvenTreePlugin
from plugin.mixins import UrlsMixin, UserInterfaceMixin
from stock.models import StockItem
from users.permissions import check_user_permission, check_user_role

from . import PLUGIN_VERSION
from .localization import translate_lazy as _


class StockXlsxAdjustmentPlugin(  # pyrefly: ignore [inconsistent-inheritance]
    UrlsMixin, UserInterfaceMixin, InvenTreePlugin
):
    """Import logged stock additions, removals, and counts from XLSX files."""

    NAME = "InvenTreeStockXlsxAdjustment"
    SLUG = "inventree-stock-xlsx-adjustment"
    AUTHOR = "Nooshin Shadiani"
    TITLE = _("Stock XLSX Adjustment")
    DESCRIPTION = _("Preview and apply logged stock adjustments from XLSX files")
    VERSION = PLUGIN_VERSION
    LICENSE = "MIT"
    MIN_VERSION = "1.6.0"
    MAX_VERSION = "1.6.99"
    WEBSITE = "https://github.com/nooshin-shadiani/inventree-plugins/tree/main/plugins/stock-xlsx-adjustment"

    def setup_urls(self):
        """Register the plugin API endpoints."""
        from .views import (  # noqa: PLC0415
            StockAdjustmentApplyView,
            StockAdjustmentPreviewView,
            StockAdjustmentTemplateView,
        )

        return [
            path(
                "preview/",
                StockAdjustmentPreviewView.as_view(),
                name="preview",
            ),
            path("apply/", StockAdjustmentApplyView.as_view(), name="apply"),
            path(
                "template/",
                StockAdjustmentTemplateView.as_view(),
                name="template",
            ),
        ]

    def _ui_feature(self) -> dict:
        """Return the common UI feature definition."""
        return {
            "key": "stock-xlsx-adjustment",
            "title": _("Stock XLSX Adjustment"),
            "description": _("Preview and apply stock movements from an XLSX file"),
            "icon": "ti:file-spreadsheet:outline",
            "source": self.plugin_static_file("stock_adjustment.js"),
            "context": {
                "preview_url": reverse(f"plugin:{self.slug}:preview"),
                "apply_url": reverse(f"plugin:{self.slug}:apply"),
                "template_url": reverse(f"plugin:{self.slug}:template"),
            },
        }

    def _can_access_ui(self, user) -> bool:
        """Return whether the user can open the stock-location plugin panel."""
        return check_user_permission(user, StockItem, "change") and check_user_role(
            user, "stock_location", "view"
        )

    def get_ui_panels(self, request, context, **kwargs):
        """Add the importer panel to the root stock-location page."""
        if not self._can_access_ui(request.user):
            return []

        if context.get("target_model") != "stocklocation" or context.get(
            "target_id"
        ) not in {None, ""}:
            return []

        return [self._ui_feature()]

    def get_ui_navigation_items(self, request, context, **kwargs):
        """Add a direct navigation link for users who can access the panel."""
        if not self._can_access_ui(request.user):
            return []

        feature = self._ui_feature()
        feature["options"] = {"url": "/stock/location/index/stock-xlsx-adjustment"}
        return [feature]
