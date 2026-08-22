"""Read-only API views for dual-currency part pricing."""

from typing import ClassVar

from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from InvenTree.permissions import IsAuthenticatedOrReadScope
from order.models import PurchaseOrder, PurchaseOrderLineItem
from part.models import Part
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from users.permissions import check_user_permission

from .localization import translate, translate_lazy

SOURCE_LABELS = {
    "supplierpricebreak": "Supplier price",
    "purchaseorderlineitem": "Purchase order line",
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

    message = translate_lazy("Part view permission is required.")

    def has_permission(self, request, view):
        """Return whether the requesting user can view parts."""
        return check_user_permission(request.user, Part, "view")


class PurchaseOrderViewPermission(BasePermission):
    """Require permission to view purchase orders and their line items."""

    message = translate_lazy("Purchase order view permission is required.")

    def has_permission(self, request, view):
        """Return whether the requesting user can view purchase-order pricing."""
        return check_user_permission(
            request.user, PurchaseOrder, "view"
        ) and check_user_permission(request.user, PurchaseOrderLineItem, "view")


def _decimal_text(value):
    """Serialize decimal values without binary floating-point loss."""
    return format(value, "f") if value is not None else None


def _source_label(snapshot):
    """Return a concise human-readable source for one snapshot."""
    model_name = snapshot.content_type.model
    source = translate(
        SOURCE_LABELS.get(model_name, model_name.replace("_", " ").title())
    )
    field = translate(FIELD_LABELS.get(snapshot.price_field, snapshot.price_field))

    if model_name == "partpricing":
        return field

    label = f"{source} #{snapshot.object_id}"
    if snapshot.quantity is not None:
        label = translate("{label} at quantity {quantity}").format(
            label=label, quantity=_decimal_text(snapshot.quantity)
        )
    return label


def _snapshot_result(snapshot):
    """Serialize one immutable price snapshot without float conversion."""
    return {
        "id": snapshot.pk,
        "source": _source_label(snapshot),
        "price_field": snapshot.price_field,
        "quantity": _decimal_text(snapshot.quantity),
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

            results.append(_snapshot_result(snapshot))

            if len(results) >= self.max_results:
                break

        return Response({"part": part_id, "results": results})


class PurchaseOrderPriceSnapshotView(APIView):
    """Return the latest frozen unit price for each purchase-order line."""

    permission_classes: ClassVar[list] = [
        IsAuthenticatedOrReadScope,
        PurchaseOrderViewPermission,
    ]

    def get(self, request, order_id):
        """Return immutable USD/IRT prices scoped to one purchase order."""
        from .models import PriceExchangeSnapshot  # noqa: PLC0415

        try:
            order = PurchaseOrder.objects.get(pk=order_id)
        except PurchaseOrder.DoesNotExist as exc:
            raise Http404 from exc

        lines = {
            line.pk: line
            for line in order.lines.select_related("part", "part__part").all()
        }
        line_content_type = ContentType.objects.get_for_model(PurchaseOrderLineItem)
        snapshots = (
            PriceExchangeSnapshot.objects.filter(
                content_type=line_content_type,
                object_id__in=lines,
                price_field="purchase_price",
            )
            .select_related("content_type")
            .order_by("-captured_at", "-pk")
        )
        seen = set()
        results = []

        for snapshot in snapshots.iterator():
            if snapshot.object_id in seen:
                continue
            seen.add(snapshot.object_id)

            line = lines[snapshot.object_id]
            part = line.get_base_part()
            quantity = snapshot.quantity
            result = _snapshot_result(snapshot)
            result.update(
                {
                    "line_item": line.pk,
                    "part": part.pk if part else None,
                    "part_name": part.name if part else None,
                    "supplier_part": line.part_id,
                    "supplier_sku": line.part.SKU if line.part else None,
                    "total_original_amount": _decimal_text(
                        snapshot.original_amount * quantity
                        if quantity is not None
                        else None
                    ),
                    "total_amount_usd": _decimal_text(
                        snapshot.amount_usd * quantity
                        if snapshot.amount_usd is not None and quantity is not None
                        else None
                    ),
                    "total_amount_irt": _decimal_text(
                        snapshot.amount_irt * quantity
                        if snapshot.amount_irt is not None and quantity is not None
                        else None
                    ),
                }
            )
            results.append(result)

        return Response({"purchase_order": order_id, "results": results})
