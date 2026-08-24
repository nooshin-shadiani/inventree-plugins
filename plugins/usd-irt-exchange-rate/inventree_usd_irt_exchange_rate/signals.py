"""Capture exchange-rate snapshots synchronously when part prices are saved."""

import logging
from decimal import Decimal

from company.models import SupplierPriceBreak
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.db import DatabaseError, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from djmoney.contrib.exchange.models import Rate
from InvenTree.ready import canAppAccessDatabase, isRunningMigrations
from order.models import PurchaseOrderLineItem
from part.models import PartInternalPriceBreak, PartPricing, PartSellPriceBreak
from stock.models import StockItem

from .models import PriceExchangeSnapshot

logger = logging.getLogger("inventree")


def _applied_usd_to_irt_rate():
    """Return the USD-based rate currently persisted by InvenTree."""
    rate = (
        Rate.objects.select_related("backend")
        .filter(
            backend_id="InvenTreeExchange",
            backend__base_currency="USD",
            currency="IRT",
        )
        .first()
    )

    if rate is None or not rate.value.is_finite() or rate.value <= 0:
        return None, None

    return rate.value, rate.backend.last_update


def _can_capture(*, raw):
    """Return whether price-save signals can safely access plugin data."""
    if (
        raw
        or isRunningMigrations()
        or not apps.is_installed("inventree_usd_irt_exchange_rate")
    ):
        return False

    return canAppAccessDatabase(
        allow_test=True,
        allow_plugins=True,
        allow_shell=True,
    )


def _capture_price(
    instance,
    *,
    price_field,
    part_id,
    quantity=None,
    compare_quantity=True,
):
    """Append a snapshot unless this exact price state is already current."""
    price = getattr(instance, price_field, None)

    if price is None:
        return

    content_type = ContentType.objects.get_for_model(instance)
    original_amount = Decimal(price.amount)
    original_currency = str(price.currency)

    latest = (
        PriceExchangeSnapshot.objects.filter(
            content_type=content_type,
            object_id=instance.pk,
            price_field=price_field,
        )
        .order_by("-captured_at", "-pk")
        .first()
    )

    if (
        latest is not None
        and latest.original_amount == original_amount
        and latest.original_currency == original_currency
        and (not compare_quantity or latest.quantity == quantity)
    ):
        return

    rate, rate_updated_at = _applied_usd_to_irt_rate()
    amount_usd = None
    amount_irt = None

    if rate is None:
        conversion_status = PriceExchangeSnapshot.ConversionStatus.MISSING_RATE
    elif original_currency == "USD":
        amount_usd = original_amount
        amount_irt = original_amount * rate
        conversion_status = PriceExchangeSnapshot.ConversionStatus.CONVERTED
    elif original_currency == "IRT":
        amount_usd = original_amount / rate
        amount_irt = original_amount
        conversion_status = PriceExchangeSnapshot.ConversionStatus.CONVERTED
    else:
        conversion_status = PriceExchangeSnapshot.ConversionStatus.UNSUPPORTED_CURRENCY

    PriceExchangeSnapshot.objects.create(
        content_type=content_type,
        object_id=instance.pk,
        price_field=price_field,
        part_id=part_id,
        quantity=quantity,
        original_amount=original_amount,
        original_currency=original_currency,
        usd_to_irt_rate=rate,
        amount_usd=amount_usd,
        amount_irt=amount_irt,
        source_updated_at=getattr(instance, "updated", None),
        rate_updated_at=rate_updated_at,
        conversion_status=conversion_status,
    )


def _capture_prices(
    instance,
    *,
    price_fields,
    supplier_price=False,
    compare_quantity=True,
):
    """Serialize and isolate auxiliary snapshot writes from the source save."""
    try:
        with transaction.atomic():
            locked_instance = (
                type(instance)
                .objects.select_for_update()
                .filter(pk=instance.pk)
                .first()
            )

            if locked_instance is None:
                return

            if supplier_price and locked_instance.part is None:
                return

            part_id = (
                locked_instance.part.part_id
                if supplier_price
                else locked_instance.part_id
            )
            quantity = getattr(locked_instance, "quantity", None)

            for price_field in price_fields:
                _capture_price(
                    locked_instance,
                    price_field=price_field,
                    part_id=part_id,
                    quantity=quantity,
                    compare_quantity=compare_quantity,
                )
    except DatabaseError:
        logger.exception(
            "Could not capture price snapshot for %s:%s",
            type(instance).__name__,
            instance.pk,
        )


@receiver(
    post_save,
    sender=SupplierPriceBreak,
    dispatch_uid="inventree_usd_irt_snapshot_supplier_price",
)
@receiver(
    post_save,
    sender=PartSellPriceBreak,
    dispatch_uid="inventree_usd_irt_snapshot_sale_price",
)
@receiver(
    post_save,
    sender=PartInternalPriceBreak,
    dispatch_uid="inventree_usd_irt_snapshot_internal_price",
)
def capture_price_break(sender, instance, raw=False, **kwargs):
    """Capture a supplier, sale, or internal price break after it is saved."""
    if not _can_capture(raw=raw):
        return

    _capture_prices(
        instance,
        price_fields=("price",),
        supplier_price=sender is SupplierPriceBreak,
    )


@receiver(
    post_save,
    sender=PurchaseOrderLineItem,
    dispatch_uid="inventree_usd_irt_snapshot_purchase_order_price",
)
def capture_purchase_order_price(sender, instance, raw=False, **kwargs):
    """Capture the unit price saved against a purchase-order line item."""
    if not _can_capture(raw=raw):
        return

    _capture_prices(
        instance,
        price_fields=("purchase_price",),
        supplier_price=True,
    )


@receiver(
    post_save,
    sender=StockItem,
    dispatch_uid="inventree_usd_irt_snapshot_stock_item_purchase_price",
)
def capture_stock_item_purchase_price(sender, instance, raw=False, **kwargs):
    """Capture the acquisition price saved on a physical stock item."""
    if not _can_capture(raw=raw):
        return

    _capture_prices(
        instance,
        price_fields=("purchase_price",),
        compare_quantity=False,
    )


@receiver(
    post_save,
    sender=PartPricing,
    dispatch_uid="inventree_usd_irt_snapshot_pricing_overrides",
)
def capture_pricing_overrides(sender, instance, raw=False, **kwargs):
    """Capture user-entered minimum and maximum price overrides."""
    if not _can_capture(raw=raw):
        return

    _capture_prices(
        instance,
        price_fields=("override_min", "override_max"),
    )
