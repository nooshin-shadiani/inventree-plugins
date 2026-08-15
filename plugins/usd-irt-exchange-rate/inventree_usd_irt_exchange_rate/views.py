"""Read-only API views for dual-currency part pricing."""

from typing import ClassVar

from django.http import Http404
from InvenTree.permissions import IsAuthenticatedOrReadScope
from part.models import Part
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import check_user_permission

SOURCE_LABELS = {
    "supplierpricebreak": "Supplier price",
    "partsellpricebreak": "Sale price",
    "partinternalpricebreak": "Internal price",
    "partpricing": "Part pricing",
}

FIELD_LABELS = {
    "price": "Price",
    "override_min": "Minimum override",
    "override_max": "Maximum override",
}


class PartViewPermission(BasePermission):
    """Require permission to view parts."""

    message = "Part view permission is required."

    def has_permission(self, request, view):
        """Return whether the requesting user can view parts."""
        return check_user_permission(request.user, Part, "view")


def _decimal_text(value):
    """Serialize decimal values without binary floating-point loss."""
    return format(value, "f") if value is not None else None


def _source_label(snapshot):
    """Return a concise human-readable source for one snapshot."""
    model_name = snapshot.content_type.model
    source = SOURCE_LABELS.get(model_name, model_name.replace("_", " ").title())
    field = FIELD_LABELS.get(snapshot.price_field, snapshot.price_field)

    if model_name == "partpricing":
        return field

    label = f"{source} #{snapshot.object_id}"
    if snapshot.quantity is not None:
        label = f"{label} at quantity {_decimal_text(snapshot.quantity)}"
    return label


class PartPriceSnapshotView(APIView):
    """Return the latest saved state for every visible part-price source."""

    permission_classes: ClassVar[list] = [
        IsAuthenticatedOrReadScope,
        PartViewPermission,
    ]
    max_results = 200

    def get(self, request, part_id):
        """Return permission-filtered USD/IRT price snapshots for one part."""
        from .models import PriceExchangeSnapshot  # noqa: PLC0415

        if not Part.objects.filter(pk=part_id).exists():
            raise Http404

        snapshots = (
            PriceExchangeSnapshot.objects.filter(part_id=part_id)
            .select_related("content_type")
            .order_by("-captured_at", "-pk")
        )
        seen = set()
        results = []

        for snapshot in snapshots.iterator():
            source_key = (
                snapshot.content_type_id,
                snapshot.object_id,
                snapshot.price_field,
            )
            if source_key in seen:
                continue
            seen.add(source_key)

            model = snapshot.content_type.model_class()
            if model is None or not check_user_permission(request.user, model, "view"):
                continue

            results.append(
                {
                    "id": snapshot.pk,
                    "source": _source_label(snapshot),
                    "price_field": snapshot.price_field,
                    "original_amount": _decimal_text(snapshot.original_amount),
                    "original_currency": snapshot.original_currency,
                    "amount_usd": _decimal_text(snapshot.amount_usd),
                    "amount_irt": _decimal_text(snapshot.amount_irt),
                    "usd_to_irt_rate": _decimal_text(snapshot.usd_to_irt_rate),
                    "conversion_status": snapshot.conversion_status,
                    "source_updated_at": snapshot.source_updated_at,
                    "rate_updated_at": snapshot.rate_updated_at,
                    "captured_at": snapshot.captured_at,
                }
            )

            if len(results) >= self.max_results:
                break

        return Response({"part": part_id, "results": results})
