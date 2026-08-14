"""HTTP endpoints for stock XLSX adjustment preview and application."""

from typing import ClassVar

from django.http import HttpResponse
from InvenTree.permissions import InvenTreeTokenMatchesOASRequirements, map_scope
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from stock.models import StockItem
from users.permissions import check_user_permission

from .operations import apply_adjustments, preview_adjustments, template_workbook


class StockItemChangePermission(BasePermission):
    """Require InvenTree's stock-item change permission."""

    message = "Stock item change permission is required."

    def has_permission(self, request, view):
        """Return whether the requesting user can change stock items."""
        return check_user_permission(request.user, StockItem, "change")


class StockChangeScopePermission(InvenTreeTokenMatchesOASRequirements):
    """Require the stock-change scope when OAuth authentication is used."""

    def has_permission(self, request, view):
        """Allow non-OAuth authentication or validate the OAuth token scope."""
        if self.is_oauth2ed(request):
            return self.check_oauth2_authentication(request, view)

        return True


class StockAdjustmentView(APIView):
    """Shared configuration for stock-adjustment endpoints."""

    permission_classes: ClassVar[list] = [
        IsAuthenticated,
        StockItemChangePermission,
        StockChangeScopePermission,
    ]
    required_alternate_scopes: ClassVar[dict] = map_scope(
        roles=["stock"], override_all_actions="change"
    )


class StockAdjustmentPreviewView(StockAdjustmentView):
    """Validate an uploaded workbook without changing stock."""

    parser_classes: ClassVar[list] = [MultiPartParser, FormParser]

    def post(self, request):
        """Return row errors and projected quantities for an XLSX upload."""
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": ["An XLSX file is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(preview_adjustments(upload))


class StockAdjustmentApplyView(StockAdjustmentView):
    """Atomically apply a fully valid workbook."""

    parser_classes: ClassVar[list] = [MultiPartParser, FormParser]

    def post(self, request):
        """Apply all rows or return validation errors without changing stock."""
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"file": ["An XLSX file is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = apply_adjustments(upload, request.user)
        response_status = (
            status.HTTP_200_OK if result["applied"] else status.HTTP_400_BAD_REQUEST
        )
        return Response(result, status=response_status)


class StockAdjustmentTemplateView(StockAdjustmentView):
    """Download the supported XLSX input template."""

    def get(self, request):
        """Return an example workbook."""
        response = HttpResponse(
            template_workbook(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            'attachment; filename="inventree-stock-adjustments.xlsx"'
        )
        return response
